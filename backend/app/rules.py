"""Deterministic credit rules engine (ADR 0001). ALL credit math lives here.

Every rule cites its ID from data/synthetic/seed/rules.csv. The semantics mirror the reference implementation that
produced transcript_lines_expected.csv (scripts/synthetic/build_data_v2.py: evaluate / lookup / course_decision).

The engine never reads gt_* ground truth. Where the reference used ground truth (only to word a flag on a still
pending line), this engine uses the evaluator decision's BU course, or the matcher's top candidate passed in as a
hint (`ai_hint`). Hints never change units, status or codes - only advisory flags and the plain-words AI tier.
"""
from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass
from typing import Callable, Optional

from .store import Decision, ExtCourse, Store, Student, TranscriptLine

CAP_UNITS = 68.0                                      # R17
GRADE_OK = {"A", "A-", "B+", "B", "B-", "C+", "C"}    # R06: minimum grade C
PASS_FAIL = {"P", "NP", "S", "U"}                     # R05
INELIGIBLE_TYPES = {                                  # R02 / R03
    "Remedial": "NC-REMEDIAL", "Physical education": "NC-PE", "Vocational": "NC-VOC", "ROTC": "NC-ROTC",
    "Internship": "NC-INTERNSHIP", "Research": "NC-RESEARCH",
}
NO_CREDIT_CODE = "TFRGEN NOCRDT"                      # R24
SEASON = {"Winter": 0, "Spring": 1, "Summer": 2, "Fall": 3}

# AI hint: ext_id -> (tier label like "Evaluator decides (50-79%)", top candidate BU code) or None
AiHint = Callable[[str], Optional[tuple[str, str]]]


# ------------------------------------------------------------------ small pure helpers
def convert_units(credits: float, calendar: str) -> float:
    """R08: quarter credits x 2/3 rounded to 2 decimals, course by course. R09: units are the student's units
    (converted), never the BU course's credits."""
    return round(credits * 2 / 3, 2) if calendar == "Quarter" else float(credits)


def elective_code(dept: str, level: int) -> str:
    """R24: elective credit -> BU code ending in TR (1TR below 200 level, 2TR at 200+)."""
    return f"CAS {dept} {1 if level < 200 else 2}TR"


def term_key(term: str) -> tuple[int, int]:
    season, year = term.split()
    return int(year), SEASON.get(season, 0)


def term_year(term: str) -> int:
    return int(term.split()[1])


def tier_label(overlap_fraction: float) -> str:
    """R20 tiers, reference wording."""
    if overlap_fraction >= 0.8:
        return "Equivalent (>=80%)"
    if overlap_fraction >= 0.5:
        return "Evaluator decides (50-79%)"
    return "Elective (<50%)"


def eligibility(line: TranscriptLine, course: Optional[ExtCourse], store: Store) -> Optional[str]:
    """R01-R06 in reference order. Returns a no-credit reason code or None if eligible."""
    school = store.schools.get(line.school_code)
    return no_credit_reason(school is None or school.accredited, course.course_type if course else "Academic",
                            line.credits, line.grade)


def no_credit_reason(accredited: bool, course_type: str, credits: Optional[float], grade: Optional[str]) -> Optional[str]:
    """R01-R06 on plain values, shared by the evaluation and the public credit check. grade=None means the grade
    is not known yet (public check): R05/R06 are then not applied."""
    if not accredited:                                         # R01
        return "NC-ACCRED"
    if course_type in INELIGIBLE_TYPES:                        # R02 / R03
        return INELIGIBLE_TYPES[course_type]
    if credits == 1:                                           # R04
        return "NC-ONECREDIT"
    if grade is None:
        return None
    if grade in PASS_FAIL:                                     # R05
        return "NC-PASSFAIL"
    if grade not in GRADE_OK:                                  # R06 (C- and below; also D, F, W ...)
        return "NC-GRADE"
    return None


def lookup(store: Store, ext_id: str, student_id: str) -> tuple[Optional[Decision], str]:
    """R10 / R11: equivalency table lookup. Holdout decisions are never visible (store.visible_decisions).
    Only reusable decisions apply to everyone; a non-reusable runtime decision applies only to the students it
    was made for. Newest (catalog_year, decision_date) wins; same-catalog-year disagreement is flagged."""
    ds = [d for d in store.visible_decisions(ext_id)
          if d.reusable or (d.applies_to is not None and student_id in d.applies_to)]
    if not ds:
        return None, ""
    ds.sort(key=lambda d: (d.catalog_year, d.decision_date))
    newest = ds[-1]
    if any(d.catalog_year == newest.catalog_year and d.decision != newest.decision for d in ds):   # R11 conflict
        return newest, "CONFLICT: same catalog year, different decisions -> flag for department"
    if len({d.decision for d in ds}) > 1:                                                            # R11 superseded
        return newest, "Older conflicting decision superseded by newest catalog year"
    return newest, ""


def lookup_public(store: Store, ext_id: str) -> tuple[Optional[Decision], str]:
    """R10 / R11 for the public credit check: reusable, non-holdout decisions only. Filtered explicitly here so a
    change to lookup() can never widen what an anonymous caller sees."""
    dec, flag = lookup(store, ext_id, student_id="")
    if dec is not None and not dec.reusable:
        return None, ""
    return dec, flag


# ------------------------------------------------------------------ plain words (R23 / status view)
# Syllabus reminders (app/main.py send_due_reminders): every N days after the request, at most M reminders.
SYLLABUS_REMINDER_DAYS = float(os.environ.get("TRANSFERIQ_SYLLABUS_REMINDER_DAYS", "2") or 0)
SYLLABUS_REMINDER_MAX = int(os.environ.get("TRANSFERIQ_SYLLABUS_REMINDER_MAX", "7") or 0)
_EVERY = f"{SYLLABUS_REMINDER_DAYS:g} day{'' if SYLLABUS_REMINDER_DAYS == 1 else 's'}"
_REMINDERS = f" We email a reminder every {_EVERY} until it arrives." if SYLLABUS_REMINDER_DAYS > 0 else ""
STATE_TEXT = {
    "matched": ("Matched - existing BU equivalency", "Nothing to do: this credit will post."),
    "approved": ("Approved \u2013 awaiting posting", "Nothing to do: the Registrar will post this credit."),
    "posted": ("Posted \u2013 credit secured", "Nothing to do: this credit is on your BU record."),
    "posted_no_credit": ("Not transferable", "No action needed."),
    "maybe_review": ("Under review - syllabus on file", "An evaluator is comparing your syllabus with BU courses."),
    "maybe_ts": ("Syllabus needed", "Upload the course syllabus." + _REMINDERS),
    "maybe_tm": ("More materials needed",
                 "Upload a syllabus that includes learning outcomes and a weekly schedule." + _REMINDERS),
    "pending_age": ("Under review - course is 5+ years old", "An evaluator will review this older course before any credit."),
}
# Approved-but-not-posted shows TP to the student until the Registrar posts it (sponsor process; contract v0.3.0).
STATUS_CODE = {"matched": "T", "approved": "TP", "posted": "T", "posted_no_credit": "TX", "maybe_review": "TP",
               "maybe_ts": "TS", "maybe_tm": "TM", "pending_age": "TP"}


@dataclass
class _Res:
    state: str = ""
    ref_status: str = ""
    bu_course: str = ""
    units: float = 0.0
    bu_grade: str = ""
    reason_code: str = ""


def evaluate_student(store: Store, student: Student, ai_hint: Optional[AiHint] = None,
                     today: Optional[_dt.date] = None) -> list[dict]:
    """Evaluate every transcript line of a student in transcript order. Returns one dict per line."""
    start_season, start_year_s = student.bu_start_term.split()
    start_year = int(start_year_s)
    start_key = (start_year, SEASON.get(start_season, 3))
    out: list[dict] = []
    used_bu: set[str] = set()
    econ_after_count = 0

    for ln in store.lines_for(student.student_id):
        course = store.ext_courses.get(ln.ext_id)
        u = convert_units(ln.credits, ln.calendar)            # R08 / R09
        level = course.level if course else 100
        r = _Res()
        flags: list[str] = []
        applied: Optional[Decision] = None

        nc = eligibility(ln, course, store)
        if nc:                                                 # R01-R06 -> R24 no credit
            r = _Res("posted_no_credit", "Posted - no credit", NO_CREDIT_CODE, 0.0, "TX", nc)
        elif term_year(ln.term) <= start_year - 5:             # R07 age (term_year <= 2021 for a Fall 2026 start)
            r = _Res("pending_age", "Pending - age review (5+ years old)", "", 0.0, "", "RV-AGE")
        else:
            dec, flag = lookup(store, ln.ext_id, student.student_id)     # R10 / R11
            if flag:
                flags.append(flag)
            if dec and dec.decision == "No credit":
                r = _Res("posted_no_credit", "Posted - no credit", NO_CREDIT_CODE, 0.0, "TX", dec.reason_code)
                applied = dec
            elif dec:
                applied = dec
                code, reason = dec.bu_course, dec.reason_code
                bu = store.bu_courses.get(code)
                dept = code.split()[1] if len(code.split()) > 1 else "TFRGEN"
                if dec.decision == "Equivalent" and bu and bu.requirement_type.startswith("Group C"):
                    code, reason = elective_code(dept, level), "EL-RESIDENCY"          # R13 CS Group C
                elif dec.decision == "Equivalent" and code in used_bu:
                    code, reason = elective_code(dept, level), "EL-DUPLICATE"          # R12 duplicate
                elif (dec.decision == "Equivalent" and bu and bu.residency_rule.startswith("Economics")
                      and student.intended_major == "Economics" and term_key(ln.term) >= start_key):
                    econ_after_count += 1                                              # R15 after matriculation
                    if econ_after_count > 4:
                        code, reason = elective_code(dept, level), "EL-RESIDENCY"
                # Seed equivalency-table matches are secured ("matched"). A decision recorded in the app is
                # "approved" (awaiting posting, TP) for each student until the Registrar posts that line.
                if dec.split == "runtime":
                    p = store.postings.get((student.student_id, ln.ext_id, ln.term))
                    state = "posted" if p and p["decision_id"] == dec.decision_id else "approved"
                else:
                    state = "matched"
                r = _Res(state, "Matched - existing equivalency", code, u, "T", reason)  # R24 grade T
                if dec.decision == "Equivalent" and reason not in ("EL-DUPLICATE", "EL-RESIDENCY"):
                    used_bu.add(dec.bu_course)
            else:
                st = store.syllabus_state(ln.ext_id)                                    # R22 / R23
                if st == "complete":
                    hint = ai_hint(ln.ext_id) if ai_hint else None
                    tier = f"; AI tier: {hint[0]}" if hint else ""
                    r = _Res("maybe_review", f"Maybe - syllabus on file{tier}", "", 0.0, "", "PD-REVIEW")
                elif st == "incomplete":
                    r = _Res("maybe_tm", "Maybe - syllabus incomplete (TM request)", "", 0.0, "", "PD-TM")
                else:
                    r = _Res("maybe_ts", "Maybe - syllabus requested (TS)", "", 0.0, "", "PD-TS")

        state_text, next_step = STATE_TEXT[r.state]
        if r.state == "posted_no_credit":
            meaning = store.reason_codes.get(r.reason_code, {}).get("meaning", "")
            state_text = f"Not transferable - {meaning.lower()}" if meaning else state_text
        out.append(dict(
            ext_id=ln.ext_id, school_code=ln.school_code, term=ln.term, course_code=ln.course_code, title=ln.title,
            credits=ln.credits, calendar=ln.calendar, grade=ln.grade,
            state=r.state, status=state_text, bu_status_code=STATUS_CODE[r.state],
            bu_course=r.bu_course or None, units=r.units, units_if_approved=u, reason_code=r.reason_code,
            bu_grade=r.bu_grade, flags=flags, next_step=next_step, ai_tier=None, ai_overlap_pct=None,
            _ref_status=r.ref_status, _decision_id=applied.decision_id if applied else None))

    # R17: 68-unit cap applied in transcript order; pending lines count with their units-if-approved.
    run = 0.0
    for o in out:
        c = o["units"] if o["units"] else (o["units_if_approved"] if o["state"].startswith(("maybe", "pending")) else 0.0)
        if c and run + c > CAP_UNITS:
            allowed = max(0.0, round(CAP_UNITS - run, 2))
            o["flags"].append(f"68-unit cap reached: only {allowed} of {c} units can count")
            if o["units"]:
                o["units"] = allowed
            run = CAP_UNITS
        else:
            run += c

    for o, ln in zip(out, store.lines_for(student.student_id)):
        code = o["bu_course"] or ""
        # R14 Biology residency (advisory; credit unaffected)
        if code.startswith("CAS BI ") and code not in ("CAS BI 107", "CAS BI 108") and not code.endswith("TR"):
            o["flags"].append("Biology residency: still needs 5 BI courses beyond BI 107/108 at BU (credit unaffected)")
        # R15 Economics timing: the four-course cap counts only courses transferred AFTER matriculation.
        if student.intended_major == "Economics" and o["state"] != "posted_no_credit" and term_key(ln.term) < start_key:
            target = None
            if o["_decision_id"]:
                d = next(d for d in store.decisions if d.decision_id == o["_decision_id"])
                target = d.bu_course
            elif ai_hint and o["state"] != "pending_age":
                hint = ai_hint(ln.ext_id)
                target = hint[1] if hint else None
            bu = store.bu_courses.get(target or "")
            if bu and bu.residency_rule.startswith("Economics"):
                o["flags"].append("Econ 200+ cap applies only after matriculation: not applied")
        # R16 Engineering residency: advisory only; no ENG students in this data set.
        # R18 Hub: transfer courses never earn BU Hub units, so no Hub field is produced.

    # R19: credits must be transferred within one year of starting at BU.
    today = today or _dt.date.today()
    deadline = _dt.date(start_year + 1, 9 if start_season == "Fall" else 1, 1)
    if today > deadline:
        for o in out:
            if o["state"].startswith(("maybe", "pending")):
                o["flags"].append("Past the one-year transfer deadline: Outstanding Transfer Credit Review needed")
    return out


def totals(lines: list[dict]) -> dict:
    secured = round(float(sum(o["units"] for o in lines if o["state"] in ("matched", "posted"))), 2)
    approved = round(float(sum(o["units"] for o in lines if o["state"] == "approved")), 2)
    pending = round(float(sum(o["units_if_approved"] for o in lines if o["state"].startswith(("maybe", "pending")))) + approved, 2)
    return dict(secured_units=secured, approved_units=approved, pending_units=pending,
                no_credit_lines=sum(1 for o in lines if o["state"] == "posted_no_credit"), cap_units=CAP_UNITS)
