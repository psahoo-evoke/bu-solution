"""Rules engine (ADR 0001): all 56 expected lines + sponsor examples T01-T04 + rule tests T05-T14."""
import csv
import os

import pytest

from app import rules
from app import store as store_mod
from app.main import _rec
from app.store import Decision, ExtCourse, Student, TranscriptLine

from .conftest import SEED

EXPECTED = list(csv.DictReader(open(os.path.join(SEED, "transcript_lines_expected.csv"), encoding="utf-8")))
# Narrative annotations the generator attached to a line for the demo script; they are not rule outcomes
# (the task scopes flags to cap / conflict / residency / econ-timing). Reported in ai-logs/2026-10-28/qa-01.md.
NARRATIVE_FLAGS = {"Same course as Maya's PSYCH-UA 10: matches instantly once her decision is approved (test T15)"}
STATE_OF_REASON = {"PD-REVIEW": "maybe_review", "PD-TS": "maybe_ts", "PD-TM": "maybe_tm", "RV-AGE": "pending_age"}
CODE_OF_STATE = {"matched": "T", "approved": "T", "posted_no_credit": "TX", "maybe_review": "TP", "maybe_ts": "TS",
                 "maybe_tm": "TM", "pending_age": "TP"}


def _hint(ext_id):
    r = _rec(ext_id)
    top = r["candidates"][0]
    return rules.tier_label(top["overlap_pct"] / 100), top["bu_code"]


def _evaluate_all():
    s = store_mod.STORE
    out = []
    for sid in ("SYN-24001", "SYN-24002", "SYN-24003", "SYN-24004"):
        out += rules.evaluate_student(s, s.students[sid], ai_hint=_hint)
    return out


def _line(student_id, ext_id, ai=True):
    s = store_mod.STORE
    for o in rules.evaluate_student(s, s.students[student_id], ai_hint=_hint if ai else None):
        if o["ext_id"] == ext_id:
            return o
    raise KeyError(ext_id)


@pytest.mark.parametrize("i", range(len(EXPECTED)), ids=[f"{e['student_id']}-{e['ext_id']}" for e in EXPECTED])
def test_expected_line(i):
    exp, got = EXPECTED[i], _evaluate_all()[i]
    assert got["ext_id"] == exp["ext_id"]
    assert got["_ref_status"] == exp["status"]
    assert (got["bu_course"] or "") == exp["bu_course"]
    assert got["units"] == pytest.approx(float(exp["units"]), abs=0.001)
    assert got["units_if_approved"] == pytest.approx(float(exp["units_if_approved"]), abs=0.001)
    assert got["bu_grade"] == exp["bu_grade"]
    assert got["reason_code"] == exp["reason_code"]
    exp_flags = [f for f in exp["flag"].split("; ") if f and f not in NARRATIVE_FLAGS]
    assert got["flags"] == exp_flags
    # API mapping
    if exp["status"].startswith("Posted"):
        assert got["state"] == "posted_no_credit"
    elif exp["status"].startswith("Matched"):
        assert got["state"] == "matched"
    else:
        assert got["state"] == STATE_OF_REASON[exp["reason_code"]]
    assert got["bu_status_code"] == CODE_OF_STATE[got["state"]]
    assert got["status"] and got["next_step"]


def test_all_56_lines_present():
    assert len(EXPECTED) == 56 and len(_evaluate_all()) == 56


# ------------------------------------------------------------------ sponsor worked examples
def test_T01_three_credit_semester_film_course_elective():
    s = store_mod.STORE
    s.ext_courses["NEU|FILM 2000"] = ExtCourse("NEU|FILM 2000", "NEU", "FILM 2000", "Film Genres", 3, "Semester", "",
                                               "Academic", 200, "Film genres.", [], [])
    s.students["SYN-T01"] = Student("SYN-T01", "Test Student", "Psychology", "Fall 2026")
    s.lines.append(TranscriptLine("SYN-T01", "NEU", "Fall 2025", "NEU|FILM 2000", "FILM 2000", "Film Genres", 3, "Semester", "B"))
    s.decisions.append(Decision("D-T01", "NEU|FILM 2000", "Elective", "TFRGEN 2TR", "EL-NOEQUIV", True, "2025-26",
                                "Evaluator", "2026-01-01"))
    [o] = rules.evaluate_student(s, s.students["SYN-T01"])
    assert o["bu_course"].endswith("TR") and o["reason_code"] == "EL-NOEQUIV"
    assert o["units"] == 3.00 and o["bu_grade"] == "T" and o["bu_status_code"] == "T"


def test_T02_quarter_conversion():
    assert rules.convert_units(4, "Quarter") == 2.67
    o = _line("SYN-24001", "PSC|PSY 215")
    assert (o["bu_course"], o["units"], o["bu_grade"]) == ("CAS PS 2TR", 2.67, "T")


def test_T03_c_minus_no_credit():
    s = store_mod.STORE
    o = next(o for o in rules.evaluate_student(s, s.students["SYN-24002"]) if o["ext_id"] == "NEU|MATH 1341")
    assert (o["bu_course"], o["units"], o["bu_grade"], o["reason_code"]) == ("TFRGEN NOCRDT", 0.0, "TX", "NC-GRADE")


def test_T04_developmental_math_no_credit():
    o = _line("SYN-24002", "NEU|MATH 0990")
    assert (o["bu_course"], o["units"], o["bu_grade"], o["reason_code"]) == ("TFRGEN NOCRDT", 0.0, "TX", "NC-REMEDIAL")


# ------------------------------------------------------------------ T05-T14
def test_T05_lab_units_are_students_units():
    o = _line("SYN-24003", "NEU|BIOL 1107")
    assert o["bu_course"] == "CAS BI 107" and o["units"] == 5.0
    assert store_mod.STORE.bu_courses["CAS BI 107"].credits == 4


def test_T06_duplicate_becomes_elective():
    o = _line("SYN-24002", "NEU|CS 1990")
    assert (o["bu_course"], o["reason_code"]) == ("CAS CS 1TR", "EL-DUPLICATE")
    assert _line("SYN-24002", "NEU|CS 2000")["bu_course"] == "CAS CS 111"


def test_T07_cs_group_c_residency():
    o = _line("SYN-24002", "NEU|CS 4400")
    assert (o["bu_course"], o["units"], o["reason_code"]) == ("CAS CS 2TR", 4.0, "EL-RESIDENCY")


def test_T07b_runtime_group_c_equivalent_is_converted():
    s = store_mod.STORE
    s.decisions = [d for d in s.decisions if d.ext_id != "NEU|CS 4400"]
    s.decisions.append(Decision("D-X", "NEU|CS 4400", "Equivalent", "CAS CS 320", "EQ-CONTENT", True, "2026-27", "E", "2026-10-01"))
    o = _line("SYN-24002", "NEU|CS 4400")
    assert (o["bu_course"], o["reason_code"]) == ("CAS CS 2TR", "EL-RESIDENCY")


def test_T08_pass_fail():
    assert _line("SYN-24002", "NEU|FILM 1101")["reason_code"] == "NC-PASSFAIL"


def test_T09_age_review():
    o = _line("SYN-24002", "NEU|HIST 1130")
    assert (o["state"], o["reason_code"], o["units"]) == ("pending_age", "RV-AGE", 0.0)
    # same course, Spring 2023, is not old for Liam
    assert _line("SYN-24004", "NEU|HIST 1130")["state"] == "matched"


def test_T10_non_accredited():
    for e in ("SOI|ECO 210", "SOI|BUS 101"):
        o = _line("SYN-24004", e)
        assert (o["reason_code"], o["bu_grade"], o["units"]) == ("NC-ACCRED", "TX", 0.0)


def test_T11_68_unit_cap():
    s = store_mod.STORE
    lines = rules.evaluate_student(s, s.students["SYN-24004"], ai_hint=_hint)
    capped = [o["ext_id"] for o in lines if any(f.startswith("68-unit cap") for f in o["flags"])]
    assert capped == ["NYU|ECON-UA 163", "NYU|ECON-UA 166", "NYU|ECON-UA 169"]
    assert rules.totals(lines)["secured_units"] <= 68.0
    assert _line("SYN-24004", "NYU|ECON-UA 163")["units"] == 0.0


def test_T12_superseded_decision():
    o = _line("SYN-24004", "NYU|ECON-UA 18")
    assert o["bu_course"] == "CAS EC 203"
    assert "Older conflicting decision superseded by newest catalog year" in o["flags"]


def test_T13_same_year_conflict():
    o = _line("SYN-24003", "NEU|BIOL 2703")
    assert o["bu_course"] == "CAS BI 2TR"
    assert any(f.startswith("CONFLICT") for f in o["flags"])


def test_T14_econ_cap_not_applied_before_matriculation():
    for e in ("NYU|ECON-UA 10", "NYU|ECON-UA 12", "NYU|ECON-UA 18", "NYU|ECON-UA 163", "NYU|ECON-UA 166"):
        o = _line("SYN-24004", e)
        assert "Econ 200+ cap applies only after matriculation: not applied" in o["flags"]
        assert o["reason_code"] != "EL-RESIDENCY"


def test_R15_econ_cap_applies_after_matriculation():
    s = store_mod.STORE
    s.lines = [ln for ln in s.lines if ln.student_id != "SYN-24004"]
    codes = ["ECON-UA 10", "ECON-UA 12", "ECON-UA 18", "ECON-UA 163", "ECON-UA 166"]
    for c in codes:
        s.lines.append(TranscriptLine("SYN-24004", "NYU", "Spring 2027", f"NYU|{c}", c, c, 4, "Semester", "A"))
    out = rules.evaluate_student(s, s.students["SYN-24004"])
    assert [o["reason_code"] for o in out][-1] == "EL-RESIDENCY"
    assert out[-1]["bu_course"] == "CAS EC 1TR" or out[-1]["bu_course"].endswith("TR")


def test_holdout_decisions_invisible_to_lookup():
    s = store_mod.STORE
    for d in s.holdout_decisions:
        assert rules.lookup(s, d.ext_id, "SYN-24001") == (None, "")
