"""In-app notifications for students (app/notifications.py, GET/POST /students/{id}/notifications[/seen])."""
import os

from app import accounts

from .conftest import SYLLABI, TRANSCRIPTS, role

MAYA_NYU = os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_NYU_Maya_Delgado.pdf")
URL = "/api/students/SYN-24001/notifications"
DECISION = dict(ext_id="NYU|PSYCH-UA 10", decision="Equivalent", bu_course="CAS PS 211", reason_code="EQ-EVALUATOR",
                evaluator="Dana Evaluator", note="Internal: strong statistics overlap")


def items(client, url=URL, headers=None):
    return client.get(url, headers=headers or role("Student")).json()


def kinds(body):
    return [i["kind"] for i in body["items"]]


def test_nothing_happened_yet(client):
    body = items(client)
    assert body == dict(items=[], unread=0, seen_at=None)


def test_the_students_journey_shows_up_newest_first(client, fresh_store):
    fresh_store.lines = [ln for ln in fresh_store.lines if ln.student_id != "SYN-24001"]
    with open(MAYA_NYU, "rb") as f:
        client.post("/api/students/SYN-24001/transcripts", files={"file": ("t.pdf", f, "application/pdf")},
                    headers=role("Student"))
    with open(os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf"), "rb") as f:
        client.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", files={"file": ("s.pdf", f, "application/pdf")},
                    headers=role("Student"))
    assert client.post("/api/decisions", json=DECISION, headers=role("Evaluator")).status_code == 201
    body = items(client)
    # the decision posts straight away: one "posted" item, not a "decision" item repeating it
    assert kinds(body) == ["posted", "syllabus_received", "syllabus_request", "transcript"]
    assert body["unread"] == 4 and all(i["unread"] for i in body["items"])
    by = {i["kind"]: i for i in body["items"]}
    assert by["transcript"]["title"] == "Transcript received" and "5 courses evaluated" in by["transcript"]["body"]
    assert by["syllabus_request"]["title"] == "Syllabus needed for NYU PSYCH-UA 25"
    assert by["syllabus_received"]["title"] == "Syllabus received for NYU PSYCH-UA 25"
    assert by["posted"]["body"] == "CAS PS 211, 4 units, is now on your BU record."
    # never internal details: staff email lists, the evaluator's name or note
    text = str(body)
    assert "Dana" not in text and "Internal" not in text and "@" not in text


def test_a_reusable_decision_reaches_every_student_with_the_course_only(client, fresh_store):
    client.post("/api/decisions", json=DECISION, headers=role("Evaluator"))
    assert kinds(items(client, "/api/students/SYN-24004/notifications")) == ["posted"]     # Liam has PSYCH-UA 10 too
    assert kinds(items(client, "/api/students/SYN-24002/notifications")) == []            # Jordan does not


def test_a_decision_without_credit_is_still_announced(client, fresh_store):
    client.post("/api/decisions", json=dict(DECISION, decision="No credit", bu_course="TFRGEN NOCRDT",
                                            reason_code="NC-GRADE"), headers=role("Evaluator"))
    [item] = items(client)["items"]
    assert item["kind"] == "decision" and item["body"] == "It does not transfer (no credit)."


def test_an_unposted_decision_is_announced_until_it_is_posted(client, fresh_store, monkeypatch):
    from app import main
    monkeypatch.setattr(main, "_auto_post", lambda role, ext_ids: None)       # as if the posting write failed
    client.post("/api/decisions", json=DECISION, headers=role("Evaluator"))
    [item] = items(client)["items"]
    assert item["kind"] == "decision" and item["body"].endswith("The Registrar posts it to your BU record next.")
    client.post("/api/postings", json={"student_id": "SYN-24001"}, headers=role("Registrar"))
    assert kinds(items(client)) == ["posted"]


def test_opening_marks_read_and_staff_views_do_not(client, fresh_store):
    client.post("/api/decisions", json=DECISION, headers=role("Evaluator"))
    assert items(client, headers=role("Evaluator"))["unread"] == 1          # staff look: still unread
    assert items(client)["unread"] == 1
    r = client.post(URL + "/seen", headers=role("Student"))
    assert r.status_code == 200 and r.json()["unread"] == 0 and r.json()["seen_at"]
    assert fresh_store.notification_seen["SYN-24001"] == r.json()["seen_at"]
    client.post("/api/decisions", json=dict(DECISION, bu_course="CAS PS 205"), headers=role("Evaluator"))
    body = items(client)
    assert body["unread"] == 1 and [i["unread"] for i in body["items"]] == [True, False]


def test_only_the_student_marks_read(client):
    for r in ("Evaluator", "CreditStaff", "Registrar"):
        assert client.post(URL + "/seen", headers=role(r)).status_code == 403
    assert client.post("/api/students/SYN-99999/notifications/seen", headers=role("Student")).status_code == 404
    assert client.get("/api/students/SYN-99999/notifications", headers=role("Student")).status_code == 404


def test_a_portal_student_reads_only_their_own(anon, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    accounts.reset_accounts()
    tok = anon.post("/api/auth/login", json=dict(email="jordan.reyes@bu.edu", password="admin", portal="student")).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert anon.get("/api/students/SYN-24002/notifications", headers=h).status_code == 200
    assert anon.get(URL, headers=h).status_code == 403
    assert anon.post(URL + "/seen", headers=h).status_code == 403
    accounts.reset_accounts()
