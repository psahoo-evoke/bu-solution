"""Contract v0.3.0: approved vs posted, POST /postings, decision validation (security F-02), parse time-out (F-04)."""
import csv
import io
import os
import time

import pytest

from .conftest import SYLLABI, TRANSCRIPTS, role

DEC = dict(ext_id="NYU|PSYCH-UA 10", decision="Equivalent", bu_course="CAS PS 211", reason_code="EQ-EVALUATOR",
           reusable=True, evaluator="Evaluator PS-A", catalog_year="2025-26")


def _ev(client, sid):
    return client.get(f"/api/students/{sid}/evaluation").json()


def _line(ev, ext_id):
    return next(o for o in ev["lines"] if o["ext_id"] == ext_id)


def test_demo_step8_approve_posts_straight_away(client):
    """Demo step 8: Maya's PSYCH-UA 10 approved -> posted at once, so Maya sees it secured (T); Liam's line is
    reused (R10) and posted too. The Registrar's POST /postings has nothing left to do."""
    before = _ev(client, "SYN-24001")["totals"]
    assert before["secured_units"] == 14.67 and before["pending_units"] == 8.0
    assert client.post("/api/decisions", json=DEC, headers=role("Evaluator")).status_code == 201

    maya = _ev(client, "SYN-24001")
    m = _line(maya, "NYU|PSYCH-UA 10")
    assert (m["state"], m["bu_status_code"], m["bu_course"], m["units"]) == ("posted", "T", "CAS PS 211", 4.0)
    assert m["status"] == "Posted – credit secured"
    assert maya["totals"]["secured_units"] == 18.67 and maya["totals"]["approved_units"] == 0.0
    assert maya["totals"]["pending_units"] == 4.0                                    # only PSYCH-UA 25 left

    liam = _line(_ev(client, "SYN-24004"), "NYU|PSYCH-UA 10")                        # reused instantly (R10)
    assert (liam["bu_course"], liam["units"], liam["reason_code"]) == ("CAS PS 211", 4.0, "EQ-EVALUATOR")
    assert (liam["state"], liam["bu_status_code"]) == ("posted", "T")

    # the export lists the posted credit
    rows = list(csv.DictReader(io.StringIO(client.get("/api/exports/mybu.csv?student_id=SYN-24001",
                                                       headers=role("Registrar")).text)))
    assert dict(student_id="SYN-24001", ext_course="NYU|PSYCH-UA 10", bu_course="CAS PS 211", units="4.00",
                grade="T") in rows
    # nothing left for the Registrar to post
    r = client.post("/api/postings", json={"student_id": "SYN-24001"}, headers=role("Registrar"))
    assert r.status_code == 201 and r.json()["posted"] == 0


def test_decision_posts_for_every_student_and_is_audited(client, fresh_store):
    r = client.post("/api/decisions", json=DEC, headers=role("Department"))
    assert {k[0] for k in fresh_store.postings} == {"SYN-24001", "SYN-24004"}
    assert all(p["decision_id"] == r.json()["decision_id"] for p in fresh_store.postings.values())
    posts = [a for a in fresh_store.audit_log if a["action"] == "posting"]
    assert len(posts) == 2 and all(a["actor_role"] == "Department" for a in posts)
    assert all(a["after"]["decision_id"] == r.json()["decision_id"] for a in posts)
    assert client.post("/api/postings", headers=role("CreditStaff")).json()["posted"] == 0   # no body: all students


def test_only_the_decided_course_is_posted(client, fresh_store):
    """An approved line of another course (posting failed earlier) is the Registrar's to post, not this decision's."""
    client.post("/api/decisions", json=DEC)
    fresh_store.postings.clear()                                            # PSYCH-UA 10 back to approved
    batch = client.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "E"})
    assert batch.status_code == 201
    assert "NYU|PSYCH-UA 10" not in {k[1] for k in fresh_store.postings}
    assert _line(_ev(client, "SYN-24001"), "NYU|PSYCH-UA 10")["state"] == "approved"


def test_failed_posting_keeps_the_decision_and_leaves_it_for_the_registrar(client, fresh_store, monkeypatch):
    from app import db
    monkeypatch.setattr(db, "enabled", lambda: True)
    monkeypatch.setattr(db, "save_decisions", lambda ds: None)
    monkeypatch.setattr(db, "save_audit", lambda e: None)

    def down(_):
        raise db.DBError("database unavailable")
    monkeypatch.setattr(db, "save_postings", down)
    assert client.post("/api/decisions", json=DEC, headers=role("Evaluator")).status_code == 201   # decision stands
    assert fresh_store.postings == {}
    m = _line(_ev(client, "SYN-24001"), "NYU|PSYCH-UA 10")
    assert (m["state"], m["bu_status_code"]) == ("approved", "TP")                 # awaiting posting

    monkeypatch.setattr(db, "save_postings", lambda items: None)
    r = client.post("/api/postings", headers=role("Registrar"))
    assert r.status_code == 201 and r.json()["posted"] == 2
    assert _line(_ev(client, "SYN-24001"), "NYU|PSYCH-UA 10")["bu_status_code"] == "T"


def test_postings_validation_and_reset(client, fresh_store):
    assert client.post("/api/postings", json={"student_id": "NOPE-1"}, headers=role("Registrar")).status_code == 404
    assert client.post("/api/postings", json={"student_id": "x;y"}, headers=role("Registrar")).status_code == 422
    client.post("/api/decisions", json=DEC)                                 # posts straight away
    assert fresh_store.postings
    client.post("/api/demo/reset", headers=role("Registrar"))
    assert fresh_store.postings == {}
    assert _line(_ev(client, "SYN-24001"), "NYU|PSYCH-UA 10")["state"] == "maybe_review"


def test_newer_decision_is_posted_with_its_new_code(client, fresh_store):
    client.post("/api/decisions", json=DEC)
    newer = dict(DEC, decision="Elective", bu_course="CAS PS 2TR", reason_code="EL-PARTIAL", catalog_year="2027-28")
    r = client.post("/api/decisions", json=newer)
    assert r.status_code == 201
    m = _line(_ev(client, "SYN-24001"), "NYU|PSYCH-UA 10")
    assert (m["state"], m["bu_course"]) == ("posted", "CAS PS 2TR")
    assert fresh_store.postings[("SYN-24001", "NYU|PSYCH-UA 10", m["term"])]["decision_id"] == r.json()["decision_id"]


def test_no_credit_decision_posts_nothing(client, fresh_store):
    client.post("/api/decisions", json=dict(DEC, decision="No credit", bu_course="TFRGEN NOCRDT", reason_code="NC-GRADE"))
    assert fresh_store.postings == {}
    assert _line(_ev(client, "SYN-24001"), "NYU|PSYCH-UA 10")["state"] == "posted_no_credit"


def test_seed_matches_stay_secured(client):
    ev = _ev(client, "SYN-24001")
    assert _line(ev, "NYU|PSYCH-UA 1")["state"] == "matched" and _line(ev, "NYU|PSYCH-UA 1")["bu_status_code"] == "T"


# ------------------------------------------------------------------ decision validation (F-02)
@pytest.mark.parametrize("change", [
    dict(bu_course='=HYPERLINK("http://x")'),                                       # pattern
    dict(bu_course="CAS PS 999"),                                                   # not in catalogue
    dict(bu_course="CAS PS 2TR"),                                                   # Equivalent with a TR code
    dict(bu_course="TFRGEN NOCRDT"),                                                # Equivalent with no-credit code
    dict(decision="Elective", bu_course="CAS PS 211", reason_code="EL-PARTIAL"),    # Elective needs TR
    dict(decision="No credit", bu_course="CAS PS 2TR", reason_code="NC-GRADE"),     # No credit needs NOCRDT
    dict(decision="No credit", bu_course="TFRGEN NOCRDT", reason_code="EQ-CONTENT"),  # reason/decision mismatch
    dict(reason_code="EL-PARTIAL"),                                                 # Equivalent with elective code
    dict(reason_code="PD-TS"),                                                      # pending code is no decision
    dict(reason_code="NOPE"),                                                       # unknown
])
def test_decision_validation_rejects(client, fresh_store, change):
    r = client.post("/api/decisions", json=dict(DEC, **change))
    assert r.status_code == 422, r.text
    assert not any(d.split == "runtime" for d in fresh_store.decisions)


@pytest.mark.parametrize("change", [
    {},
    dict(decision="Elective", bu_course="CAS PS 2TR", reason_code="EL-PARTIAL"),
    dict(decision="Elective", bu_course="TFRGEN 1TR", reason_code="EL-NOEQUIV"),
    dict(decision="No credit", bu_course="TFRGEN NOCRDT", reason_code="NC-GRADE"),
])
def test_decision_validation_accepts(client, change):
    assert client.post("/api/decisions", json=dict(DEC, **change)).status_code == 201


def test_batch_decisions_pass_validation(client):
    r = client.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712", "NEU|ECON 2706"], "evaluator": "E"})
    assert r.status_code == 201 and [d["reason_code"] for d in r.json()] == ["EQ-CONTENT", "EQ-CONTENT"]


# ------------------------------------------------------------------ parse off the event loop with a time-out (F-04)
def test_slow_pdf_parse_times_out_with_422(client, monkeypatch):
    import app.main as main_mod

    def slow(_data):
        time.sleep(1.0)
        return ""
    monkeypatch.setattr(main_mod, "PDF_PARSE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(main_mod, "pdf_text", slow)
    monkeypatch.setattr(main_mod, "parse_transcript", slow)
    with open(os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf"), "rb") as f:
        r = client.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", files={"file": ("s.pdf", f, "application/pdf")})
    assert r.status_code == 422 and "too long" in r.json()["detail"]
    with open(os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_NYU_Maya_Delgado.pdf"), "rb") as f:
        r = client.post("/api/students/SYN-24001/transcripts", files={"file": ("t.pdf", f)}, headers=role("Student"))
    assert r.status_code == 422


def test_parse_runs_off_the_event_loop(client, monkeypatch):
    import threading

    import app.main as main_mod
    seen = {}
    real = main_mod.pdf_text

    def spy(data):
        seen["thread"] = threading.current_thread() is threading.main_thread()
        return real(data)
    monkeypatch.setattr(main_mod, "pdf_text", spy)
    with open(os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf"), "rb") as f:
        assert client.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", files={"file": ("s.pdf", f)}).status_code == 201
    assert seen["thread"] is False


def test_syllabus_filename_not_kept(client, fresh_store):
    """Security F-06: the client filename is never stored."""
    with open(os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf"), "rb") as f:
        client.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", files={"file": ("../../etc/passwd", f)})
    name = fresh_store.syllabi["NYU|PSYCH-UA 25"].file
    assert name.startswith("upload-") and "passwd" not in name and "/" not in name
