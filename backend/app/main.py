"""TransferIQ API (contract: docs/api/openapi.yaml). Run from backend/: `uvicorn app.main:app`.

AI recommends (matcher.py), rules compute (rules.py), evaluators decide (POST /decisions). Nothing here posts
credit on the AI's say-so: only a recorded human decision changes a line's credit.
"""
from __future__ import annotations

import asyncio
import csv
import datetime as dt
import io
import logging
import os
import re
import uuid
from html import escape as html_escape
from typing import Literal, Optional

from fastapi import APIRouter, FastAPI, File, Header, HTTPException, Path, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import accounts, blob_store, notify
from . import store as store_mod
from .evaluation import evaluate_holdout
from .guard import MAX_UPLOAD_BYTES, RoleGuardMiddleware, auth_mode
from .ingest import UploadError, check_pdf_bytes, check_syllabus, parse_transcript, pdf_text
from .matcher import detect_injection, recommend
from .rules import evaluate_student, tier_label, totals
from .store import Decision, ExtCourse, SyllabusRecord, TranscriptLine

# uvicorn only configures its own loggers; give ours a handler so INFO lines (e.g. stored uploads) reach the
# container log stream.
_log = logging.getLogger("transferiq")
if not _log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:     %(name)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)

_entra = auth_mode() == "entra"
app = FastAPI(title="TransferIQ API", version="0.3.0",
              description="AI recommends, the rules engine computes, evaluators decide.",
              docs_url=None if _entra else "/docs", redoc_url=None, openapi_url=None if _entra else "/openapi.json")


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


def _own_department_only(request: Request, ext_ids: list[str]) -> None:
    """Portal mode: a Department account decides only its own department's courses."""
    u = _user(request)
    if not u or u["role"] != "Department":
        return
    other = [e for e in ext_ids if e in S().ext_courses and S().ext_courses[e].program_area != u["department"]]
    if other:
        raise HTTPException(403, f"The {u['department']} department can only decide its own courses "
                                 f"(not {', '.join(other)})")


def _audit(role: str, action: str, ext_id: str, before, after):
    S().audit_log.append(dict(actor_role=role, action=action, ext_id=ext_id, before=before, after=after,
                              at=dt.datetime.now(dt.timezone.utc).isoformat()))


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
    public = [{k: v for k, v in o.items() if not k.startswith("_")} for o in lines]
    return dict(student=st.to_api(), lines=public, totals=totals(lines))


# ------------------------------------------------------------------ routes
@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/students")
def list_students(request: Request):
    u = _user(request)
    if u and u["role"] == "Student":           # portal: a student only ever sees their own record
        st = S().students.get(u["student_id"])
        return [st.to_api()] if st else []
    return [s.to_api() for s in S().students.values()]


@api.get("/students/{student_id}/evaluation")
def student_evaluation(student_id: str = StudentIdPath):
    return build_evaluation(student_id)


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


@api.post("/students/{student_id}/transcripts", status_code=201)
async def upload_transcript(student_id: str = StudentIdPath, file: UploadFile = File(...)):
    st = S().students.get(student_id)
    if st is None:
        raise HTTPException(404, f"Unknown student {student_id}")
    data = await _read_upload(file)
    try:
        parsed = await _parse_off_loop(parse_transcript, data)
    except UploadError as e:
        raise HTTPException(e.status, e.detail)
    if parsed.student_ref and not parsed.student_ref.startswith(student_id):
        raise HTTPException(422, f"Transcript belongs to {parsed.student_ref}, not {student_id}")
    school = next((s for s in S().schools.values() if s.name == parsed.institution), None)
    if school is None:
        raise HTTPException(422, f"Unknown institution '{parsed.institution}'")
    if not parsed.lines:
        raise HTTPException(422, "No course lines found in transcript")
    await _archive("transcripts", student_id, data)
    with S().lock:
        new_lines = []
        for p in parsed.lines:
            ext_id = f"{school.school_code}|{p.course_code}"
            if ext_id not in S().ext_courses:
                num = int("".join(ch for ch in p.course_code.split()[-1] if ch.isdigit()) or 0)
                S().ext_courses[ext_id] = ExtCourse(ext_id, school.school_code, p.course_code, p.title, p.credits,
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
        S().lines = kept[:idx] + new_lines + kept[idx:]
    return build_evaluation(student_id)


@api.post("/courses/{ext_id}/syllabus", status_code=201)
async def upload_syllabus(request: Request, ext_id: str = ExtIdPath, file: UploadFile = File(...)):
    if ext_id not in S().ext_courses:
        raise HTTPException(404, f"Unknown course {ext_id}")
    u = _user(request)
    if u and u["role"] == "Student" and not any(
            ln.student_id == u["student_id"] and ln.ext_id == ext_id for ln in S().lines):
        raise HTTPException(403, "You can only add a syllabus for a course on your own transcript")
    data = await _read_upload(file)
    try:
        text = await _parse_off_loop(pdf_text, data)
    except UploadError as e:
        raise HTTPException(e.status, e.detail)
    chk = check_syllabus(text)
    inj = detect_injection(text)
    stored = await _archive("syllabi", ext_id, data)
    with S().lock:
        S().syllabi[ext_id] = SyllabusRecord(ext_id=ext_id, state="complete" if chk["complete"] else "incomplete",
                                             file=stored or f"upload-{uuid.uuid4().hex}.pdf", text=text,
                                             injection_detected=inj)
    return dict(ext_id=ext_id, complete=chk["complete"], missing_sections=chk["missing_sections"],
                status_code="TP" if chk["complete"] else "TM", injection_detected=inj)


SYLLABUS_REQUEST_COOLDOWN = dt.timedelta(minutes=15)
_syllabus_requests: dict[tuple[str, str], dt.datetime] = {}


@api.post("/students/{student_id}/courses/{ext_id}/syllabus-request", status_code=201)
async def request_syllabus(request: Request, student_id: str = StudentIdPath, ext_id: str = ExtIdPath,
                           x_demo_role: str = Header(...)):
    """Email "syllabus needed, please upload" to the notification list (app/notify.py). Triggered from the
    Upload syllabus button. Never emails the student's own address in this build."""
    st = S().students.get(student_id)
    if st is None:
        raise HTTPException(404, f"Unknown student {student_id}")
    line = next((ln for ln in S().lines if ln.student_id == student_id and ln.ext_id == ext_id), None)
    if line is None:
        raise HTTPException(404, f"Course {ext_id} is not on {student_id}'s transcript")
    to, cc = notify.recipients()
    now = dt.datetime.now(dt.timezone.utc)
    key = (student_id, ext_id)
    last = _syllabus_requests.get(key)
    if last and now - last < SYLLABUS_REQUEST_COOLDOWN:
        return dict(student_id=student_id, ext_id=ext_id, status="already_requested", to=to, cc=cc,
                    requested_at=last.isoformat())

    school = next((s.name for s in S().schools.values() if s.school_code == line.school_code), line.school_code)
    state = S().syllabus_state(ext_id)
    need = "an updated, complete syllabus" if state == "incomplete" else "the syllabus"
    u = _user(request)
    by = f"{u['name']} ({u['role']})" if u else x_demo_role
    link = notify.app_link(f"/student/{student_id}")
    subject = f"Syllabus needed: {line.course_code} for {st.name} ({student_id})"
    text = (f"Hello,\n\nTransferIQ needs {need} for {line.course_code} \"{line.title}\" ({school}, {line.term}) "
            f"on the transcript of {st.name} ({student_id}).\n\nPlease upload it as a PDF on the student's status page"
            f"{': ' + link if link else ''}.\nUntil it arrives this course stays pending.\n\nRequested by {by}.\n"
            f"TransferIQ transfer credit evaluation")
    e = html_escape
    link_html = f': <a href="{e(link)}">{e(link)}</a>' if link else ""
    html = (f"<p>Hello,</p><p>TransferIQ needs <strong>{e(need)}</strong> for <strong>{e(line.course_code)} "
            f"&ldquo;{e(line.title)}&rdquo;</strong> ({e(school)}, {e(line.term)}) on the transcript of "
            f"<strong>{e(st.name)}</strong> ({e(student_id)}).</p>"
            f"<p>Please upload it as a PDF on the student's status page{link_html}. "
            f"Until it arrives this course stays pending.</p>"
            f'<p style="color:#5a6370">Requested by {e(by)}.<br>TransferIQ transfer credit evaluation</p>')
    try:
        status = await asyncio.to_thread(notify.send, subject, text, html)
    except notify.NotifyError as err:
        raise HTTPException(502, str(err))
    _syllabus_requests[key] = now
    _audit(x_demo_role, "syllabus_request", ext_id, None, dict(student_id=student_id, status=status, to=to, cc=cc))
    return dict(student_id=student_id, ext_id=ext_id, status=status, to=to, cc=cc, requested_at=now.isoformat())


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
    for ext_id, students in _maybe_lines().items():
        c = S().ext_courses[ext_id]
        if department and c.program_area.lower() != department.lower():
            continue
        rec = _rec(ext_id)
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
    evaluator: str = Field(min_length=1, max_length=80)
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
        s.decisions.append(d)
    _audit(role, "decision", inp.ext_id, None, d.to_api())   # actor role recorded (checklist section 1)
    return d


@api.post("/decisions", status_code=201)
def post_decision(inp: DecisionInput, request: Request, x_demo_role: str = Header(...)):
    role = x_demo_role               # already authorised by RoleGuardMiddleware (ADR 0005)
    _own_department_only(request, [inp.ext_id])
    rec = _rec(inp.ext_id) if inp.ext_id in S().ext_courses else None
    return _save_decision(inp, role, rec).to_api()


class BatchInput(BaseModel):
    ext_ids: list[str] = Field(min_length=1, max_length=200)
    evaluator: str = Field(min_length=1, max_length=80)


def _batch_problem(rec: dict) -> Optional[str]:
    if rec["confidence_pct"] <= BATCH_THRESHOLD:                     # R21
        return f"confidence {rec['confidence_pct']}% is not above {BATCH_THRESHOLD}%"
    if rec["preliminary"]:                                           # R22: description only, not decidable
        return "preliminary (no complete syllabus on file)"
    if rec["injection_detected"]:                                    # ADR 0004: needs a human look
        return "syllabus flagged for injected instructions"
    if rec["suggested_decision"] == "Evaluator decides":
        return "tier requires an evaluator decision"
    return None


@api.post("/decisions/batch", status_code=201)
def post_batch(inp: BatchInput, request: Request, x_demo_role: str = Header(...)):
    role = x_demo_role               # Evaluator or Department, enforced by RoleGuardMiddleware
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
        for sid in ids:
            for o in evaluate_student(s, s.students[sid]):
                if o["state"] != "approved":
                    continue
                s.postings[(sid, o["ext_id"], o["term"])] = dict(decision_id=o["_decision_id"], posted_at=now,
                                                                 actor_role=x_demo_role)
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
    store_mod.reset()
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
