"""Public "will this course transfer?" check, before any login or transcript (used by the credit-check form and the
credit chat). Facts come from the rules engine and the equivalency table; the matcher only adds a preliminary
estimate for courses nobody has decided yet. ADR 0006.

What it may reveal: catalog data (schools, external and BU courses) and REUSABLE past decisions, the same facts
any student would see on their own status page. Never: holdout decisions, decisions made for one student
(rules.lookup_public), student records or ground truth. Courses that exist only because a student uploaded a
transcript (no catalog program area) are treated as not in the catalog, so the check cannot reveal what someone
uploaded.

Per-course rules come from the evaluation's own code (rules.no_credit_reason for R01-R06, R07 age, R08 quarter
conversion, rules.lookup_public for R10/R11, R13 CS Group C). An R11 same-year conflict shows the newest decision,
as the evaluation does, with a caveat that the department is confirming it. Rules that depend on the whole record or the major (R12 duplicates, R14-R16 residency, R17 68-unit cap, R19
deadline) are returned as caveats, not applied.
"""
from __future__ import annotations

import re
from typing import Optional

from .matcher import recommend
from .rules import NO_CREDIT_CODE, convert_units, elective_code, lookup_public, no_credit_reason, term_year
from .safety import detect_injection, sanitize
from .store import ExtCourse, Store

CAVEATS = [
    "This is an estimate before evaluation. The official decision is made when your transcript is evaluated.",
    "Record-wide rules are not applied here: at most 68 transfer units count (R17), a second course covering the "
    "same BU course earns elective credit (R12), and some majors limit transfer courses (R14-R16).",
]
MAX_DESCRIPTION = 2000
_CODE_RE = re.compile(r"^[A-Za-z]{2,8}(?:-[A-Za-z]{2})?\s*\d{1,4}[A-Za-z]?$")
_TERM_RE = re.compile(r"^(Winter|Spring|Summer|Fall)\s+(\d{4})$", re.IGNORECASE)
NO_CREDIT_TEXT = {
    "NC-ACCRED": "{school} is not regionally accredited, so its courses do not transfer.",
    "NC-ONECREDIT": "One-credit courses are generally not accepted.",
    "NC-PASSFAIL": "Pass/fail grades are generally not accepted.",
    "NC-GRADE": "A grade of {grade} is below the minimum of C.",
}
DECIDED = ("decided_equivalent", "decided_elective")


class CheckError(ValueError):
    pass


def normalize_code(code: str) -> str:
    """'psych-ua10' / 'PSYCH-UA  10' -> 'PSYCH-UA 10'."""
    c = re.sub(r"\s+", " ", (code or "").strip()).upper()
    m = re.match(r"^([A-Z]{2,8}(?:-[A-Z]{2})?)\s*(\d{1,4}[A-Z]?)$", c)
    return f"{m.group(1)} {m.group(2)}" if m else c


def _term(term: Optional[str]) -> Optional[str]:
    if not term:
        return None
    m = _TERM_RE.match(term.strip())
    if not m:
        raise CheckError("Term must look like 'Fall 2024'")
    return f"{m.group(1).title()} {m.group(2)}"


def find_school(store: Store, school: str):
    """By code ('NYU') or name, case-insensitive."""
    s = (school or "").strip().lower()
    return next((sc for sc in store.schools.values() if s in (sc.school_code.lower(), sc.name.lower())), None)


def schools(store: Store) -> list[dict]:
    return [dict(school_code=s.school_code, name=s.name, calendar=s.calendar) for s in store.schools.values()]


def courses(store: Store, school: str) -> Optional[list[dict]]:
    """A school's catalog courses for the form's course picker (code, title, credits), sorted by code; None for an
    unknown school. Courses known only from a transcript upload are left out, as in check_course."""
    sc = find_school(store, school)
    if sc is None:
        return None
    rows = [c for c in store.ext_courses.values() if c.school_code == sc.school_code and c.program_area]
    return [dict(course_code=c.course_code, title=c.title, credits=c.credits)
            for c in sorted(rows, key=lambda c: c.course_code)]


def catalog_course(store: Store, ext_id: str) -> Optional[ExtCourse]:
    """A catalog course, or None. Courses created by a transcript upload have no program area and are private."""
    c = store.ext_courses.get(ext_id)
    return c if c is not None and c.program_area else None


GRADE_ASSUMED = " This assumes a grade of C or better; pass/fail grades and grades below C do not transfer."


def _result(kind: str, **kw) -> dict:
    """kind: decided_equivalent | decided_elective | not_transferable | pending_review | needs_evaluation |
    unknown_school | unknown_course."""
    return {**dict(kind=kind, bu_course=None, units=None, reason_code=None, estimate=None, caveats=list(CAVEATS)), **kw}


def _assume_grade(res: dict, grade: str) -> dict:
    """Without a grade, a decided match only holds for C or better (R05/R06): say so."""
    if not grade and res["kind"] in DECIDED:
        res["message"] += GRADE_ASSUMED
    return res


CONFLICT_CAVEAT = ("Evaluators recorded different decisions for this course in the same catalog year. The newest "
                   "one is shown, and the department has been asked to confirm it, so it may change.")


def _conflict(res: dict, flag: str) -> dict:
    """R11: the evaluation applies the newest decision and flags a same-year conflict for the department; say so."""
    if flag.startswith("CONFLICT"):
        res["caveats"].insert(0, CONFLICT_CAVEAT)
        res["message"] += " The department is confirming this decision, so it may change."
    return res


def check_course(store: Store, school: str, course_code: str = "", title: str = "", description: str = "",
                 grade: str = "", credits: Optional[float] = None, term: str = "", start_term: str = "Fall 2026",
                 estimate: bool = True) -> dict:
    sc = find_school(store, school)
    if sc is None:
        return _result("unknown_school", message=f"'{school[:60]}' is not a school in the catalog yet. Upload the "
                       "transcript and a syllabus after you register, and an evaluator will review it.")
    code = normalize_code(course_code) if course_code else ""
    if code and not _CODE_RE.match(code):
        raise CheckError("Course code must look like 'PSYCH-UA 10'")
    grade = (grade or "").strip().upper()
    term_n, start_n = _term(term), _term(start_term) or "Fall 2026"
    description = (description or "")[:MAX_DESCRIPTION]
    course = catalog_course(store, f"{sc.school_code}|{code}") if code else None
    calendar = course.calendar if course else sc.calendar
    cr = float(credits) if credits else (course.credits if course else None)
    units = convert_units(cr, calendar) if cr else None                                   # R08 / R09
    base = dict(school_code=sc.school_code, school_name=sc.name, course_code=code or None,
                title=(course.title if course else title[:120]) or None, calendar=calendar, credits=cr)

    def no_credit(reason: str, message: str) -> dict:
        meaning = store.reason_codes.get(reason, {}).get("meaning", "")
        return _result("not_transferable", **base, reason_code=reason, bu_course=NO_CREDIT_CODE, units=0.0,
                       message=message + (f" ({meaning})" if meaning else ""))

    nc = no_credit_reason(sc.accredited, course.course_type if course else "Academic", cr, grade or None)  # R01-R06
    if nc:
        text = NO_CREDIT_TEXT.get(nc, "{ctype} courses are not eligible for transfer credit.")
        return no_credit(nc, text.format(school=sc.name, grade=grade, ctype=course.course_type if course else ""))
    if term_n and term_year(term_n) <= int(start_n.split()[1]) - 5:                        # R07
        return _result("pending_review", **base, reason_code="RV-AGE", units=units,
                       message="Courses five or more years old are reviewed before any credit is given.")

    if course:
        dec, flag = lookup_public(store, course.ext_id)                                    # R10 / R11 (reusable only)
        if dec and dec.decision == "No credit":
            return _conflict(no_credit(dec.reason_code, "An evaluator has already decided this course does not "
                                                        "transfer."), flag)
        if dec:
            bu = store.bu_courses.get(dec.bu_course)
            dept = dec.bu_course.split()[1] if len(dec.bu_course.split()) > 1 else "TFRGEN"
            if dec.decision == "Equivalent" and bu and bu.requirement_type.startswith("Group C"):    # R13
                res = _result("decided_elective", **base, bu_course=elective_code(dept, course.level), units=units,
                              reason_code="EL-RESIDENCY", message=f"Matches {bu.bu_code}, which must be taken at "
                              f"BU, so it transfers as elective credit.")
            elif dec.decision == "Equivalent":
                res = _result("decided_equivalent", **base, bu_course=dec.bu_course, units=units,
                              reason_code=dec.reason_code, bu_title=bu.title if bu else None,
                              message=f"Already decided: transfers as {dec.bu_course}"
                                      f"{' (' + bu.title + ')' if bu else ''}.")
            else:
                res = _result("decided_elective", **base, bu_course=dec.bu_course, units=units,
                              reason_code=dec.reason_code,
                              message=f"Already decided: transfers as elective credit ({dec.bu_course}).")
            return _conflict(_assume_grade(res, grade), flag)

    if not course and not (title or description):
        return _result("unknown_course", **base, units=units,
                       message="This course is not in the catalog yet. Add its title or a short description for "
                               "a preliminary estimate, or upload the syllabus after registering.")
    est = None
    if estimate:
        est = _estimate(store, course, sc, code, title, description)
    return _result("needs_evaluation", **base, units=units, estimate=est,
                   message="No decision yet: an evaluator will compare the syllabus with BU courses. "
                           + ("The possible matches below are a preliminary estimate, not a promise of credit."
                              if est and est["candidates"] else ""))


def _estimate(store: Store, course: Optional[ExtCourse], sc, code: str, title: str, description: str) -> dict:
    """Preliminary BU candidates (R22: description-only evidence is never decidable). Injected text is removed.
    A course typed in by the caller is ranked without touching the shared model cache."""
    adhoc = course is None
    if adhoc:
        course = ExtCourse(f"{sc.school_code}|{code or 'UNLISTED'}", sc.school_code, code or "UNLISTED",
                           sanitize(title)[:120], 3.0, sc.calendar, "", "Academic", 100,
                           sanitize(description or title)[:MAX_DESCRIPTION], [], [])   # the ranker reads the text
    syllabus = None if adhoc else store.syllabi.get(course.ext_id)
    rec = recommend(course, list(store.bu_courses.values()), syllabus, cache=not adhoc)
    cands = [dict(bu_code=c["bu_code"], title=c["title"], overlap_pct=c["overlap_pct"]) for c in rec["candidates"]
             if c["overlap_pct"] > 0]
    return dict(preliminary=True, candidates=cands[:3], engine=rec["engine"],
                injection_detected=rec["injection_detected"] or detect_injection(f"{title} {description}"))
