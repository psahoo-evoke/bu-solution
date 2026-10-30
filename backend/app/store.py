"""In-memory repository the rules engine and matcher work on.

Source of truth:
- POSTGRES_HOST set: PostgreSQL (backend/db/schema.sql, app/db.py). The store is loaded from the tables at start-up
  (an empty database is seeded from the CSVs first) and every change is written to the database before memory.
- Otherwise: the synthetic seed CSVs (data/synthetic/seed/), in memory only (tests, local runs).
`reset()` restores the seeded state (in the database too).

Data-hygiene guarantees (AGENTS.md, ADR 0002):
- `gt_*` columns of external_courses.csv are split off into `ground_truth` at load time. The matcher only ever
  receives `ExtCourse` objects, which have no gt fields.
- Decisions with split == holdout are kept in `holdout_decisions` and are NOT visible to the equivalency
  lookup or to any API that lists past decisions. Only the evaluation reads them.
"""
from __future__ import annotations

import csv
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEED_DIR = os.environ.get("TRANSFERIQ_SEED_DIR", os.path.join(REPO_ROOT, "data", "synthetic", "seed"))
SYNTH_DIR = os.path.dirname(SEED_DIR)

LIST_SEP = " | "


def _split(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def _read(name: str) -> list[dict]:
    with open(os.path.join(SEED_DIR, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@dataclass
class BUCourse:
    bu_code: str
    dept: str
    title: str
    program: str
    requirement_type: str
    level: int
    credits: float
    residency_rule: str
    description: str
    learning_outcomes: list[str]
    topics: list[str]


@dataclass
class School:
    school_code: str
    name: str
    calendar: str
    accreditation: str

    @property
    def accredited(self) -> bool:
        # R01: "Not regionally accredited (...)" -> ineligible
        return not self.accreditation.lower().startswith("not")


@dataclass
class ExtCourse:
    """External course as the app and the matcher see it. Deliberately has NO gt_* fields."""
    ext_id: str
    school_code: str
    course_code: str
    title: str
    credits: float
    calendar: str
    program_area: str
    course_type: str
    level: int
    description: str
    learning_outcomes: list[str]
    topics: list[str]
    elective_code: str = ""


@dataclass
class Decision:
    decision_id: str
    ext_id: str
    decision: str            # Equivalent | Elective | No credit
    bu_course: str
    reason_code: str
    reusable: bool
    catalog_year: str
    decided_by: str
    decision_date: str       # ISO date or datetime; sorts lexically
    split: str = "train"     # train | holdout | runtime
    note: str = ""
    overlap_pct: Optional[int] = None
    ai_suggestion: Optional[str] = None
    ai_agreed: Optional[bool] = None
    applies_to: Optional[list[str]] = None   # non-reusable runtime decision: only these students

    def to_api(self) -> dict:
        return dict(decision_id=self.decision_id, ext_id=self.ext_id, decision=self.decision, bu_course=self.bu_course,
                    reason_code=self.reason_code, reusable=self.reusable, evaluator=self.decided_by,
                    catalog_year=self.catalog_year, note=self.note, decided_at=self.decision_date,
                    ai_suggestion=self.ai_suggestion, ai_agreed=self.ai_agreed)


@dataclass
class Student:
    student_id: str
    name: str
    intended_major: str
    bu_start_term: str
    bu_school: str = ""
    # Contact fields (synthetic: example.edu, 555-01xx, invented streets). Personal data: shown to people through the
    # API, never sent to an AI service (ADR 0004); the matcher only ever receives ExtCourse/BUCourse.
    email: str = ""
    phone: str = ""
    address: str = ""
    previous_school: str = ""          # schools.school_code of the latest non-summer transcript term ("" if unknown)

    def to_api(self, schools: Optional[dict[str, "School"]] = None) -> dict:
        prev = (schools or {}).get(self.previous_school)
        return dict(student_id=self.student_id, name=self.name, intended_major=self.intended_major,
                    bu_school=self.bu_school, bu_start_term=self.bu_start_term, email=self.email, phone=self.phone,
                    address=self.address, previous_school=self.previous_school or None,
                    previous_school_name=prev.name if prev else None)


@dataclass
class TranscriptLine:
    student_id: str
    school_code: str
    term: str
    ext_id: str
    course_code: str
    title: str
    credits: float
    calendar: str
    grade: str


@dataclass
class TranscriptRecord:
    """One accepted transcript upload. The latest record per (student, school) is the source of that school's lines."""
    transcript_id: str
    student_id: str                    # portal / BU student id the transcript was uploaded for
    school_code: str
    school_student_id: str             # the "Student ID" printed on the transcript (the previous school's id; "" if none)
    sha256: str                        # of the PDF bytes: the same file again is a duplicate
    blob_url: str                      # archived original (<container>/<blob>), "" when the archive is off
    course_count: int
    uploaded_by: str                   # portal email, or the demo role
    uploaded_at: str                   # ISO 8601 UTC

    def to_api(self) -> dict:
        return dict(transcript_id=self.transcript_id, school_code=self.school_code,
                    school_student_id=self.school_student_id or None, course_count=self.course_count,
                    uploaded_by=self.uploaded_by, uploaded_at=self.uploaded_at)


@dataclass
class SyllabusRecord:
    ext_id: str
    state: str               # complete | incomplete | missing (complete-late is stored as missing until uploaded)
    file: str = ""
    text: str = ""
    injection_detected: bool = False
    seed_state: str = ""
    uploaded_at: str = ""    # set when someone uploaded it through the app; a syllabus is uploaded only once


@dataclass
class Store:
    bu_courses: dict[str, BUCourse] = field(default_factory=dict)
    schools: dict[str, School] = field(default_factory=dict)
    ext_courses: dict[str, ExtCourse] = field(default_factory=dict)
    ground_truth: dict[str, dict] = field(default_factory=dict)      # eval only, never passed to the matcher
    decisions: list[Decision] = field(default_factory=list)          # train + runtime (visible to the app)
    holdout_decisions: list[Decision] = field(default_factory=list)  # eval only
    students: dict[str, Student] = field(default_factory=dict)
    lines: list[TranscriptLine] = field(default_factory=list)
    transcripts: list[TranscriptRecord] = field(default_factory=list)   # uploads, oldest first (seed: none)
    notification_seen: dict[str, str] = field(default_factory=dict)     # student_id -> read up to (ISO time)
    syllabi: dict[str, SyllabusRecord] = field(default_factory=dict)
    rules: list[dict] = field(default_factory=list)
    reason_codes: dict[str, dict] = field(default_factory=dict)
    # Hackathon workbook "Course Match" notes, ext_id -> [{bu_course, match_level, note}]. Staff reference only:
    # never passed to the matcher, never shown to students.
    workbook_notes: dict[str, list[dict]] = field(default_factory=dict)
    audit_log: list[dict] = field(default_factory=list)
    # Registrar posting step: (student_id, ext_id, term) -> {decision_id, posted_at, actor_role}
    postings: dict[tuple[str, str, str], dict] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    # ---------------------------------------------------------------- lookups
    def visible_decisions(self, ext_id: str) -> list[Decision]:
        """Decisions the app may use for ext_id. Holdout decisions are never included."""
        return [d for d in self.decisions if d.ext_id == ext_id and d.split != "holdout"]

    def lines_for(self, student_id: str) -> list[TranscriptLine]:
        return [ln for ln in self.lines if ln.student_id == student_id]

    def latest_transcript(self, student_id: str, school_code: str) -> Optional[TranscriptRecord]:
        return next((t for t in reversed(self.transcripts)
                     if t.student_id == student_id and t.school_code == school_code), None)

    def syllabus_state(self, ext_id: str) -> str:
        rec = self.syllabi.get(ext_id)
        return rec.state if rec else "missing"

    def next_decision_id(self) -> str:
        n = len(self.decisions) + len(self.holdout_decisions) + 1
        return f"D-{n:04d}"


_SYLLABUS_TEXT_CACHE: dict[str, str] = {}


def _syllabus_text(path: str) -> str:
    if path not in _SYLLABUS_TEXT_CACHE:
        from .ingest import pdf_text
        try:
            _SYLLABUS_TEXT_CACHE[path] = pdf_text(path)
        except Exception:  # pragma: no cover - missing/broken file must not stop the API
            _SYLLABUS_TEXT_CACHE[path] = ""
    return _SYLLABUS_TEXT_CACHE[path]


def load() -> Store:
    s = Store()
    for r in _read("bu_courses.csv"):
        s.bu_courses[r["bu_code"]] = BUCourse(
            bu_code=r["bu_code"], dept=r["dept"], title=r["title"], program=r["program"],
            requirement_type=r["requirement_type"], level=int(r["level"]), credits=float(r["credits"]),
            residency_rule=r["residency_rule"], description=r["description"],
            learning_outcomes=_split(r["learning_outcomes"]), topics=_split(r["topics"]))
    for r in _read("schools.csv"):
        s.schools[r["school_code"]] = School(r["school_code"], r["name"], r["calendar"], r["accreditation"])
    for r in _read("external_courses.csv"):
        # gt_* columns are split off here and never stored on ExtCourse.
        s.ground_truth[r["ext_id"]] = {k: v for k, v in r.items() if k.startswith("gt_")}
        s.ext_courses[r["ext_id"]] = ExtCourse(
            ext_id=r["ext_id"], school_code=r["school_code"], course_code=r["course_code"], title=r["title"],
            credits=float(r["credits"]), calendar=r["calendar"], program_area=r["program_area"],
            course_type=r["course_type"], level=int(float(r["level"])), description=r["description"],
            learning_outcomes=_split(r["learning_outcomes"]), topics=_split(r["topics"]),
            elective_code=r.get("elective_code") or "")
    for r in _read("past_decisions.csv"):
        d = Decision(
            decision_id=r["decision_id"], ext_id=r["ext_id"], decision=r["decision"], bu_course=r["bu_course"],
            reason_code=r["reason_code"], reusable=r["reusable"].strip().lower() == "yes",
            catalog_year=r["catalog_year"], decided_by=r["decided_by"], decision_date=r["decision_date"],
            split=r["split"], note=r.get("notes", ""),
            overlap_pct=int(float(r["overlap_pct"])) if r.get("overlap_pct") else None)
        (s.holdout_decisions if d.split == "holdout" else s.decisions).append(d)
    for r in _read("students.csv"):
        s.students[r["student_id"]] = Student(
            r["student_id"], r["name"], r["intended_major"], r["bu_start_term"], bu_school=r.get("bu_school", ""),
            email=r.get("email", ""), phone=r.get("phone", ""), address=r.get("address", ""),
            previous_school=r.get("previous_school", ""))
    # Seeded transcript lines: only the INPUT columns of transcript_lines_expected.csv are loaded.
    # The expected outcome columns (status, bu_course, units, ...) are test oracles, not app state.
    for r in _read("transcript_lines_expected.csv"):
        s.lines.append(TranscriptLine(r["student_id"], r["school_code"], r["term"], r["ext_id"], r["course_code"],
                                      r["title"], float(r["credits"]), r["calendar"], r["grade"]))
    for r in _read("syllabi_index.csv"):
        seed_state = r["state"]
        # complete-late: the file exists for the demo but has not been "received" yet -> missing (TS) until uploaded
        state = {"complete": "complete", "complete-injection": "complete", "incomplete": "incomplete"}.get(seed_state, "missing")
        path = os.path.join(SYNTH_DIR, r["file"])
        rec = SyllabusRecord(ext_id=r["ext_id"], state=state, file=path if state != "missing" else "", seed_state=seed_state)
        if state != "missing":
            from .safety import detect_injection
            rec.text = _syllabus_text(path)
            rec.injection_detected = detect_injection(rec.text)
        s.syllabi[r["ext_id"]] = rec
    s.rules = _read("rules.csv")
    s.reason_codes = {r["reason_code"]: r for r in _read("reason_codes.csv")}
    s.workbook_notes = _workbook_notes()
    return s


def syllabus_file_for(ext_id: str) -> Optional[str]:
    """Path of the synthetic syllabus PDF for ext_id (whether or not it has been 'received')."""
    for r in _read("syllabi_index.csv"):
        if r["ext_id"] == ext_id:
            return os.path.join(SYNTH_DIR, r["file"])
    return None


def _workbook_notes() -> dict[str, list[dict]]:
    """seed/workbook_notes.csv (scripts/synthetic/extract_workbook_notes.py): the CSV store's notes and the seed for
    the workbook_notes table in PostgreSQL mode. Optional: no file, no notes."""
    try:
        rows = _read("workbook_notes.csv")
    except FileNotFoundError:
        return {}
    out: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("note", "").strip():
            out.setdefault(f"{r['school_code']}|{r['course_code']}", []).append(
                dict(bu_course=r["bu_course"], match_level=r.get("match_level", ""), note=r["note"].strip()))
    return out


def load_db() -> Store:
    """Store from PostgreSQL. Rules and reason codes are not in the schema and still come from the seed CSVs;
    workbook notes are read from the workbook_notes table (seeded from the CSV)."""
    from . import db
    db.ensure_schema()
    if db.is_empty():
        db.reseed(load())
    else:
        db.seed_workbook_notes_if_empty(_workbook_notes())
    s = Store()
    s.rules = _read("rules.csv")
    s.reason_codes = {r["reason_code"]: r for r in _read("reason_codes.csv")}
    db.load_store(s)
    return s


def _initial() -> Store:
    from . import db
    return load_db() if db.enabled() else load()


STORE: Store = _initial()


def reset() -> Store:
    global STORE
    from . import db
    if db.enabled():
        db.reseed(load())       # seed rows back; registered students and accounts are kept
        new = load_db()
    else:
        new = load()
    with STORE.lock:
        STORE.__dict__.update({k: v for k, v in new.__dict__.items() if k != "lock"})
    return STORE
