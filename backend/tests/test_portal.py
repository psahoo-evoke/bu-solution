"""Portal sign-in (TRANSFERIQ_AUTH_MODE=portal, app/accounts.py): per-user accounts, own-record scoping for students,
own-department scoping for departments, self-registration."""
import os

import pytest

from app import accounts

from .conftest import SYLLABI, TRANSCRIPTS


@pytest.fixture(autouse=True)
def portal(monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    accounts.reset_accounts()
    yield
    accounts.reset_accounts()


def login(anon, email, portal="student", password="admin"):
    return anon.post("/api/auth/login", json=dict(email=email, password=password, portal=portal))


def bearer(anon, email, portal="student"):
    r = login(anon, email, portal)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ------------------------------------------------------------------ sign-in
def test_sample_students_sign_in_with_admin(anon):
    for sid, email in accounts.SAMPLE_STUDENTS.items():
        body = login(anon, email).json()
        assert body["user"]["student_id"] == sid and body["user"]["role"] == "Student"


def test_wrong_password_unknown_email_and_wrong_portal(anon):
    assert login(anon, "maya.delgado@bu.edu", password="nope").status_code == 401
    r = login(anon, "nobody@bu.edu")
    assert r.status_code == 404 and "Register" in r.json()["detail"]
    r = login(anon, "maya.delgado@bu.edu", portal="department")
    assert r.status_code == 403 and "Student sign-in" in r.json()["detail"]
    assert login(anon, "not-an-email").status_code == 422
    assert login(anon, "maya@gmail.com").status_code == 404     # any domain is a valid email, just not registered


def test_api_needs_a_session(anon):
    assert anon.get("/api/students").status_code == 401
    assert anon.get("/api/students", headers={"X-Demo-Role": "Registrar"}).status_code == 401   # header not trusted
    assert anon.get("/api/students", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert anon.get("/api/health").status_code == 200


def test_login_disabled_outside_portal_mode(anon, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "demo")
    assert login(anon, "maya.delgado@bu.edu").status_code == 409


# ------------------------------------------------------------------ student: own record only
def test_student_sees_only_their_own_record(anon):
    h = bearer(anon, "jordan.reyes@bu.edu")
    assert [s["student_id"] for s in anon.get("/api/students", headers=h).json()] == ["SYN-24002"]
    assert anon.get("/api/students/SYN-24002/evaluation", headers=h).status_code == 200
    r = anon.get("/api/students/SYN-24001/evaluation", headers=h)
    assert r.status_code == 403 and "own record" in r.json()["detail"]
    with open(os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_NYU_Maya_Delgado.pdf"), "rb") as f:
        assert anon.post("/api/students/SYN-24001/transcripts", headers=h, files={"file": ("t.pdf", f)}).status_code == 403
    assert anon.get("/api/review-queue", headers=h).status_code == 403


def test_student_syllabus_only_for_own_courses(anon):
    maya, jordan = bearer(anon, "maya.delgado@bu.edu"), bearer(anon, "jordan.reyes@bu.edu")
    path = os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf")
    with open(path, "rb") as f:
        assert anon.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", headers=jordan, files={"file": ("s.pdf", f)}).status_code == 403
    with open(path, "rb") as f:
        assert anon.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", headers=maya, files={"file": ("s.pdf", f)}).status_code == 201


# ------------------------------------------------------------------ department: own department only
def test_department_sees_and_decides_only_its_courses(anon, fresh_store):
    h = bearer(anon, "biology.dept@bu.edu", "department")
    queue = anon.get("/api/review-queue", params={"department": "Psychology"}, headers=h).json()
    assert queue and {i["department"] for i in queue} == {"Biology"}           # filter forced to own department
    other = next(e for e, c in fresh_store.ext_courses.items() if c.program_area == "Psychology")
    dec = dict(ext_id=other, decision="Elective", bu_course="CAS PS 1TR", reason_code="EL-LOWOVERLAP", evaluator="B")
    r = anon.post("/api/decisions", json=dec, headers=h)
    assert r.status_code == 403 and "Biology department" in r.json()["detail"]
    r = anon.post("/api/decisions/batch", json={"ext_ids": [other], "evaluator": "B"}, headers=h)
    assert r.status_code == 403
    r = anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "B"}, headers=h)
    assert r.status_code == 201 and fresh_store.audit_log[-1]["actor_role"] == "Department"


def test_department_cannot_post_credit(anon):
    h = bearer(anon, "psychology.dept@bu.edu", "department")
    assert anon.post("/api/postings", headers=h).status_code == 403


def test_staff_accounts_keep_full_access(anon):
    reg = bearer(anon, "registrar@bu.edu", "staff")
    assert len(anon.get("/api/students", headers=reg).json()) == 4
    assert anon.get("/api/exports/mybu.csv", headers=reg).status_code == 200
    ev = bearer(anon, "evaluator@bu.edu", "staff")
    assert {i["department"] for i in anon.get("/api/review-queue", headers=ev).json()} > {"Biology"}


# ------------------------------------------------------------------ registration
def test_register_student_creates_own_empty_record(anon, fresh_store):
    r = anon.post("/api/auth/register/student", json=dict(
        name="Sam Patel", email="Sam.Patel@bu.edu", password="secret1", intended_major="Mathematics"))
    assert r.status_code == 201
    user = r.json()["user"]
    assert user["student_id"] == "SYN-24005" and user["email"] == "sam.patel@bu.edu"
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    ev = anon.get("/api/students/SYN-24005/evaluation", headers=h).json()
    assert ev["student"]["name"] == "Sam Patel" and ev["lines"] == []
    assert login(anon, "sam.patel@bu.edu", password="secret1").status_code == 200
    assert anon.post("/api/auth/register/student", json=dict(
        name="Sam", email="sam.patel@bu.edu", password="secret1", intended_major="Mathematics")).status_code == 409


def test_register_accepts_any_email_domain(anon, fresh_store):
    r = anon.post("/api/auth/register/student", json=dict(
        name="Pat Lee", email="Pat.Lee@Example.com", password="secret1", intended_major="Mathematics"))
    assert r.status_code == 201 and r.json()["user"]["email"] == "pat.lee@example.com"
    sid = r.json()["user"]["student_id"]
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert anon.get(f"/api/students/{sid}/evaluation", headers=h).json()["student"]["email"] == "pat.lee@example.com"
    assert login(anon, "pat.lee@example.com", password="secret1").status_code == 200


def test_registered_student_survives_demo_reset(anon):
    r = anon.post("/api/auth/register/student", json=dict(
        name="Ana Lima", email="ana.lima@bu.edu", password="admin", intended_major="Biology"))
    sid = r.json()["user"]["student_id"]
    reg = bearer(anon, "registrar@bu.edu", "staff")
    assert anon.post("/api/demo/reset", headers=reg).status_code == 204
    h = bearer(anon, "ana.lima@bu.edu")
    assert anon.get(f"/api/students/{sid}/evaluation", headers=h).status_code == 200


def test_register_department(anon):
    r = anon.post("/api/auth/register/department", json=dict(
        name="Dr. Kim", email="kim@bu.edu", password="admin", department="Economics"))
    assert r.status_code == 201 and r.json()["user"]["department"] == "Economics"
    assert anon.post("/api/auth/register/department", json=dict(
        name="X", email="x@bu.edu", password="admin", department="Astrology")).status_code == 422


@pytest.mark.parametrize("bad", [
    dict(email="sam@nodomain"), dict(password="123"), dict(name="S"), dict(intended_major=""),
])
def test_register_student_validation(anon, bad):
    body = dict(name="Sam Patel", email="sam@bu.edu", password="secret1", intended_major="Mathematics") | bad
    assert anon.post("/api/auth/register/student", json=body).status_code == 422


def test_options_are_public(anon):
    body = anon.get("/api/auth/options").json()
    assert body["mode"] == "portal" and "Biology" in body["departments"] and body["majors"]


# ------------------------------------------------------------------ who decided: the account, not a typed name
def test_decisions_record_the_signed_in_accounts_name(anon, fresh_store):
    ev = bearer(anon, "evaluator@bu.edu", "staff")
    dec = dict(ext_id="NYU|PSYCH-UA 10", decision="Equivalent", bu_course="CAS PS 211", reason_code="EQ-EVALUATOR",
               evaluator="Someone Else")
    r = anon.post("/api/decisions", json=dec, headers=ev)
    assert r.status_code == 201 and r.json()["evaluator"] == f"{accounts.STAFF_NAMES['Evaluator']} <evaluator@bu.edu>"
    h = bearer(anon, "biology.dept@bu.edu", "department")
    r = anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "Someone Else"}, headers=h)
    assert r.status_code == 201 and {d["evaluator"] for d in r.json()} == {"Biology Department <biology.dept@bu.edu>"}


# ------------------------------------------------------------------ advisor and financial aid caseload
def test_advisor_and_financial_aid_sign_in_and_read_the_caseload(anon):
    for email in ("advisor@bu.edu", "financialaid@bu.edu"):
        h = bearer(anon, email, "staff")
        r = anon.get("/api/students/summary", headers=h)
        assert r.status_code == 200 and len(r.json()) == len(accounts.SAMPLE_STUDENTS)
    fa = bearer(anon, "financialaid@bu.edu", "staff")
    assert anon.post("/api/postings", json={}, headers=fa).status_code == 403
    assert anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "x"}, headers=fa).status_code == 403


def test_a_student_cannot_read_the_caseload(anon):
    assert anon.get("/api/students/summary", headers=bearer(anon, "maya.delgado@bu.edu")).status_code == 403
