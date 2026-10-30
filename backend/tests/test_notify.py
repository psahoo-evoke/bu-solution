"""'Syllabus needed' emails (app/notify.py + POST /students/{id}/courses/{ext}/syllabus-request).
Azure Communication Services is faked; no network (ADR 0003)."""
import pytest

from app import accounts, main, notify

from .conftest import role

URL = "/api/students/SYN-24001/courses/NYU%7CPSYCH-UA%2025/syllabus-request"   # Maya's course with no syllabus (TS)
TO, CC = "spathur@evoketechnologies.com", "psahoo@evoketechnologies.com"


class FakePoller:
    def __init__(self, status):
        self.status = status

    def result(self):
        return {"status": self.status}


class FakeClient:
    def __init__(self):
        self.sent, self.status, self.fail = [], "Succeeded", False

    def begin_send(self, message):
        if self.fail:
            raise RuntimeError("acs down")
        self.sent.append(message)
        return FakePoller(self.status)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    monkeypatch.setenv("SYLLABUS_REQUEST_TO", TO)
    monkeypatch.setenv("SYLLABUS_REQUEST_CC", CC)
    monkeypatch.setenv("APP_BASE_URL", "https://app.example")
    yield


@pytest.fixture
def acs(monkeypatch):
    client = FakeClient()
    monkeypatch.setenv("AZURE_COMMUNICATION_ENDPOINT", "https://acs.example.communication.azure.com")
    monkeypatch.setenv("ACS_SENDER_ADDRESS", "DoNotReply@example.azurecomm.net")
    monkeypatch.setattr(notify, "_client", lambda: client)
    return client


def test_without_mail_service_the_request_is_recorded_not_sent(client, fresh_store):
    r = client.post(URL, headers=role("Student"))
    assert r.status_code == 201
    body = r.json()
    assert (body["status"], body["to"], body["cc"]) == ("not_sent", [TO], [CC])
    assert fresh_store.audit_log[-1]["action"] == "syllabus_request"


def test_email_goes_to_the_notification_list_only(client, acs):
    r = client.post(URL, headers=role("Department"))
    assert r.status_code == 201 and r.json()["status"] == "sent"
    [msg] = acs.sent
    assert msg["recipients"] == {"to": [{"address": TO}], "cc": [{"address": CC}]}   # never the student's bu.edu address
    assert msg["senderAddress"] == "DoNotReply@example.azurecomm.net"
    subject, text, html = msg["content"]["subject"], msg["content"]["plainText"], msg["content"]["html"]
    assert subject == "Syllabus needed for transfer credit: PSYCH-UA 25 (Maya R. Delgado, SYN-24001)"
    assert "https://app.example/student/SYN-24001" in text and "Requested by Department" in text
    assert "Hello Maya R. Delgado" in html and "<strong>PSYCH-UA 25</strong>" in html
    assert "maya.delgado@bu.edu" not in text + html                             # sample student: never emailed


def test_repeat_clicks_within_15_minutes_send_once(client, acs):
    assert client.post(URL, headers=role("Student")).json()["status"] == "sent"
    assert client.post(URL, headers=role("Student")).json()["status"] == "already_requested"
    assert len(acs.sent) == 1


def test_send_failure_is_502_and_can_be_retried(client, acs):
    acs.fail = True
    r = client.post(URL, headers=role("Student"))
    assert r.status_code == 502 and "could not be sent" in r.json()["detail"]
    acs.fail = False
    assert client.post(URL, headers=role("Student")).json()["status"] == "sent"


def test_failed_status_is_502(client, acs):
    acs.status = "Failed"
    assert client.post(URL, headers=role("Student")).status_code == 502


def test_course_must_be_on_the_students_transcript(client):
    r = client.post("/api/students/SYN-24002/courses/NYU%7CPSYCH-UA%2025/syllabus-request", headers=role("Student"))
    assert r.status_code == 404 and "not on SYN-24002" in r.json()["detail"]
    assert client.post("/api/students/SYN-99999/courses/NYU%7CPSYCH-UA%2025/syllabus-request").status_code == 404


def test_roles_that_cannot_upload_a_syllabus_cannot_request_one(client):
    for r in ("Registrar", "Advisor"):
        assert client.post(URL, headers=role(r)).status_code == 403


def test_portal_student_only_for_own_record(anon, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    accounts.reset_accounts()
    tok = anon.post("/api/auth/login", json=dict(email="jordan.reyes@bu.edu", password="admin", portal="student")).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    assert anon.post(URL, headers=h).status_code == 403                    # Maya's course, Jordan's session
    accounts.reset_accounts()


# ------------------------------------------------------------------ Logic App webhook (Office 365 connector)
class FakeResp:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def webhook(monkeypatch):
    import json
    import urllib.error
    import urllib.request

    calls = {"bodies": [], "status": 200, "error": None}

    def fake_urlopen(req, timeout):
        if calls["error"]:
            raise urllib.error.HTTPError(req.full_url, calls["error"], "boom", {}, None)
        calls["bodies"].append(json.loads(req.data))
        calls["url"] = req.full_url
        return FakeResp(calls["status"])

    monkeypatch.setenv("NOTIFY_WEBHOOK_URL", "https://logic.example/trigger?sig=SECRET")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return calls


def test_webhook_sends_to_and_cc(client, webhook):
    r = client.post(URL, headers=role("Student"))
    assert r.status_code == 201 and r.json()["status"] == "sent"
    [body] = webhook["bodies"]
    assert (body["to"], body["cc"]) == (TO, CC)
    assert body["subject"] == "Syllabus needed for transfer credit: PSYCH-UA 25 (Maya R. Delgado, SYN-24001)" and "<strong>" in body["html"]


def test_webhook_failure_is_502_and_hides_the_url(client, webhook, caplog):
    webhook["error"] = 502
    r = client.post(URL, headers=role("Student"))
    assert r.status_code == 502 and "answered 502" in r.json()["detail"]
    assert "SECRET" not in caplog.text and "SECRET" not in r.text


def test_acs_wins_when_both_are_configured(client, webhook, acs):
    assert client.post(URL, headers=role("Student")).json()["status"] == "sent"
    assert len(acs.sent) == 1 and webhook["bodies"] == []
