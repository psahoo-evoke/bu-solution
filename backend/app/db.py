"""PostgreSQL persistence (schema: backend/db/schema.sql, database bu-solution-pg / butransfer).

Enabled when POSTGRES_HOST is set (with POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD; without a password an Entra
token for the managed identity is used). POSTGRES_SCHEMA (default public) selects the schema, which tests use to work
in a throw-away schema. Without POSTGRES_HOST nothing here runs and the app keeps its in-memory store (ADR 0003: tests
and local runs need no database).

How it is used (app/store.py, app/main.py, app/accounts.py):
- Start-up: load_store() fills the in-memory Store from the tables; rules and reason codes still come from the seed
  CSVs (they are not in the schema). An empty database is first seeded from the CSVs.
- Every change is written to the database BEFORE the in-memory store changes; a failed write raises DBError and the
  request fails (503) with nothing changed. Audit entries are written best-effort (logged if they fail).
- Demo reset: reseed() restores the seed rows of the mutable tables; registered students and accounts are kept.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import threading
from contextlib import contextmanager
from typing import Iterator, Optional

log = logging.getLogger("transferiq.db")


class DBError(Exception):
    pass


def enabled() -> bool:
    return bool(os.environ.get("POSTGRES_HOST", "").strip())


def schema() -> str:
    return os.environ.get("POSTGRES_SCHEMA", "public").strip() or "public"


_CONN = None
_LOCK = threading.RLock()


def _connect():
    import psycopg  # lazy: offline tests and local runs never import it

    password = os.environ.get("POSTGRES_PASSWORD") or None
    if password is None:   # Entra auth: the managed identity's token is the password
        from .ingest import azure_credential
        password = azure_credential().get_token("https://ossrdbms-aad.database.windows.net/.default").token
    conn = psycopg.connect(host=os.environ["POSTGRES_HOST"], dbname=os.environ.get("POSTGRES_DB", "postgres"),
                           user=os.environ["POSTGRES_USER"], password=password, sslmode="require",
                           connect_timeout=30, options=f"-c search_path={schema()}")
    log.info("connected to PostgreSQL %s/%s (schema %s)", os.environ["POSTGRES_HOST"],
             os.environ.get("POSTGRES_DB"), schema())
    return conn


@contextmanager
def tx() -> Iterator:
    """One transaction on the shared connection (single API replica, low traffic). Reconnects once if the
    connection was dropped; any database error becomes DBError."""
    global _CONN
    import psycopg

    with _LOCK:
        for attempt in (1, 2):
            try:
                if _CONN is None or _CONN.closed or _CONN.broken:
                    _CONN = _connect()
                with _CONN.transaction():
                    yield _CONN.cursor()
                return
            except psycopg.OperationalError as e:
                _CONN = None
                if attempt == 2:
                    log.error("database unavailable: %s", type(e).__name__)
                    raise DBError("The database is not reachable. Please try again in a moment.") from e
            except psycopg.Error as e:
                log.error("database error: %s: %s", type(e).__name__, str(e).splitlines()[0][:200])
                raise DBError("The change could not be saved. Please try again.") from e


# ------------------------------------------------------------------ helpers
def _date_str(value) -> str:
    """Seed dates are stored as midnight-UTC timestamps; show them as plain dates like the CSV did."""
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0, 0) and value.utcoffset() in (None, dt.timedelta(0)):
            return value.date().isoformat()
        return value.isoformat()
    return str(value or "")


def _ts(value: Optional[str]):
    return dt.datetime.fromisoformat(value) if value else None


EXTRA_TABLES = """
CREATE TABLE IF NOT EXISTS portal_accounts (
    email          text PRIMARY KEY,
    name           text NOT NULL,
    role           text NOT NULL CHECK (role IN ('Student','Department')),
    password_hash  text NOT NULL,
    student_id     text REFERENCES students,
    department     text,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id     text PRIMARY KEY,
    student_id        text NOT NULL REFERENCES students,
    school_code       text NOT NULL REFERENCES schools,
    school_student_id text,                     -- the Student ID printed on the transcript (previous school's id)
    sha256            text NOT NULL,            -- of the PDF: the same file uploaded again is a duplicate
    blob_url          text,                     -- archived original, <container>/<blob>
    course_count      integer NOT NULL,
    uploaded_by       text,
    uploaded_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS transcripts_student_school ON transcripts (student_id, school_code, uploaded_at);
CREATE TABLE IF NOT EXISTS notification_reads (
    student_id  text PRIMARY KEY REFERENCES students,
    seen_at     timestamptz NOT NULL            -- the student read every in-app notification up to this time
);
-- Hackathon workbook "Course Match" notes (seed/workbook_notes.csv): staff reference, never an AI or rules input.
CREATE TABLE IF NOT EXISTS workbook_notes (
    ext_id       text NOT NULL REFERENCES external_courses ON DELETE CASCADE,
    bu_course    text NOT NULL,                 -- the workbook row (BU course) the note belongs to
    match_level  text,
    note         text NOT NULL,
    PRIMARY KEY (ext_id, bu_course)
);
"""


def ensure_schema() -> None:
    """Base tables come from backend/db/schema.sql; create them when the schema is empty, then add the portal table."""
    with tx() as cur:
        cur.execute("select to_regclass(%s)", (f"{schema()}.students",))
        if cur.fetchone()[0] is None:
            from .store import REPO_ROOT
            with open(os.path.join(REPO_ROOT, "backend", "db", "schema.sql"), encoding="utf-8") as f:
                cur.execute(f.read())
            log.info("created the TransferIQ tables from schema.sql")
        cur.execute(EXTRA_TABLES)
        # Students registered before registration stored their email: take it from their sign-in account.
        cur.execute("update students s set email = a.email from portal_accounts a "
                    "where a.student_id = s.student_id and s.email is null")


# ------------------------------------------------------------------ load
def is_empty() -> bool:
    with tx() as cur:
        cur.execute("select count(*) from students")
        return cur.fetchone()[0] == 0


def load_store(s) -> None:
    """Fill Store s (already holding rules and reason codes) from the database."""
    from .store import (BUCourse, Decision, ExtCourse, School, Student, SyllabusRecord, SYNTH_DIR, TranscriptLine,
                        TranscriptRecord)

    with tx() as cur:
        cur.execute("select bu_code, dept, title, program, requirement_type, level, credits, residency_rule, "
                    "description, learning_outcomes, topics from bu_courses order by bu_code")
        for r in cur.fetchall():
            s.bu_courses[r[0]] = BUCourse(r[0], r[1], r[2], r[3], r[4], int(r[5]), float(r[6]), r[7], r[8],
                                          list(r[9]), list(r[10]))
        cur.execute("select school_code, name, calendar, accreditation from schools")
        for r in cur.fetchall():
            s.schools[r[0]] = School(*r)
        cur.execute("select ext_id, school_code, course_code, title, credits, calendar, coalesce(program_area,''), "
                    "course_type, coalesce(level,100), coalesce(description,''), learning_outcomes, topics, "
                    "coalesce(elective_code,'') from external_courses order by ext_id")
        for r in cur.fetchall():
            s.ext_courses[r[0]] = ExtCourse(r[0], r[1], r[2], r[3], float(r[4]), r[5], r[6], r[7], int(r[8]), r[9],
                                            list(r[10]), list(r[11]), r[12])
        cur.execute("select ext_id, gt_counterpart, gt_overlap, gt_tier from external_courses_gt")
        for r in cur.fetchall():   # eval only, never handed to the matcher
            s.ground_truth[r[0]] = dict(gt_counterpart=r[1] or "", gt_overlap="" if r[2] is None else str(float(r[2])),
                                        gt_tier=r[3] or "")
        cur.execute("select decision_id, student_id from decision_scope")
        scope: dict[str, list[str]] = {}
        for did, sid in cur.fetchall():
            scope.setdefault(did, []).append(sid)
        cur.execute("select decision_id, ext_id, decision, bu_course, reason_code, reusable, catalog_year, decided_by, "
                    "decision_date, split, note, overlap_pct, ai_suggestion, ai_agreed from decisions "
                    "order by decision_date, decision_id")
        for r in cur.fetchall():
            d = Decision(decision_id=r[0], ext_id=r[1], decision=r[2], bu_course=r[3], reason_code=r[4],
                         reusable=bool(r[5]), catalog_year=r[6], decided_by=r[7], decision_date=_date_str(r[8]),
                         split=r[9], note=r[10] or "", overlap_pct=r[11], ai_suggestion=r[12], ai_agreed=r[13],
                         applies_to=sorted(scope[r[0]]) if r[0] in scope else None)
            (s.holdout_decisions if d.split == "holdout" else s.decisions).append(d)
        s.decisions.sort(key=lambda d: d.decision_id)
        s.holdout_decisions.sort(key=lambda d: d.decision_id)
        cur.execute(f"select {', '.join(STUDENT_COLS)} from students order by student_id")
        for r in cur.fetchall():
            s.students[r[0]] = Student(**{k: v or "" for k, v in zip(STUDENT_COLS, r)})
        cur.execute("select student_id, school_code, term, ext_id, course_code, coalesce(title,''), credits, calendar, "
                    "grade from transcript_lines order by student_id, seq")
        s.lines = [TranscriptLine(r[0], r[1], r[2], r[3], r[4], r[5], float(r[6]), r[7], r[8]) for r in cur.fetchall()]
        cur.execute("select transcript_id, student_id, school_code, coalesce(school_student_id,''), sha256, "
                    "coalesce(blob_url,''), course_count, coalesce(uploaded_by,''), uploaded_at from transcripts "
                    "order by uploaded_at, transcript_id")
        s.transcripts = [TranscriptRecord(*r[:8], uploaded_at=r[8].isoformat()) for r in cur.fetchall()]
        cur.execute("select student_id, seen_at from notification_reads")
        s.notification_seen = {sid: at.isoformat() for sid, at in cur.fetchall()}
        cur.execute("select ext_id, state, blob_url, source_file, extracted_text, injection_detected, "
                    "coalesce(seed_state,''), received_at from syllabi")
        for ext_id, state, blob_url, source_file, text, inj, seed_state, received_at in cur.fetchall():
            state = "complete" if state == "complete-injection" else state
            # blob_url = uploaded copy (<container>/<name>); source_file = bundled seed PDF relative to data/synthetic
            path = blob_url or (os.path.join(SYNTH_DIR, source_file) if source_file else "")
            # received_at is only set by an upload through the app (seed rows: NULL) -> upload-once rule
            s.syllabi[ext_id] = SyllabusRecord(ext_id=ext_id, state=state, file=path if state != "missing" else "",
                                               text=text or "", injection_detected=bool(inj), seed_state=seed_state,
                                               uploaded_at=received_at.isoformat() if received_at else "")
        cur.execute("select ext_id, bu_course, coalesce(match_level,''), note from workbook_notes "
                    "order by ext_id, bu_course")
        s.workbook_notes = {}
        for ext_id, bu, level, note in cur.fetchall():
            s.workbook_notes.setdefault(ext_id, []).append(dict(bu_course=bu, match_level=level, note=note))
        cur.execute("select student_id, ext_id, term, decision_id, posted_at, actor_role from postings")
        for sid, ext_id, term, did, posted_at, actor in cur.fetchall():
            s.postings[(sid, ext_id, term)] = dict(decision_id=did, posted_at=posted_at.isoformat(), actor_role=actor)
        cur.execute("select actor_role, action, ext_id, before, after, at from audit_log order by id")
        s.audit_log = [dict(actor_role=r[0], action=r[1], ext_id=r[2], before=r[3], after=r[4], at=r[5].isoformat())
                       for r in cur.fetchall()]
    log.info("loaded store from PostgreSQL: %d students, %d lines, %d decisions, %d postings",
             len(s.students), len(s.lines), len(s.decisions) + len(s.holdout_decisions), len(s.postings))


# ------------------------------------------------------------------ writes (call BEFORE changing the in-memory store)
# One column list for every students read and insert, so a Student field cannot be dropped on one side only
# (bu_school used to be stored as NULL that way).
STUDENT_COLS = ("student_id", "name", "intended_major", "bu_start_term", "bu_school", "email", "phone", "address",
                "previous_school")
_INSERT_STUDENT = (f"insert into students ({', '.join(STUDENT_COLS)}) values ({','.join(['%s'] * len(STUDENT_COLS))})")


def _student_row(st):
    return tuple(getattr(st, k) or None for k in STUDENT_COLS)   # "" -> NULL for the optional profile fields


def _ext_course_row(c):
    return (c.ext_id, c.school_code, c.course_code, c.title, c.credits, c.calendar, c.course_type, c.program_area,
            c.level, c.description, c.learning_outcomes, c.topics, c.elective_code or None)


_UPSERT_EXT = ("insert into external_courses (ext_id, school_code, course_code, title, credits, calendar, course_type, "
               "program_area, level, description, learning_outcomes, topics, elective_code) "
               "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict (ext_id) do nothing")


def save_transcript(student_id: str, new_courses: list, student_lines: list, record=None) -> None:
    """New external courses from an upload + the student's full, ordered transcript lines (replaces theirs), and
    the upload's TranscriptRecord, in one transaction."""
    with tx() as cur:
        if record is not None:
            cur.execute("insert into transcripts (transcript_id, student_id, school_code, school_student_id, sha256, "
                        "blob_url, course_count, uploaded_by, uploaded_at) values (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (record.transcript_id, record.student_id, record.school_code, record.school_student_id or None,
                         record.sha256, record.blob_url or None, record.course_count, record.uploaded_by or None,
                         _ts(record.uploaded_at)))
        for c in new_courses:
            cur.execute(_UPSERT_EXT, _ext_course_row(c))
        cur.execute("delete from transcript_lines where student_id = %s", (student_id,))
        for seq, ln in enumerate(student_lines):
            cur.execute("insert into transcript_lines (student_id, ext_id, term, seq, school_code, course_code, title, "
                        "credits, calendar, grade) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (ln.student_id, ln.ext_id, ln.term, seq, ln.school_code, ln.course_code, ln.title, ln.credits,
                         ln.calendar, ln.grade))


def save_syllabus(rec, blob_path: Optional[str], missing_sections: list[str]) -> None:
    with tx() as cur:
        cur.execute("insert into syllabi (ext_id, state, blob_url, missing_sections, injection_detected, received_at, "
                    "source_file, seed_state, extracted_text) values (%s,%s,%s,%s,%s,now(),%s,%s,%s) "
                    "on conflict (ext_id) do update set state = excluded.state, blob_url = excluded.blob_url, "
                    "missing_sections = excluded.missing_sections, injection_detected = excluded.injection_detected, "
                    "received_at = excluded.received_at, extracted_text = excluded.extracted_text",
                    (rec.ext_id, rec.state, blob_path, missing_sections, rec.injection_detected, None,
                     rec.seed_state or None, rec.text))


def save_decisions(decisions: list) -> None:
    with tx() as cur:
        for d in decisions:
            cur.execute("insert into decisions (decision_id, ext_id, decision, bu_course, reason_code, reusable, split, "
                        "catalog_year, decided_by, decision_date, ai_suggestion, ai_agreed, note, overlap_pct) "
                        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (d.decision_id, d.ext_id, d.decision, d.bu_course, d.reason_code, d.reusable, d.split,
                         d.catalog_year, d.decided_by, _ts(d.decision_date), d.ai_suggestion, d.ai_agreed,
                         d.note or "", d.overlap_pct))
            for sid in d.applies_to or []:
                cur.execute("insert into decision_scope (decision_id, student_id) values (%s,%s)", (d.decision_id, sid))


def save_postings(items: list[tuple[tuple[str, str, str], dict]]) -> None:
    with tx() as cur:
        for (sid, ext_id, term), p in items:
            cur.execute("insert into postings (student_id, ext_id, term, decision_id, posted_at, actor_role) "
                        "values (%s,%s,%s,%s,%s,%s) on conflict (student_id, ext_id, term) do update set "
                        "decision_id = excluded.decision_id, posted_at = excluded.posted_at, "
                        "actor_role = excluded.actor_role",
                        (sid, ext_id, term, p["decision_id"], _ts(p["posted_at"]), p["actor_role"]))


def save_notification_seen(student_id: str, seen_at: str) -> None:
    with tx() as cur:
        cur.execute("insert into notification_reads (student_id, seen_at) values (%s, %s) on conflict (student_id) "
                    "do update set seen_at = excluded.seen_at", (student_id, _ts(seen_at)))


def save_audit(entry: dict) -> None:
    """Best-effort: an audit write that fails is logged, the request itself has already succeeded."""
    from psycopg.types.json import Jsonb
    try:
        with tx() as cur:
            cur.execute("insert into audit_log (actor_role, action, ext_id, before, after, at) values (%s,%s,%s,%s,%s,%s)",
                        (entry["actor_role"], entry["action"], entry.get("ext_id"), Jsonb(entry.get("before")),
                         Jsonb(entry.get("after")), _ts(entry["at"])))
    except DBError:
        log.error("audit entry not stored: %s %s", entry.get("action"), entry.get("ext_id"))


# ------------------------------------------------------------------ portal accounts
def load_accounts() -> list[dict]:
    with tx() as cur:
        cur.execute("select email, name, role, password_hash, student_id, department from portal_accounts")
        cols = ("email", "name", "role", "password_hash", "student_id", "department")
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def save_registration(acct, student=None) -> None:
    """A registered account (and, for a student, their new student record) in one transaction."""
    with tx() as cur:
        if student is not None:
            cur.execute(_INSERT_STUDENT, _student_row(student))
        cur.execute("insert into portal_accounts (email, name, role, password_hash, student_id, department) "
                    "values (%s,%s,%s,%s,%s,%s)",
                    (acct.email, acct.name, acct.role, acct.password_hash, acct.student_id, acct.department))


# ------------------------------------------------------------------ seed / demo reset
def _insert_workbook_notes(cur, notes: dict[str, list[dict]], known_ext_ids: set[str]) -> None:
    for ext_id, rows in notes.items():
        if ext_id not in known_ext_ids:          # a workbook course missing from the catalogue: nothing to attach to
            continue
        for n in rows:
            cur.execute("insert into workbook_notes (ext_id, bu_course, match_level, note) values (%s,%s,%s,%s) "
                        "on conflict (ext_id, bu_course) do nothing",
                        (ext_id, n["bu_course"], n.get("match_level") or None, n["note"]))


def seed_workbook_notes_if_empty(notes: dict[str, list[dict]]) -> None:
    """A database seeded before the table existed is not reseeded (it is not empty): copy the notes in once."""
    with tx() as cur:
        cur.execute("select exists (select 1 from workbook_notes)")
        if cur.fetchone()[0]:
            return
        cur.execute("select ext_id from external_courses")
        _insert_workbook_notes(cur, notes, {r[0] for r in cur.fetchall()})
    log.info("workbook notes copied into the database")


def reseed(seed) -> None:
    """Make the database match the seed Store `seed` (CSV state). Runtime data (runtime decisions, postings, audit,
    uploaded lines, uploaded syllabi, courses created by uploads) is removed; registered students and portal accounts
    are kept. On an empty database this is the initial seed."""
    from psycopg.types.json import Jsonb  # noqa: F401  (import check: psycopg present)

    with tx() as cur:
        cur.execute("delete from postings")
        cur.execute("delete from audit_log")
        cur.execute("delete from decision_scope")
        cur.execute("delete from decisions")
        cur.execute("delete from transcripts")
        cur.execute("delete from transcript_lines")
        cur.execute("delete from syllabi")
        cur.execute("delete from external_courses_gt")
        for b in seed.bu_courses.values():
            cur.execute("insert into bu_courses (bu_code, dept, title, program, requirement_type, level, credits, "
                        "residency_rule, description, learning_outcomes, topics) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "on conflict (bu_code) do nothing",
                        (b.bu_code, b.dept, b.title, b.program, b.requirement_type, b.level, b.credits,
                         b.residency_rule, b.description, b.learning_outcomes, b.topics))
        for sc in seed.schools.values():
            cur.execute("insert into schools (school_code, name, calendar, accreditation) values (%s,%s,%s,%s) "
                        "on conflict (school_code) do nothing", (sc.school_code, sc.name, sc.calendar, sc.accreditation))
        cur.execute("delete from external_courses where not (ext_id = any(%s))", (list(seed.ext_courses),))
        for c in seed.ext_courses.values():
            cur.execute(_UPSERT_EXT, _ext_course_row(c))
        for ext_id, gt in seed.ground_truth.items():
            cur.execute("insert into external_courses_gt (ext_id, gt_counterpart, gt_overlap, gt_tier) "
                        "values (%s,%s,%s,%s)", (ext_id, gt.get("gt_counterpart") or None,
                                                 float(gt["gt_overlap"]) if gt.get("gt_overlap") else None,
                                                 gt.get("gt_tier") or None))
        for st in seed.students.values():
            cur.execute(_INSERT_STUDENT + " on conflict (student_id) do update set "
                        + ", ".join(f"{k} = excluded.{k}" for k in STUDENT_COLS[1:]), _student_row(st))
        for d in seed.decisions + seed.holdout_decisions:
            cur.execute("insert into decisions (decision_id, ext_id, decision, bu_course, reason_code, reusable, split, "
                        "catalog_year, decided_by, decision_date, note, overlap_pct) "
                        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (d.decision_id, d.ext_id, d.decision, d.bu_course, d.reason_code, d.reusable, d.split,
                         d.catalog_year, d.decided_by, _ts(d.decision_date), d.note or "", d.overlap_pct))
        per_student: dict[str, int] = {}
        for ln in seed.lines:
            seq = per_student.get(ln.student_id, 0)
            per_student[ln.student_id] = seq + 1
            cur.execute("insert into transcript_lines (student_id, ext_id, term, seq, school_code, course_code, title, "
                        "credits, calendar, grade) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (ln.student_id, ln.ext_id, ln.term, seq, ln.school_code, ln.course_code, ln.title, ln.credits,
                         ln.calendar, ln.grade))
        cur.execute("delete from workbook_notes")
        _insert_workbook_notes(cur, seed.workbook_notes, set(seed.ext_courses))
        from .store import SYNTH_DIR, syllabus_file_for
        for rec in seed.syllabi.values():
            seed_file = syllabus_file_for(rec.ext_id)
            src = os.path.relpath(seed_file, SYNTH_DIR).replace(os.sep, "/") if seed_file else None
            cur.execute("insert into syllabi (ext_id, state, missing_sections, injection_detected, source_file, "
                        "seed_state, extracted_text) values (%s,%s,%s,%s,%s,%s,%s)",
                        (rec.ext_id, rec.state, [], rec.injection_detected, src, rec.seed_state or None, rec.text))
    log.info("database reseeded from the seed files")
