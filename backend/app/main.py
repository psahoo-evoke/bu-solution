"""TransferIQ API (contract: docs/api/openapi.yaml). Run from backend/: `uvicorn app.main:app`.

AI recommends (matcher.py), rules compute (rules.py), evaluators decide (POST /decisions). Nothing here posts
credit on the AI's say-so: only a recorded human decision changes a line's credit.
"""
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import hashlib
import io
import logging
import os
import re
import threading
import uuid
from contextlib import asynccontextmanager
from html import escape as html_escape
from typing import Literal, Optional

from fastapi import APIRouter, FastAPI, File, Header, HTTPException, Path, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import accounts, blob_store, credit_chat, credit_check, db, notifications, notify, ratelimit
from . import store as store_mod
from .evaluation import evaluate_holdout
from .guard import MAX_UPLOAD_BYTES, RoleGuardMiddleware, auth_mode
from .ingest import UploadError, check_pdf_bytes, check_syllabus, parse_transcript, pdf_text
from .matcher import detect_injection, engine_name, recommend, recommend_many
from . import rules
from .rules import evaluate_student, tier_label, totals
from .store import Decision, ExtCourse, SyllabusRecord, TranscriptLine, TranscriptRecord

# uvicorn only configures its own loggers; give ours a handler so INFO lines (e.g. stored uploads) reach the
# container log stream.
_log = logging.getLogger("transferiq")
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)


def _prewarm() -> None:
    """Fill the matcher's model cache for the review queue and the holdout evaluation, so the first evaluator page
    load does not wait on the model. Best effort: a failure here only means the first request does the work."""
    try:
        recommend_many([(S().ext_courses[e], _bus(), S().syllabi.get(e)) for e in _maybe_lines()])
        evaluate_holdout(S())
    except Exception:
        _log.warning("prewarm failed", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if engine_name() == "azure-openai" and os.environ.get("TRANSFERIQ_PREWARM", "1") != "0":
        threading.Thread(target=_prewarm, name="prewarm", daemon=True).start()
    reminders = asyncio.create_task(_reminder_loop()) if rules.SYLLABUS_REMINDER_DAYS > 0 else None
    yield
    if reminders:
        reminders.cancel()


_entra = auth_mode() == "entra"
app = FastAPI(title="TransferIQ API", version="0.8.0",
              description="AI recommends, the rules engine computes, evaluators decide.", lifespan=lifespan,
              docs_url=None if _entra else "/docs", redoc_url=None, openapi_url=None if _entra else "/openapi.json")


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    """422 without echoing the submitted values: they can be private (passwords, transcript text) or not encodable
    (a lone surrogate would otherwise turn the 422 into a 500)."""
    errors = [{k: v for k, v in e.items() if k not in ("input", "ctx", "url")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


def cors_origins() -> list[str]:
    raw = os.environ.get("TRANSFERIQ_CORS_ORIGINS", "http://localhost:4200")
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]


# Order matters: the guard is added first so CORS wraps it (preflights and 401/403 responses get CORS headers).
app.add_middleware(RoleGuardMiddleware)          # ADR 0005 default deny + upload size limit, before any handler
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=True,
                   allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type", "X-Demo-Role", "Authorization"])
api = APIRouter(prefix="/api")

BATCH_THRESHOLD = 90           # R21: strictly above 90%
DEFAULT_CATALOG_YEAR = "2026-27"
STUDENT_ID_RE = r"^[A-Za-z0-9][A-Za-z0-9-]{0,31}$"
EXT_ID_RE = r"^[A-Z]{2,8}\|[A-Za-z0-9][A-Za-z0-9 .&-]{0,31}$"
BU_COURSE_RE = r"^(CAS [A-Z]{2} [0-9]{3}|CAS [A-Z]{2} [12]TR|TFRGEN 1TR|TFRGEN NOCRDT)$"   # contract v0.3.0
TR_RE = r"^(CAS [A-Z]{2} [12]TR|TFRGEN 1TR)$"
StudentIdPath = Path(..., pattern=STUDENT_ID_RE)
ExtIdPath = Path(..., pattern=EXT_ID_RE)


def S():
    return store_mod.STORE


def _bus():
    return list(S().bu_courses.values())


def _rec(ext_id: str) -> dict:
    c = S().ext_courses.get(ext_id)
    if c is None:
        raise HTTPException(404, f"Unknown course {ext_id}")
    return recommend(c, _bus(), S().syllabi.get(ext_id))


def _user(request: Request) -> Optional[dict]:
    """Signed-in portal user set by RoleGuardMiddleware (portal mode only; None in demo/entra mode)."""
    return (request.scope.get("state") or {}).get("user")


def _decided_by(request: Request, typed: str) -> str:
    """Who made a decision (Decision.decided_by, shown as `evaluator`, and in the audit entry).
    Portal and Entra: the verified sign-in, "Name <email>", never the name the browser sent. The email (or Entra
    sign-in name) makes it unique: display names repeat ("Transfer Evaluator") and a self-registered account picks
    its own. Without a verified identity outside demo mode the request is refused. Demo mode has no accounts:
    the typed name (X-Demo-Role is self-asserted there anyway)."""
    ident = (request.scope.get("state") or {}).get("identity")
    if auth_mode() != "demo":
        if not ident or not (ident.get("email") or ident.get("name")):
            raise HTTPException(401, "Sign in required to record a decision")
        name, email = ident.get("name", "").strip(), ident.get("email", "").strip()
        return (f"{name} <{email}>" if name and email else name or email)[:160]
    if not (typed or "").strip():
        raise HTTPException(422, "Enter the evaluator name")
    return typed.strip()


def _own_department_only(request: Request, ext_ids: list[str]) -> None:
    """Portal mode: a Department account decides only its own department's courses."""
    u = _user(request)
    if not u or u["role"] != "Department":
        return
    other = [e for e in ext_ids if e in S().ext_courses and S().ext_courses[e].program_area != u["department"]]
    if other:
        raise HTTPException(403, f"The {u['department']} department can only decide its own courses "
                                 f"(not {', '.join(other)})")


def _persist(fn, *args) -> None:
    """Write a change to PostgreSQL (when configured) BEFORE the in-memory store changes; a failed write fails the
    request with nothing changed."""
    if not db.enabled():
        return
    try:
        fn(*args)
    except db.DBError as e:
        raise HTTPException(503, str(e))


def _audit(role: str, action: str, ext_id: str, before, after, at: Optional[dt.datetime] = None):
    entry = dict(actor_role=role, action=action, ext_id=ext_id, before=before, after=after,
                 at=(at or dt.datetime.now(dt.timezone.utc)).isoformat())
    S().audit_log.append(entry)
    if db.enabled():
        db.save_audit(entry)   # best-effort, logged on failure


def build_evaluation(student_id: str) -> dict:
    st = S().students.get(student_id)
    if st is None:
        raise HTTPException(404, f"Unknown student {student_id}")
    cache: dict[str, dict] = {}

    def rec_cached(ext_id: str) -> Optional[dict]:
        if ext_id not in S().ext_courses:
            return None
        if ext_id not in cache:
            cache[ext_id] = _rec(ext_id)
        return cache[ext_id]

    def hint(ext_id: str):
        r = rec_cached(ext_id)
        if not r or not r["candidates"]:
            return None
        top = r["candidates"][0]
        return tier_label(top["overlap_pct"] / 100), top["bu_code"]

    lines = evaluate_student(S(), st, ai_hint=hint)
    for o in lines:
        if o["state"].startswith("maybe"):
            r = rec_cached(o["ext_id"])
            if r and r["candidates"]:
                o["ai_tier"] = r["candidates"][0]["tier"]
                o["ai_overlap_pct"] = r["candidates"][0]["overlap_pct"]
    for o in lines:
        o["syllabus_uploaded"] = _syllabus_uploaded(o["ext_id"])   # the UI hides Upload syllabus (upload once)
    public = [{k: v for k, v in o.items() if not k.startswith("_")} for o in lines]
    return dict(student=st.to_api(S().schools), lines=public, totals=totals(lines))


# ------------------------------------------------------------------ routes
@api.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------------ public credit check (no login, ADR 0006)
class CreditCheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    school: str = Field(min_length=1, max_length=80)
    course_code: str = Field("", max_length=20)
    title: str = Field("", max_length=120)
    description: str = Field("", max_length=credit_check.MAX_DESCRIPTION)
    grade: str = Field("", max_length=3)
    credits: Optional[float] = Field(None, gt=0, le=20)
    term: str = Field("", max_length=20)
    start_term: str = Field("Fall 2026", max_length=20)


def _client(request: Request) -> str:
    headers = {k.lower(): v for k, v in request.headers.items()}
    return ratelimit.client_key(headers, request.client.host if request.client else "")


def _public_limit(request: Request) -> str:
    """Per-client request limit; returns the client key for the AI budgets."""
    key = _client(request)
    try:
        ratelimit.PER_IP.hit(key)
    except ratelimit.RateLimited as e:
        raise HTTPException(429, str(e), headers={"Retry-After": str(e.retry_after)})
    return key


def run_credit_check(inp: CreditCheckInput, client: str, allow_estimate: bool = True) -> dict:
    """Facts first (no model call); the preliminary estimate only when needed and within the AI budgets."""
    args = inp.model_dump()
    try:
        res = credit_check.check_course(S(), **args, estimate=False)
        if res["kind"] == "needs_evaluation" and allow_estimate:
            if engine_name() == "azure-openai":
                ratelimit.ai_call(client)
            res = credit_check.check_course(S(), **args, estimate=True)
    except credit_check.CheckError as e:
        raise HTTPException(422, str(e))
    except ratelimit.RateLimited:
        res["message"] += " (A preliminary estimate is not available right now; please try again later.)"
    return res


@api.get("/credit-check/schools")
def credit_check_schools(request: Request):
    _public_limit(request)
    return credit_check.schools(S())


@api.get("/credit-check/courses")
def credit_check_courses(request: Request, school: str = Query(..., min_length=1, max_length=80)):
    _public_limit(request)
    rows = credit_check.courses(S(), school)
    if rows is None:
        raise HTTPException(404, "School not in the catalog")
    return rows


@api.post("/credit-check")
def post_credit_check(inp: CreditCheckInput, request: Request):
    return run_credit_check(inp, _public_limit(request))


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"]
    # user turns: at most MAX_MESSAGE_CHARS (checked in credit_chat); assistant turns are earlier replies, up to 1500
    content: str = Field(min_length=1, max_length=credit_chat.MAX_REPLY_CHARS)
    signature: Optional[str] = Field(None, pattern=r"^[0-9a-f]{64}$")     # the server's HMAC of an earlier reply

    @field_validator("content")
    @classmethod
    def _encodable(cls, v: str) -> str:
        """Lone surrogates ("\\ud800") are valid JSON but not text; reject them (422) instead of failing later."""
        try:
            v.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("Text contains invalid characters")
        return v


class CreditChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[ChatMessage] = Field(min_length=1, max_length=credit_chat.MAX_MESSAGES)


# Chat turns hold a worker thread while the model answers: cap them so staff routes always have threads left.
_CHAT_SLOTS = threading.BoundedSemaphore(int(os.environ.get("TRANSFERIQ_PUBLIC_CHAT_CONCURRENCY", "4")))


@api.post("/credit-chat")
def post_credit_chat(inp: CreditChatInput, request: Request):
    """Public chat turn; nothing is stored. 503 when no AI is configured (the page falls back to the form)."""
    client = _public_limit(request)
    if not _CHAT_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "The chat is busy right now; please use the course check form or try again shortly.",
                            headers={"Retry-After": "10"})
    try:
        return credit_chat.chat(S(), [m.model_dump() for m in inp.messages],
                                check=lambda args, est: run_credit_check(CreditCheckInput(**args), client, est),
                                ai_budget=lambda: ratelimit.ai_call(client))
    except credit_chat.ChatUnavailable as e:
        raise HTTPException(503, str(e))
    except credit_chat.ChatInputError as e:
        raise HTTPException(422, str(e))
    except ratelimit.RateLimited as e:
        raise HTTPException(429, "The chat is busy right now; please use the course check form or try again later.",
                            headers={"Retry-After": str(e.retry_after)})
    except Exception:
        _log.warning("credit chat failed", exc_info=True)
        raise HTTPException(502, "The chat could not answer right now; please use the course check form.")
    finally:
        _CHAT_SLOTS.release()


@api.get("/students")
def list_students(request: Request):
    u = _user(request)
    if u and u["role"] == "Student":           # portal: a student only ever sees their own record
        st = S().students.get(u["student_id"])
        return [st.to_api(S().schools)] if st else []
    return [st.to_api(S().schools) for st in S().students.values()]


@api.get("/students/{student_id}/evaluation")
def student_evaluation(student_id: str = StudentIdPath):
    return build_evaluation(student_id)


@api.get("/students/{student_id}/notifications")
def student_notifications(student_id: str = StudentIdPath):
    """In-app notifications (app/notifications.py). Reading them does not mark them read: a staff member looking at
    a student's record must not clear the student's unread count."""
    if student_id not in S().students:
        raise HTTPException(404, f"Unknown student {student_id}")
    return notifications.for_student(S(), student_id)


@api.post("/students/{student_id}/notifications/seen")
def student_notifications_seen(student_id: str = StudentIdPath):
    """The student opened their notifications: everything they were shown is read (Student role only; portal: own
    id). Read up to the newest notification, not "now": an event in the same moment stays unread."""
    if student_id not in S().students:
        raise HTTPException(404, f"Unknown student {student_id}")
    with S().lock:
        shown = notifications.for_student(S(), student_id)["items"]
        if shown:
            seen = shown[0]["at"]
            _persist(db.save_notification_seen, student_id, seen)
            S().notification_seen[student_id] = seen
    return notifications.for_student(S(), student_id)


PDF_PARSE_TIMEOUT_S = float(os.environ.get("TRANSFERIQ_PDF_TIMEOUT_S", "15"))


async def _parse_off_loop(fn, data: bytes):
    """Security F-04: PDF parsing runs in a worker thread with a time budget, so one slow PDF cannot stall the
    event loop. On time-out the request gets 422; the worker thread finishes in the background (Python threads
    cannot be killed), bounded by the 10 MB / 30-page limits."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(fn, data), timeout=PDF_PARSE_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise UploadError(422, f"The PDF took too long to read (over {PDF_PARSE_TIMEOUT_S:g} s)")


async def _read_upload(file: UploadFile) -> bytes:
    """Body size was already bounded by RoleGuardMiddleware; this re-checks the file part and the magic bytes."""
    head = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(head) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    try:
        check_pdf_bytes(head)
    except UploadError as e:
        raise HTTPException(e.status, e.detail)
    return head


async def _archive(kind: blob_store.Kind, key: str, data: bytes) -> Optional[str]:
    """Keep the original PDF in Blob Storage before any state changes. A configured archive that fails -> 502 and
    nothing is recorded, so an accepted upload is always stored. Not configured (offline) -> None."""
    try:
        return await asyncio.to_thread(blob_store.save_pdf, kind, key, data)
    except blob_store.BlobStoreError as e:
        raise HTTPException(502, str(e))


def _line_changes(old: list[TranscriptLine], new: list[TranscriptLine]) -> dict:
    """What a replacing transcript changed for one school, by (course, term): added, removed, grade/credits updated."""
    before = {(ln.ext_id, ln.term): ln for ln in old}
    after = {(ln.ext_id, ln.term): ln for ln in new}
    label = lambda ln: f"{ln.course_code} ({ln.term})"   # noqa: E731
    return dict(added=[label(ln) for k, ln in after.items() if k not in before],
                removed=[label(ln) for k, ln in before.items() if k not in after],
                updated=[label(ln) for k, ln in after.items()
                         if k in before and (before[k].grade, before[k].credits) != (ln.grade, ln.credits)])


@api.post("/students/{student_id}/transcripts", status_code=201)
async def upload_transcript(request: Request, student_id: str = StudentIdPath, file: UploadFile = File(...)):
    st = S().students.get(student_id)
    if st is None:
        raise HTTPException(404, f"Unknown student {student_id}")
    data = await _read_upload(file)
    try:
        parsed = await _parse_off_loop(parse_transcript, data)
    except UploadError as e:
        raise HTTPException(e.status, e.detail)
    school = next((s for s in S().schools.values() if s.name == parsed.institution), None)
    if school is None:
        raise HTTPException(422, f"Unknown institution '{parsed.institution[:80]}': only transcripts from schools in "
                                 f"the catalog can be read")
    if not parsed.lines:
        raise HTTPException(422, "No course lines found in transcript")
    # ADR 0004 for transcripts: course titles go into the AI prompt, and a real transcript never addresses an AI.
    injected = [ln.course_code for ln in parsed.lines if detect_injection(ln.title)]
    if injected:
        raise HTTPException(422, f"Not accepted: the course title of {', '.join(injected)} contains instructions "
                                 f"aimed at automated systems. Ask credit staff to review the transcript.")
    # The Student ID on a transcript is the previous school's id: it is stored, never compared with portal ids.
    # It is only checked against this student's earlier transcript from the same school.
    ref = parsed.student_ref
    digest = hashlib.sha256(data).hexdigest()
    prev = S().latest_transcript(student_id, school.school_code)
    if ref and prev and prev.school_student_id and prev.school_student_id != ref:
        raise HTTPException(422, f"This {school.name} transcript has student ID {ref}, but the {school.name} transcript "
                                 f"already on file has {prev.school_student_id}. Check it is the right student's transcript.")
    upload = dict(school_code=school.school_code, school_name=school.name, school_student_id=ref or None,
                  duplicate=False, replaced=False, added=[], removed=[], updated=[])
    if prev and prev.sha256 == digest:        # the same file again: nothing to store or change
        return dict(build_evaluation(student_id), upload=dict(upload, duplicate=True, transcript_id=prev.transcript_id))
    blob_url = await _archive("transcripts", student_id, data)
    u = _user(request)
    with S().lock:
        new_lines, new_courses = [], {}
        for p in parsed.lines:
            ext_id = f"{school.school_code}|{p.course_code}"
            if ext_id not in S().ext_courses and ext_id not in new_courses:
                num = int("".join(ch for ch in p.course_code.split()[-1] if ch.isdigit()) or 0)
                new_courses[ext_id] = ExtCourse(ext_id, school.school_code, p.course_code, p.title, p.credits,
                                                parsed.calendar, "", "Academic", 100 if num < 200 else 200,
                                                p.title, [], [])
            new_lines.append(TranscriptLine(student_id, school.school_code, p.term, ext_id, p.course_code, p.title,
                                            p.credits, parsed.calendar, p.grade))
        # Re-uploading a school's transcript replaces that school's lines, keeping transcript order.
        old = S().lines
        idx = next((i for i, ln in enumerate(old) if ln.student_id == student_id and ln.school_code == school.school_code), None)
        kept = [ln for ln in old if not (ln.student_id == student_id and ln.school_code == school.school_code)]
        if idx is None:
            last = max((i for i, ln in enumerate(kept) if ln.student_id == student_id), default=len(kept) - 1)
            idx = last + 1
        else:
            idx = sum(1 for ln in old[:idx] if not (ln.student_id == student_id and ln.school_code == school.school_code))
        lines = kept[:idx] + new_lines + kept[idx:]
        replaced = [ln for ln in old if ln.student_id == student_id and ln.school_code == school.school_code]
        if replaced:                          # seeded lines have no upload record, so compare lines, not records
            upload.update(_line_changes(replaced, new_lines), replaced=True)
        record = TranscriptRecord(
            transcript_id=f"TR-{uuid.uuid4().hex[:12]}", student_id=student_id, school_code=school.school_code,
            school_student_id=ref, sha256=digest, blob_url=blob_url or "", course_count=len(new_lines),
            uploaded_by=(u["email"] if u else request.headers.get("x-demo-role", "")),
            uploaded_at=dt.datetime.now(dt.timezone.utc).isoformat())
        _persist(db.save_transcript, student_id, list(new_courses.values()),
                 [ln for ln in lines if ln.student_id == student_id], record)
        S().ext_courses.update(new_courses)
        S().lines = lines
        S().transcripts.append(record)
    upload["syllabus_request"] = await auto_request_syllabi(student_id)        # step 5: ask once, automatically
    return dict(build_evaluation(student_id), upload=dict(upload, transcript_id=record.transcript_id))


def _syllabus_uploaded(ext_id: str) -> bool:
    rec = S().syllabi.get(ext_id)
    return bool(rec and rec.uploaded_at)


def _syllabus_not_uploaded_yet(ext_id: str) -> None:
    """A syllabus is uploaded through the app only once per course (no duplicates). Seed syllabi do not count."""
    if _syllabus_uploaded(ext_id):
        code = S().ext_courses[ext_id].course_code if ext_id in S().ext_courses else ext_id
        raise HTTPException(409, f"A syllabus for {code} has already been uploaded. It can only be uploaded once.")


@api.post("/courses/{ext_id}/syllabus", status_code=201)
async def upload_syllabus(request: Request, ext_id: str = ExtIdPath, file: UploadFile = File(...)):
    if ext_id not in S().ext_courses:
        raise HTTPException(404, f"Unknown course {ext_id}")
    u = _user(request)
    if u and u["role"] == "Student" and not any(
            ln.student_id == u["student_id"] and ln.ext_id == ext_id for ln in S().lines):
        raise HTTPException(403, "You can only add a syllabus for a course on your own transcript")
    _syllabus_not_uploaded_yet(ext_id)
    data = await _read_upload(file)
    try:
        text = await _parse_off_loop(pdf_text, data)
    except UploadError as e:
        raise HTTPException(e.status, e.detail)
    chk = check_syllabus(text)
    if not chk["looks_like_syllabus"]:
        raise HTTPException(422, "This does not look like a syllabus: no course code line and no syllabus sections "
                                 "(learning outcomes, schedule, …) were found.")
    own_code = S().ext_courses[ext_id].course_code
    if chk["course_code"] and chk["course_code"] != own_code:
        raise HTTPException(422, f"This syllabus is for {chk['course_code']}, not {own_code}.")
    inj = detect_injection(text)              # kept and flagged, not rejected: the sentences are sanitised (ADR 0004)
    stored = await _archive("syllabi", ext_id, data)
    rec = SyllabusRecord(ext_id=ext_id, state="complete" if chk["complete"] else "incomplete",
                         file=stored or f"upload-{uuid.uuid4().hex}.pdf", text=text, injection_detected=inj,
                         uploaded_at=dt.datetime.now(dt.timezone.utc).isoformat())
    with S().lock:
        _syllabus_not_uploaded_yet(ext_id)    # again under the lock: two uploads at the same moment -> one wins
        _persist(db.save_syllabus, rec, stored, chk["missing_sections"])
        S().syllabi[ext_id] = rec
    return dict(ext_id=ext_id, complete=chk["complete"], missing_sections=chk["missing_sections"],
                status_code="TP" if chk["complete"] else "TM", injection_detected=inj)


# ------------------------------------------------------------------ syllabus requests (step 5 of the process)
SYLLABUS_REQUEST_COOLDOWN = dt.timedelta(minutes=15)
NEEDS_SYLLABUS = ("maybe_ts", "maybe_tm")     # TS: no syllabus on file, TM: incomplete (rules.STATUS_CODE)


def syllabus_requests(student_id: Optional[str] = None, ext_id: Optional[str] = None) -> list[dict]:
    """Requests on record, newest first, from the audit log (saved in PostgreSQL, so they survive restarts)."""
    out = []
    for e in reversed(S().audit_log):
        a = e.get("after") or {}
        if e.get("action") != "syllabus_request" or (ext_id and e.get("ext_id") != ext_id):
            continue
        if student_id and a.get("student_id") != student_id:
            continue
        out.append(dict(student_id=a.get("student_id"), ext_id=e.get("ext_id"), requested_at=e.get("at"),
                        status=a.get("status"), automatic=bool(a.get("automatic")), reminder=bool(a.get("reminder")),
                        emailed_student=bool(a.get("emailed_student"))))
    return out


async def _send_syllabus_request(student_id: str, lines: list[dict], actor_role: str, by: str, automatic: bool,
                                 reminder: bool = False, at: Optional[dt.datetime] = None) -> dict:
    """One email for one student listing every course that needs a syllabus (TS) or a complete one (TM). A registered
    student receives it at their own address with the notification list copied; sample students are never emailed
    (app/notify.py). A failed send is recorded, never raised: the transcript upload that triggered it still succeeds."""
    st = S().students[student_id]
    own = accounts.registered_student_email(student_id)
    if own:
        to, cc = [own], [a for a in notify.recipients()[0] + notify.recipients()[1] if a.lower() != own.lower()]
    else:
        to, cc = notify.recipients()
    link = notify.app_link(f"/student/{student_id}")
    schools = {s.school_code: s.name for s in S().schools.values()}
    rows = []
    for o in lines:
        need = "a complete syllabus (learning outcomes and weekly schedule)" if o["state"] == "maybe_tm" else "the syllabus"
        rows.append((o, need))
    codes = ", ".join(o["course_code"] for o, _ in rows)
    subject = f"{'Reminder: s' if reminder else 'S'}yllabus needed for transfer credit: {codes} ({st.name}, {student_id})"
    text_rows = "\n".join(f"- {o['course_code']} \"{o['title']}\" ({schools.get(o['school_code'], o['school_code'])}, "
                          f"{o['term']}): {need}" for o, need in rows)
    text = (f"Hello {st.name},\n\nBoston University's Credit Evaluation Department is reviewing your transfer credit. "
            f"These courses have no existing equivalency, so a department evaluator compares the course syllabus with BU "
            f"courses. Please upload:\n{text_rows}\n\nUpload each as a PDF on your status page{': ' + link if link else ''}. "
            f"Until it arrives the course stays pending.\n\nRequested by {by}.\nTransferIQ transfer credit evaluation")
    e = html_escape
    html_rows = "".join(f"<li><strong>{e(o['course_code'])}</strong> &ldquo;{e(o['title'])}&rdquo; "
                        f"({e(schools.get(o['school_code'], o['school_code']))}, {e(o['term'])}): {e(need)}</li>"
                        for o, need in rows)
    link_html = f': <a href="{e(link)}">{e(link)}</a>' if link else ""
    html = (f"<p>Hello {e(st.name)},</p><p>Boston University's Credit Evaluation Department is reviewing your transfer "
            f"credit. These courses have no existing equivalency, so a department evaluator compares the course syllabus "
            f"with BU courses. Please upload:</p><ul>{html_rows}</ul><p>Upload each as a PDF on your status "
            f"page{link_html}. Until it arrives the course stays pending.</p>"
            f'<p style="color:#5a6370">Requested by {e(by)}.<br>TransferIQ transfer credit evaluation</p>')
    error = None
    try:
        status = await asyncio.to_thread(notify.send, subject, text, html, to, cc)
    except notify.NotifyError as err:
        status, error = "failed", str(err)     # recorded; the evaluator sees "failed", and the next upload retries
    for o, need in rows:
        _audit(actor_role, "syllabus_request", o["ext_id"], None,
               dict(student_id=student_id, status=status, to=to, cc=cc, automatic=automatic, reminder=reminder,
                    emailed_student=bool(own), need="complete" if o["state"] == "maybe_tm" else "syllabus"), at=at)
    return dict(status=status, courses=[o["course_code"] for o, _ in rows], to=to, cc=cc, emailed_student=bool(own),
                **({"error": error} if error else {}))


async def auto_request_syllabi(student_id: str) -> dict:
    """Step 5, automatic: after a transcript is processed, ask the student once for every "maybe" course without a
    complete syllabus. Skips courses already requested for this student and courses whose syllabus was already
    uploaded through the app (uploaded only once; a department reviews what is on file)."""
    st = S().students.get(student_id)
    if st is None:
        return dict(status="none", courses=[])
    asked = {r["ext_id"] for r in syllabus_requests(student_id) if r["status"] != "failed"}   # failed ones are retried
    todo = [o for o in evaluate_student(S(), st)
            if o["state"] in NEEDS_SYLLABUS and o["ext_id"] not in asked and not _syllabus_uploaded(o["ext_id"])]
    if not todo:
        return dict(status="none", courses=[])
    return await _send_syllabus_request(student_id, todo, "System", "the Credit Evaluation Department (automatic)",
                                        automatic=True)


def _reminder_plan(student_id: str, ext_id: str) -> dict:
    """First request, last successful send, reminders sent and when the next one is due (None: none planned)."""
    sent = [r for r in syllabus_requests(student_id, ext_id) if r["status"] != "failed"]      # newest first
    if not sent:
        return dict(requested_at=None, last_sent_at=None, reminders=0, next_reminder_at=None)
    reminders = sum(1 for r in sent if r["reminder"])
    last = dt.datetime.fromisoformat(sent[0]["requested_at"])
    due = None
    if rules.SYLLABUS_REMINDER_DAYS > 0 and reminders < rules.SYLLABUS_REMINDER_MAX:
        due = last + dt.timedelta(days=rules.SYLLABUS_REMINDER_DAYS)
    return dict(requested_at=sent[-1]["requested_at"], last_sent_at=sent[0]["requested_at"], reminders=reminders,
                next_reminder_at=due.isoformat() if due else None)


async def send_due_reminders(now: Optional[dt.datetime] = None) -> dict:
    """Re-request every syllabus that was requested, is still missing or incomplete and whose last (successful) request
    is TRANSFERIQ_SYLLABUS_REMINDER_DAYS old (default 2), at most TRANSFERIQ_SYLLABUS_REMINDER_MAX times (default 7).
    One email per student, and only where a mail service is configured. Stops by itself when the syllabus is uploaded
    or the course is decided (no longer maybe).
    Never starts a request: courses never requested (seeded sample data) get no reminders. A failed send does not
    count, so it is retried at the next check. Idempotent: the times come from the audit log (PostgreSQL)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    if rules.SYLLABUS_REMINDER_DAYS <= 0:
        return dict(students=0, courses=[], skipped="reminders are off (TRANSFERIQ_SYLLABUS_REMINDER_DAYS=0)")
    if not notify.configured():
        # Nothing can be delivered: record nothing either. A local or test instance sharing the database with the
        # deployed API must not write undeliverable reminders that would shift the real schedule.
        return dict(students=0, courses=[], skipped="no mail service configured")
    due: dict[str, list[dict]] = {}
    for sid, st in list(S().students.items()):
        for o in evaluate_student(S(), st):
            if o["state"] not in NEEDS_SYLLABUS or _syllabus_uploaded(o["ext_id"]):
                continue
            plan = _reminder_plan(sid, o["ext_id"])
            if plan["next_reminder_at"] and dt.datetime.fromisoformat(plan["next_reminder_at"]) <= now:
                due.setdefault(sid, []).append(o)
    courses = []
    for sid, lines in due.items():
        res = await _send_syllabus_request(sid, lines, "System", "the Credit Evaluation Department (automatic reminder)",
                                           automatic=True, reminder=True, at=now)
        courses += [f"{sid} {c}" for c in res["courses"]]
    if courses:
        _log.info("syllabus reminders sent for %d course(s)", len(courses))
    return dict(students=len(due), courses=courses)


REMINDER_CHECK_MINUTES = float(os.environ.get("TRANSFERIQ_SYLLABUS_REMINDER_CHECK_MINUTES", "60") or 60)


async def _reminder_loop() -> None:
    """Check for due reminders every REMINDER_CHECK_MINUTES (first check after one interval, not at start-up)."""
    while True:
        await asyncio.sleep(REMINDER_CHECK_MINUTES * 60)
        try:
            await send_due_reminders()
        except Exception:
            log.warning("syllabus reminder check failed", exc_info=True)


@api.post("/syllabus-reminders/run")
async def run_syllabus_reminders():
    """Send the reminders that are due now (the API also checks every hour on its own). For demos and external
    schedulers."""
    return await send_due_reminders()


@api.post("/students/{student_id}/courses/{ext_id}/syllabus-request", status_code=201)
async def request_syllabus(request: Request, student_id: str = StudentIdPath, ext_id: str = ExtIdPath,
                           x_demo_role: str = Header(...)):
    """Send the request for one course again (staff). The normal request is automatic after a transcript upload
    (auto_request_syllabi). Repeats within 15 minutes are skipped."""
    st = S().students.get(student_id)
    if st is None:
        raise HTTPException(404, f"Unknown student {student_id}")
    line = next((ln for ln in S().lines if ln.student_id == student_id and ln.ext_id == ext_id), None)
    if line is None:
        raise HTTPException(404, f"Course {ext_id} is not on {student_id}'s transcript")
    _syllabus_not_uploaded_yet(ext_id)       # nothing to ask for once it is uploaded (409)
    last = next((r for r in syllabus_requests(student_id, ext_id) if r["status"] != "failed"), None)
    now = dt.datetime.now(dt.timezone.utc)
    if last and now - dt.datetime.fromisoformat(last["requested_at"]) < SYLLABUS_REQUEST_COOLDOWN:
        to, cc = notify.recipients()
        return dict(student_id=student_id, ext_id=ext_id, status="already_requested", to=to, cc=cc,
                    requested_at=last["requested_at"])
    state = "maybe_tm" if S().syllabus_state(ext_id) == "incomplete" else "maybe_ts"
    u = _user(request)
    by = f"{u['name']} ({u['role']})" if u else x_demo_role
    res = await _send_syllabus_request(student_id, [dict(ext_id=ext_id, course_code=line.course_code, title=line.title,
                                                         school_code=line.school_code, term=line.term, state=state)],
                                       x_demo_role, by, automatic=False)
    if res["status"] == "failed":
        raise HTTPException(502, res.get("error") or "The email could not be sent")
    return dict(student_id=student_id, ext_id=ext_id, status=res["status"], to=res["to"], cc=res["cc"],
                requested_at=now.isoformat())


@api.get("/courses/{ext_id}/syllabus")
def course_syllabus(request: Request, ext_id: str = ExtIdPath):
    """What the department evaluator reads next to the AI comparison: the syllabus text on file (as extracted from
    the PDF; shown as plain text, never as HTML) and the requests sent to the students waiting on this course.
    Staff only (x-roles); a department sees only its own courses."""
    if ext_id not in S().ext_courses:
        raise HTTPException(404, f"Unknown course {ext_id}")
    _own_department_only(request, [ext_id])
    rec = S().syllabi.get(ext_id)
    names = {sid: st.name for sid, st in S().students.items()}
    waiting = sorted({ln.student_id for ln in S().lines if ln.ext_id == ext_id})
    return dict(ext_id=ext_id, state=S().syllabus_state(ext_id),
                source=("upload" if rec and rec.uploaded_at else "on file") if rec and rec.text else None,
                uploaded_at=(rec.uploaded_at or None) if rec else None,
                injection_detected=bool(rec and rec.injection_detected),
                text=(rec.text[:SYLLABUS_TEXT_MAX] if rec and rec.text else None),
                truncated=bool(rec and len(rec.text or "") > SYLLABUS_TEXT_MAX),
                # What the matcher used when the syllabus lists no outcomes, so the evaluator can trace the score.
                catalogue_outcomes=list(S().ext_courses[ext_id].learning_outcomes),
                requests=[_request_summary(sid, ext_id, names) for sid in waiting
                          if syllabus_requests(sid, ext_id)])


def _request_summary(student_id: str, ext_id: str, names: dict) -> dict:
    """One line per student: the first request, the latest attempt and the reminder plan."""
    reqs = syllabus_requests(student_id, ext_id)                           # newest first, failed ones included
    latest = reqs[0]
    plan = _reminder_plan(student_id, ext_id)
    st = S().students.get(student_id)
    # The same rule as send_due_reminders: only a course still waiting for its syllabus (TS/TM) gets reminders. An old
    # request on a course that is now, for example, under age review (RV-AGE) shows no next reminder.
    open_ = bool(st) and not _syllabus_uploaded(ext_id) and any(
        o["ext_id"] == ext_id and o["state"] in NEEDS_SYLLABUS for o in evaluate_student(S(), st))
    return dict(student_id=student_id, student_name=names.get(student_id, student_id),
                requested_at=plan["requested_at"] or reqs[-1]["requested_at"], last_sent_at=plan["last_sent_at"],
                reminders=plan["reminders"], next_reminder_at=plan["next_reminder_at"] if open_ else None,
                status=latest["status"], automatic=latest["automatic"], emailed_student=latest["emailed_student"])


SYLLABUS_TEXT_MAX = 30_000


@api.get("/courses/{ext_id}/recommendation")
def course_recommendation(ext_id: str = ExtIdPath):
    rec = _rec(ext_id)
    top = rec["candidates"][0]["bu_code"] if rec["candidates"] else None
    past = [d for d in S().decisions if d.ext_id == ext_id or (top and d.bu_course == top)]  # holdout excluded
    past.sort(key=lambda d: (d.ext_id != ext_id, d.decision_date), reverse=False)
    rec["past_decisions"] = [d.to_api() for d in past[:5]]
    return rec


def _maybe_lines():
    out = {}
    for st in S().students.values():
        for o in evaluate_student(S(), st):
            if o["state"].startswith("maybe"):
                out.setdefault(o["ext_id"], []).append(st.student_id)
    return out


@api.get("/review-queue")
def review_queue(request: Request, department: Optional[str] = Query(None)):
    u = _user(request)
    if u and u["role"] == "Department":        # portal: a department sees only its own courses
        department = u["department"]
    items = []
    rows = [(ext_id, students) for ext_id, students in _maybe_lines().items()
            if not department or S().ext_courses[ext_id].program_area.lower() == department.lower()]
    recs = recommend_many([(S().ext_courses[e], _bus(), S().syllabi.get(e)) for e, _ in rows])
    for (ext_id, students), rec in zip(rows, recs):
        c = S().ext_courses[ext_id]
        top = rec["candidates"][0] if rec["candidates"] else None
        items.append(dict(ext_id=ext_id, course_code=c.course_code, title=c.title, school_code=c.school_code,
                          department=c.program_area, students=students, syllabus_state=S().syllabus_state(ext_id),
                          top_candidate=top, confidence_pct=rec["confidence_pct"],
                          preliminary=rec["preliminary"], injection_detected=rec["injection_detected"],
                          batch_eligible=_batch_problem(rec) is None))
    return items


class DecisionInput(BaseModel):
    ext_id: str = Field(pattern=EXT_ID_RE)
    decision: Literal["Equivalent", "Elective", "No credit"]
    bu_course: str = Field(pattern=BU_COURSE_RE)
    reason_code: str
    reusable: bool = True
    evaluator: str = Field("", max_length=80)          # demo mode only; signed in, the verified identity is used
    catalog_year: str = Field(DEFAULT_CATALOG_YEAR, pattern=r"^\d{4}-\d{2}$")
    note: str = Field("", max_length=1000)


def _validate_decision(inp: DecisionInput) -> None:
    """Security F-02 / contract v0.3.0: bu_course must agree with the decision, reason_code must exist and belong
    to the same decision. (The pattern itself is enforced by DecisionInput.)"""
    s = S()
    if inp.decision == "Equivalent" and inp.bu_course not in s.bu_courses:
        raise HTTPException(422, f"Equivalent needs a known BU course; {inp.bu_course!r} is not in the catalogue")
    if inp.decision == "Elective" and not re.match(TR_RE, inp.bu_course):
        raise HTTPException(422, "Elective needs a TR elective code (CAS <DEPT> 1TR/2TR or TFRGEN 1TR)")
    if inp.decision == "No credit" and inp.bu_course != "TFRGEN NOCRDT":
        raise HTTPException(422, "No credit must use TFRGEN NOCRDT")
    rc = s.reason_codes.get(inp.reason_code)
    if rc is None:
        raise HTTPException(422, f"Unknown reason code {inp.reason_code}")
    if rc["decision"] != inp.decision:
        raise HTTPException(422, f"Reason code {inp.reason_code} is for '{rc['decision']}', not '{inp.decision}'")


def _save_decision(inp: DecisionInput, role: str, rec: Optional[dict]) -> Decision:
    s = S()
    if inp.ext_id not in s.ext_courses:
        raise HTTPException(404, f"Unknown course {inp.ext_id}")
    _validate_decision(inp)
    sugg = f"{rec['suggested_decision']} {rec['suggested_code']}" if rec else None
    agreed = None
    if rec:
        agreed = rec["suggested_code"] == inp.bu_course and (
            rec["suggested_decision"] == inp.decision or rec["suggested_decision"] == "Evaluator decides")
    applies_to = None
    if not inp.reusable:  # one-off decision: only the students waiting on this course right now
        applies_to = sorted({ln.student_id for ln in s.lines if ln.ext_id == inp.ext_id})
    d = Decision(decision_id=s.next_decision_id(), ext_id=inp.ext_id, decision=inp.decision, bu_course=inp.bu_course,
                 reason_code=inp.reason_code, reusable=inp.reusable, catalog_year=inp.catalog_year,
                 decided_by=inp.evaluator, decision_date=dt.datetime.now(dt.timezone.utc).isoformat(),
                 split="runtime", note=inp.note, ai_suggestion=sugg, ai_agreed=agreed, applies_to=applies_to)
    with s.lock:
        _persist(db.save_decisions, [d])
        s.decisions.append(d)
    _audit(role, "decision", inp.ext_id, None, d.to_api())   # actor role recorded (checklist section 1)
    return d


@api.post("/decisions", status_code=201)
def post_decision(inp: DecisionInput, request: Request, x_demo_role: str = Header(...)):
    role = x_demo_role               # already authorised by RoleGuardMiddleware (ADR 0005)
    _own_department_only(request, [inp.ext_id])
    inp = inp.model_copy(update=dict(evaluator=_decided_by(request, inp.evaluator)))
    rec = _rec(inp.ext_id) if inp.ext_id in S().ext_courses else None
    return _save_decision(inp, role, rec).to_api()


class BatchInput(BaseModel):
    ext_ids: list[str] = Field(min_length=1, max_length=200)
    evaluator: str = Field("", max_length=80)          # demo mode only (see _decided_by)


def _batch_problem(rec: dict) -> Optional[str]:
    if rec["confidence_pct"] <= BATCH_THRESHOLD:                     # R21
        return f"confidence {rec['confidence_pct']}% is not above {BATCH_THRESHOLD}%"
    if rec["preliminary"]:                                           # R22: description only, not decidable
        return "preliminary (no complete syllabus on file)"
    if rec["injection_detected"]:                                    # ADR 0004: needs a human look
        return "course text flagged for injected instructions"
    if rec["suggested_decision"] == "Evaluator decides":
        return "tier requires an evaluator decision"
    return None


@api.post("/decisions/batch", status_code=201)
def post_batch(inp: BatchInput, request: Request, x_demo_role: str = Header(...)):
    role = x_demo_role               # Evaluator or Department, enforced by RoleGuardMiddleware
    inp = inp.model_copy(update=dict(evaluator=_decided_by(request, inp.evaluator)))
    recs, problems = {}, []
    bad = [e for e in inp.ext_ids if not re.match(EXT_ID_RE, e)]
    if bad:
        raise HTTPException(422, dict(message="Invalid ext_id", items=bad))
    _own_department_only(request, inp.ext_ids)
    for e in inp.ext_ids:
        rec = _rec(e)
        p = _batch_problem(rec)
        if p:
            problems.append(dict(ext_id=e, problem=p, confidence_pct=rec["confidence_pct"]))
        recs[e] = rec
    if problems:
        raise HTTPException(422, dict(message="Batch rejected; nothing saved", items=problems))
    saved = []
    for e, rec in recs.items():
        if rec["suggested_decision"] == "Equivalent":
            reason = "EQ-CONTENT"
        elif rec["candidates"] and rec["candidates"][0]["tier"] == "equivalent":
            reason = "EL-RESIDENCY"      # R13: equivalent to a BU-only (Group C) course -> elective
        else:
            reason = "EL-LOWOVERLAP"
        inp_d = DecisionInput(ext_id=e, decision=rec["suggested_decision"], bu_course=rec["suggested_code"],
                              reason_code=reason, reusable=True, evaluator=inp.evaluator,
                              note=f"Batch-approved (R21), AI confidence {rec['confidence_pct']}%")
        saved.append(_save_decision(inp_d, role, rec).to_api())
    return saved


def _csv_safe(v) -> str:
    """CSV/formula injection guard (checklist section 5): prefix cells that Excel would evaluate."""
    v = "" if v is None else str(v)
    return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v


class PostingInput(BaseModel):
    student_id: Optional[str] = Field(None, pattern=STUDENT_ID_RE)


@api.post("/postings", status_code=201)
def post_postings(inp: Optional[PostingInput] = None, x_demo_role: str = Header(...)):
    """Registrar step: every `approved` line (for one student, or all) becomes `posted` (secured, T).
    Returns the MyBU-style CSV of exactly the rows posted. GET /exports/mybu.csv stays a read-only preview."""
    student_id = inp.student_id if inp else None
    s = S()
    ids = [student_id] if student_id else list(s.students)
    if student_id and student_id not in s.students:
        raise HTTPException(404, f"Unknown student {student_id}")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["student_id", "ext_course", "bu_course", "units", "grade"])
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    posted = 0
    with s.lock:
        todo = [(sid, o) for sid in ids for o in evaluate_student(s, s.students[sid]) if o["state"] == "approved"]
        items = [((sid, o["ext_id"], o["term"]), dict(decision_id=o["_decision_id"], posted_at=now,
                                                       actor_role=x_demo_role)) for sid, o in todo]
        _persist(db.save_postings, items)            # all postings of this request in one transaction
        for (key, val), (sid, o) in zip(items, todo):
            s.postings[key] = val
            w.writerow([_csv_safe(v) for v in (sid, o["ext_id"], o["bu_course"], f"{o['units']:.2f}", "T")])
            _audit(x_demo_role, "posting", o["ext_id"], dict(student_id=sid, state="approved"),
                   dict(student_id=sid, state="posted", bu_course=o["bu_course"], units=o["units"]))
            posted += 1
    return dict(posted=posted, csv=buf.getvalue())


@api.get("/exports/mybu.csv")
def export_mybu(student_id: Optional[str] = Query(None, pattern=STUDENT_ID_RE)):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["student_id", "ext_course", "bu_course", "units", "grade"])
    ids = [student_id] if student_id else list(S().students)
    for sid in ids:
        if sid not in S().students:
            raise HTTPException(404, f"Unknown student {sid}")
        for o in evaluate_student(S(), S().students[sid]):
            if o["state"] in ("matched", "approved", "posted", "posted_no_credit"):   # R24 rows (preview)
                w.writerow([_csv_safe(v) for v in (sid, o["ext_id"], o["bu_course"], f"{o['units']:.2f}", o["bu_grade"])])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=mybu.csv"})


@api.get("/evaluation/metrics")
def metrics():
    m = evaluate_holdout(S())
    return {k: v for k, v in m.items() if k != "rows"}


@api.get("/rules")
def rules_list():
    return [dict(rule_id=r["rule_id"], category=r["category"], rule=r["rule"], reason_code=r["reason_code"])
            for r in S().rules]


@api.get("/reason-codes")
def reason_codes():
    return [dict(reason_code=r["reason_code"], decision=r["decision"], meaning=r["meaning"])
            for r in S().reason_codes.values()]


@api.post("/demo/reset", status_code=204)
def demo_reset():
    if auth_mode() == "entra":       # ADR 0005: disabled outside the demo
        raise HTTPException(403, "Demo reset is disabled in entra mode")
    try:
        store_mod.reset()                    # PostgreSQL mode: seed rows restored in the database too
    except db.DBError as e:
        raise HTTPException(503, str(e))
    accounts.restore_registered_students()   # registered accounts survive a demo reset
    return Response(status_code=204)


# ------------------------------------------------------------------ portal sign-in (TRANSFERIQ_AUTH_MODE=portal)
# Public routes (guard.PUBLIC). Kept on their own router: they are not role-gated operations of the contract.
auth_api = APIRouter(prefix="/api/auth")


class LoginInput(BaseModel):
    email: str = Field(max_length=120)
    password: str = Field(max_length=200)
    portal: Literal["student", "department", "staff"]


class StudentRegistration(BaseModel):
    name: str = Field(max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(max_length=200)
    intended_major: str = Field(max_length=60)
    start_term: str = Field("Fall 2026", max_length=20)


class DepartmentRegistration(BaseModel):
    name: str = Field(max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(max_length=200)
    department: str = Field(max_length=60)


def _portal_session(acct: accounts.Account) -> dict:
    return dict(token=accounts.issue_token(acct), user=acct.public(), expires_in=accounts.SESSION_HOURS * 3600)


def _account_call(fn, *args):
    if auth_mode() != "portal":
        raise HTTPException(409, "Portal sign-in is not enabled on this server")
    try:
        return _portal_session(fn(*args))
    except accounts.AccountError as e:
        raise HTTPException(e.status, e.detail)


@auth_api.get("/options")
def auth_options():
    majors = sorted({s.intended_major for s in S().students.values()} |
                    {d for d in accounts.departments() if d != "General education"})
    return dict(mode=auth_mode(), departments=accounts.departments(), majors=majors,
                terms=["Fall 2026", "Spring 2027", "Fall 2027"])


@auth_api.post("/login")
def auth_login(inp: LoginInput):
    return _account_call(accounts.authenticate, inp.email, inp.password, inp.portal)


@auth_api.post("/register/student", status_code=201)
def auth_register_student(inp: StudentRegistration):
    return _account_call(accounts.register_student, inp.name, inp.email, inp.password, inp.intended_major,
                         inp.start_term)


@auth_api.post("/register/department", status_code=201)
def auth_register_department(inp: DepartmentRegistration):
    return _account_call(accounts.register_department, inp.name, inp.email, inp.password, inp.department)


app.include_router(api)
app.include_router(auth_api)
