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
_PARTIAL_RE = re.compile(r"^(?:[A-Z]{2,8}(?:-[A-Z]{2})?|\d{1,4})$")     # just a department ("CS") or a number ("3000")
MAX_SUGGESTIONS = 6
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


def resolve_school(store: Store, school: str):
    """(school, suggestions). Only an exact code or name is used. Anything else returns suggestions for the student
    to confirm: the start of a code ("NE" -> NEU), the start of a word in the name ("northeastern", 3+ letters) or
    part of the name (4+ letters); all catalog schools when nothing matches. Never auto-picked, even when only one
    school matches: "northeast" could be Northeast State, and a decided result for the wrong school misleads."""
    exact = find_school(store, school)
    if exact is not None:
        return exact, []
    q = re.sub(r"\s+", " ", (school or "").strip().lower())
    every = list(store.schools.values())
    if len(q) < 2:
        return None, every
    hits = [sc for sc in every if sc.school_code.lower().startswith(q)
            or (len(q) >= 3 and any(w.startswith(q) for w in re.findall(r"[a-z]+", sc.name.lower())))
            or (len(q) >= 4 and q in sc.name.lower())]
    return None, hits or every


def course_suggestions(store: Store, school_code: str, code: str = "", title: str = "") -> list[dict]:  # all matches
    """Catalog courses (never upload-only ones) whose code starts with the partial `code` ("CS 30" -> CS 3000, CS
    3001; "3000" -> any department's 3000), or, without a code, whose title contains `title`."""
    q = re.sub(r"[\s-]+", "", code.upper())
    t = (title or "").strip().lower()
    rows = []
    for c in catalog_rows(store, school_code):
        dept, number = c.course_code.split()[0].upper(), c.course_code.split()[-1]
        if q.isalpha():                                    # a department alone: "CS" is CS, not CSE
            hit = q in (dept.replace("-", ""), dept.split("-")[0])          # "PSYCH-UA" or "PSYCH"
        elif q.isdigit():                                  # a number alone: any department's 3000
            hit = number.startswith(q)
        elif q:                                            # department + start of the number: "CS30" -> CS 3000
            hit = re.sub(r"[\s-]+", "", c.course_code.upper()).startswith(q)
        else:                                              # no code: the title
            hit = len(t) >= 3 and t in c.title.lower()
        if hit:
            rows.append(c)
    return [dict(course_code=c.course_code, title=c.title, credits=c.credits) for c in rows]


def _did_you_mean(rows: list[dict]) -> str:
    shown = ", ".join(f"{r['course_code']} ({r['title']})" for r in rows[:MAX_SUGGESTIONS])
    more = len(rows) - MAX_SUGGESTIONS
    return f"Did you mean {shown}" + (f", or one of {more} more (type more of the code)?" if more > 0 else "?")


def schools(store: Store) -> list[dict]:
    return [dict(school_code=s.school_code, name=s.name, calendar=s.calendar) for s in store.schools.values()]


def courses(store: Store, school: str) -> Optional[list[dict]]:
    """A school's catalog courses for the form's course picker (code, title, credits), sorted by code; None for an
    unknown school. Courses known only from a transcript upload are left out, as in check_course."""
    sc = find_school(store, school)
    if sc is None:
        return None
    return [dict(course_code=c.course_code, title=c.title, credits=c.credits) for c in catalog_rows(store, sc.school_code)]


def is_catalog(c: ExtCourse) -> bool:
    """The one privacy rule of the public check: courses created by a transcript upload have no program area and
    are never shown, suggested or used (ADR 0006)."""
    return bool(c.program_area)


def catalog_course(store: Store, ext_id: str) -> Optional[ExtCourse]:
    c = store.ext_courses.get(ext_id)
    return c if c is not None and is_catalog(c) else None


def catalog_rows(store: Store, school_code: str) -> list[ExtCourse]:
    return sorted((c for c in store.ext_courses.values() if c.school_code == school_code and is_catalog(c)),
                  key=lambda c: c.course_code)


# Keyword / subject search over the catalog (credit chat). Only catalog fields: code, title, subject, topics.
MAX_MATCHES = 8
_SEARCH_STOP = {
    "a", "an", "the", "and", "or", "of", "in", "at", "on", "for", "to", "from", "with", "my", "i", "me", "do", "does",
    "did", "is", "are", "can", "will", "would", "which", "what", "any", "all", "show", "list", "find", "search", "about",
    "course", "courses", "class", "classes", "subject", "subjects", "program", "programs", "transfer", "transfers",
    "credit", "credits", "bu", "boston", "university", "took", "take", "taken", "there", "that", "this", "please", "some",
}
_SCHOOL_GENERIC = {"university", "college", "state", "institute", "online", "school", "community"}
_SEARCH_ALIASES = {
    "cs": "computer", "comp": "computer", "programming": "computer", "coding": "computer", "code": "computer",
    "math": "mathematics", "maths": "mathematics", "calc": "calculus", "stats": "statistics", "stat": "statistics",
    "psych": "psychology", "econ": "economics", "bio": "biology", "gen": "general", "ed": "education",
}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _code_in(code: str, text: str) -> bool:
    """`code` written anywhere in `text` as a whole code, spaces and dashes optional: "psych-ua10" has PSYCH-UA 10
    but not PSYCH-UA 1."""
    parts = map(re.escape, re.split(r"[\s-]+", code.upper()))
    return re.search(r"(?<![A-Z0-9])" + r"[\s-]*".join(parts) + r"(?![A-Z0-9])", text) is not None


def search_courses(store: Store, query: str, school: str = "") -> dict:
    """Catalog courses for a keyword, subject or code ("psychology", "NYU math", "calc", "PSYCH-UA 10"), across all
    schools or one. A school named in the query narrows the search. Without any search word (just "course" or
    "subject"), the subjects per school. Never upload-only courses or ground truth (ADR 0006)."""
    sc = find_school(store, school) if school else None
    words = _words(query)
    codes = {s.school_code.lower(): s for s in store.schools.values()}
    if sc is None:                                    # "NYU math" / "northeastern biology": the school in the query
        named = {codes[w].school_code: codes[w] for w in words if w in codes}
        for s in store.schools.values():              # a distinctive word of the name: "northeastern", "pinecrest"
            if any(w in words for w in _words(s.name) if len(w) >= 4 and w not in _SCHOOL_GENERIC):
                named[s.school_code] = s
        sc = next(iter(named.values())) if len(named) == 1 else None
    if sc is not None:
        drop = {sc.school_code.lower(), *_words(sc.name)}
        words = [w for w in words if w not in drop]
    rows = [c for s in ([sc] if sc else list(store.schools.values())) for c in catalog_rows(store, s.school_code)]
    names = {s.school_code: s.name for s in store.schools.values()}
    q_upper = (query or "").upper()
    q_lower = (query or "").lower()
    exact = [c for c in rows if _code_in(c.course_code, q_upper)]
    if not exact:                                      # a full title of 2+ words: "calculus i" is Calculus I only
        exact = [c for c in rows if len(c.title.split()) >= 2 and re.search(
            r"(?<![a-z0-9])" + re.escape(c.title.lower()) + r"(?![a-z0-9])", q_lower)]
    terms = [(w, _SEARCH_ALIASES.get(w, w)) for w in words if w not in _SEARCH_STOP and len(w) > 1]
    if not exact and not terms:
        subjects: dict[str, set] = {}
        for c in rows:
            subjects.setdefault(c.program_area, set()).add(c.school_code)
        return dict(school=sc.school_code if sc else None, matches=[], total=0,
                    subjects=[dict(subject=k, schools=sorted(v)) for k, v in sorted(subjects.items())])

    def score(c: ExtCourse) -> int:
        dept = _words(c.course_code)
        title, subject = _words(c.title), _words(c.program_area)
        topics = [w for t in c.topics for w in _words(t)]
        total = 0
        for orig, alias in terms:
            stems = {t[:-1] if len(t) > 4 and t.endswith("s") else t for t in (orig, alias)}
            hit = (4 if orig in dept else
                   3 if any(w.startswith(st) for w in title for st in stems) else
                   2 if any(w.startswith(st) for w in subject for st in stems) else
                   1 if any(w.startswith(st) for w in topics for st in stems) else 0)
            if not hit:
                return 0                                   # every search word must match somewhere
            total += hit
        return total
    ranked = exact or sorted((c for c in rows if score(c)), key=lambda c: (-score(c), c.level, c.school_code, c.course_code))
    return dict(school=sc.school_code if sc else None, total=len(ranked),
                matches=[dict(school_code=c.school_code, school_name=names.get(c.school_code, ""),
                              course_code=c.course_code, title=c.title, subject=c.program_area, credits=c.credits)
                         for c in ranked[:MAX_MATCHES]])


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
    code = normalize_code(course_code) if course_code else ""
    if code and not (_CODE_RE.match(code) or _PARTIAL_RE.match(code)):     # input errors first, whatever the school
        raise CheckError("Course code must look like 'PSYCH-UA 10'")
    sc, school_options = resolve_school(store, school)
    if sc is None:
        options = [dict(school_code=o.school_code, name=o.name) for o in school_options]
        names = ", ".join(f"{o['name']} ({o['school_code']})" for o in options)
        return _result("unknown_school", school_suggestions=options,
                       message=(f"Did you mean {names}? Please confirm the school." if len(options) == 1 else
                                f"'{sanitize(school)[:60]}' does not match one school in the catalog. Schools: {names}. If yours "
                                "is not listed, upload the transcript and a syllabus after you register, and an "
                                "evaluator will review it."))
    return _check(store, sc, course_code, title, description, grade, credits, term, start_term, estimate)


def _check(store: Store, sc, course_code: str, title: str, description: str, grade: str, credits: Optional[float],
           term: str, start_term: str, estimate: bool) -> dict:
    code = normalize_code(course_code) if course_code else ""
    partial = bool(code) and not _CODE_RE.match(code)       # a department or number alone (validated above)
    grade = (grade or "").strip().upper()
    term_n, start_n = _term(term), _term(start_term) or "Fall 2026"
    description = (description or "")[:MAX_DESCRIPTION]
    course = catalog_course(store, f"{sc.school_code}|{code}") if code and not partial else None
    calendar = course.calendar if course else sc.calendar
    cr = float(credits) if credits else (course.credits if course else None)
    units = convert_units(cr, calendar) if cr else None                                   # R08 / R09
    base = dict(school_code=sc.school_code, school_name=sc.name, course_code=code or None,
                title=(course.title if course else sanitize(title)[:120]) or None, calendar=calendar, credits=cr)

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
    if partial:                                            # "CS" or "3000": which course exactly?
        rows = course_suggestions(store, sc.school_code, code)
        return _result("unknown_course", **base, units=units, suggestions=rows[:MAX_SUGGESTIONS],
                       message=(f"'{code}' is only part of a course code. " + _did_you_mean(rows)) if rows else
                               f"No {sc.name} course code starts with '{code}'. Check the code on your transcript.")

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

    rows = course_suggestions(store, sc.school_code, code, title) if not course else []
    if not course and not (title or description):
        return _result("unknown_course", **base, units=units, suggestions=rows[:MAX_SUGGESTIONS],
                       message=(f"{code} is not in the catalog. " + _did_you_mean(rows) + " If it is none of these, add "
                                "what the course covers for a preliminary estimate.") if rows else
                               "This course is not in the catalog yet. Add its title or a short description for "
                               "a preliminary estimate, or upload the syllabus after registering.")
    est = None
    if estimate:
        est = _estimate(store, course, sc, code, title, description)
    return _result("needs_evaluation", **base, units=units, estimate=est, **({"suggestions": rows[:MAX_SUGGESTIONS]} if rows else {}),
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
