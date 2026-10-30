"""Step 5 of the process: the Credit Evaluation Department asks the student for the syllabus of every "maybe" course,
automatically after a transcript upload, and the department evaluator reads the syllabus next to the AI comparison
(GET /courses/{ext_id}/syllabus). Mail service faked; no network."""
import os

import pytest

from app import accounts, notify

from .conftest import TRANSCRIPTS, role

MAYA_NYU = os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_NYU_Maya_Delgado.pdf")
MAYA_PSC = os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_PSC_Maya_Delgado.pdf")
LIST_TO, LIST_CC = "credit-office@example.edu", "dept-office@example.edu"


@pytest.fixture(autouse=True)
def notification_list(monkeypatch):
    monkeypatch.setenv("SYLLABUS_REQUEST_TO", LIST_TO)
    monkeypatch.setenv("SYLLABUS_REQUEST_CC", LIST_CC)


def upload(client, student_id, path, headers):
    with open(path, "rb") as f:
        r = client.post(f"/api/students/{student_id}/transcripts", files={"file": ("t.pdf", f, "application/pdf")},
                        headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["upload"]["syllabus_request"]


def requests_for(store, ext_id):
    return [e for e in store.audit_log if e["action"] == "syllabus_request" and e["ext_id"] == ext_id]


def test_upload_asks_once_for_maybe_courses_without_a_complete_syllabus(client, fresh_store):
    fresh_store.lines = [ln for ln in fresh_store.lines if ln.student_id != "SYN-24001"]
    req = upload(client, "SYN-24001", MAYA_NYU, role("Student"))
    # PSYCH-UA 25 has no syllabus (TS); PSYCH-UA 10 is a maybe too, but its syllabus is complete: nothing to ask.
    assert req["courses"] == ["PSYCH-UA 25"] and req["status"] == "not_sent"           # no mail service: recorded
    # Maya is a seeded sample student (made-up bu.edu address): never emailed, the list receives it.
    assert (req["to"], req["cc"], req["emailed_student"]) == ([LIST_TO], [LIST_CC], False)
    assert upload(client, "SYN-24001", MAYA_PSC, role("CreditStaff"))["status"] == "none"   # not asked twice
    assert len(requests_for(fresh_store, "NYU|PSYCH-UA 25")) == 1
    assert requests_for(fresh_store, "NYU|PSYCH-UA 25")[0]["actor_role"] == "System"


def test_a_registered_student_is_emailed_at_their_own_address(anon, fresh_store, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    accounts.reset_accounts()
    r = anon.post("/api/auth/register/student", json=dict(name="Sam Patel", email="Sam.Patel@Example.com",
                                                          password="secret1", intended_major="Psychology"))
    sid, tok = r.json()["user"]["student_id"], r.json()["token"]
    req = upload(anon, sid, MAYA_NYU, {"Authorization": f"Bearer {tok}"})
    assert req["courses"] == ["PSYCH-UA 25"] and req["emailed_student"] is True
    assert (req["to"], req["cc"]) == (["sam.patel@example.com"], [LIST_TO, LIST_CC])
    accounts.reset_accounts()


def test_a_failed_email_is_recorded_and_retried_on_the_next_upload(client, fresh_store, monkeypatch):
    def refuse(*a, **k):
        raise notify.NotifyError("The email could not be sent (status Failed)")
    monkeypatch.setattr(notify, "send", refuse)
    fresh_store.lines = [ln for ln in fresh_store.lines if ln.student_id != "SYN-24001"]
    assert upload(client, "SYN-24001", MAYA_NYU, role("Student"))["status"] == "failed"     # the upload still works
    monkeypatch.setattr(notify, "send", lambda *a, **k: "sent")
    req = upload(client, "SYN-24001", MAYA_PSC, role("Student"))
    assert req["status"] == "sent" and "PSYCH-UA 25" in req["courses"]


def test_the_upload_button_no_longer_sends_a_request(client, fresh_store):
    # Requests are automatic (or a staff re-send); uploading a syllabus never emails anyone.
    before = len(fresh_store.audit_log)
    client.get("/api/students/SYN-24001/evaluation", headers=role("Student"))
    assert not [e for e in fresh_store.audit_log[before:] if e["action"] == "syllabus_request"]


# ------------------------------------------------------------------ the evaluator reads the syllabus
def test_evaluator_reads_the_syllabus_and_the_requests(client, fresh_store):
    r = client.get("/api/courses/NYU%7CPSYCH-UA%2010/syllabus", headers=role("Evaluator"))
    assert r.status_code == 200
    body = r.json()
    assert body["state"] == "complete" and body["source"] == "on file" and len(body["text"]) > 200
    assert body["requests"] == []
    fresh_store.lines = [ln for ln in fresh_store.lines if ln.student_id != "SYN-24001"]
    upload(client, "SYN-24001", MAYA_NYU, role("Student"))
    body = client.get("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", headers=role("Evaluator")).json()
    assert body["state"] == "missing" and body["text"] is None
    [req] = body["requests"]
    assert (req["student_id"], req["student_name"], req["automatic"], req["status"]) == \
        ("SYN-24001", "Maya R. Delgado", True, "not_sent")


def test_syllabus_text_is_staff_only_and_flags_injection(client, anon):
    assert client.get("/api/courses/NYU%7CPSYCH-UA%2010/syllabus", headers=role("Student")).status_code == 403
    assert anon.get("/api/courses/NYU%7CPSYCH-UA%2010/syllabus").status_code == 401
    assert client.get("/api/courses/NYU%7CNOPE%20999/syllabus", headers=role("Evaluator")).status_code == 404
    body = client.get("/api/courses/NYU%7CECON-UA%20266/syllabus", headers=role("Department")).json()
    assert body["injection_detected"] is True                     # shown as a warning, text kept for the human


def test_a_department_reads_only_its_own_courses(anon, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    accounts.reset_accounts()
    tok = anon.post("/api/auth/login", json=dict(email="biology.dept@bu.edu", password="admin",
                                                  portal="department")).json()["token"]
    r = anon.get("/api/courses/NYU%7CPSYCH-UA%2010/syllabus", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403
    accounts.reset_accounts()
