"""API contract, role checks, batch threshold, reuse after approval (T15), transcript upload, export, reset."""
import csv
import io
import os

from app import store as store_mod
from app.ingest import parse_transcript

from .conftest import SEED, SYLLABI, TRANSCRIPTS, role

MAYA_NYU = os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_NYU_Maya_Delgado.pdf")
DEC = dict(ext_id="NYU|PSYCH-UA 10", decision="Equivalent", bu_course="CAS PS 211", reason_code="EQ-EVALUATOR",
           reusable=True, evaluator="Evaluator PS-A", catalog_year="2025-26")


def _line(client, sid, ext_id):
    ev = client.get(f"/api/students/{sid}/evaluation").json()
    return next(o for o in ev["lines"] if o["ext_id"] == ext_id)


def test_health_students_rules(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    st = client.get("/api/students").json()
    assert [s["student_id"] for s in st] == ["SYN-24001", "SYN-24002", "SYN-24003", "SYN-24004"]
    assert len(client.get("/api/rules").json()) == 24


TERM_ORDER = {"Winter": 0, "Spring": 1, "Summer": 2, "Fall": 3}


def test_student_profile_fields(client):
    st = {s["student_id"]: s for s in client.get("/api/students").json()}
    s = store_mod.STORE
    for sid, x in st.items():
        assert x["bu_school"] == "College of Arts & Sciences"
        assert x["email"].endswith(("@example.edu", "@example.com"))                       # RFC 2606: unreachable
        assert x["phone"][-8:-2] == "555-01"                                               # fictional 555-0100..0199
        assert x["address"]
        regular = [ln for ln in s.lines_for(sid) if not ln.term.startswith("Summer")]  # summer-only stints do not count
        latest = max(regular, key=lambda ln: (int(ln.term.split()[1]), TERM_ORDER[ln.term.split()[0]]))
        assert x["previous_school"] == latest.school_code                                  # most recent regular term's school
        assert x["previous_school_name"] == s.schools[latest.school_code].name
    assert st["SYN-24001"]["previous_school"] == "NYU"                                     # NYU, not the PSC summer course
    assert st["SYN-24004"]["previous_school"] == "NYU"                                     # NEU -> SOI -> NYU
    ev = client.get("/api/students/SYN-24004/evaluation").json()
    assert ev["student"] == st["SYN-24004"]


def test_audit_log_has_no_contact_data(client, fresh_store):
    client.post("/api/decisions", json=DEC, headers=role("Evaluator"))
    client.post("/api/postings", json={"student_id": "SYN-24001"}, headers=role("Registrar"))
    text = repr(fresh_store.audit_log)
    assert "posting" in text
    for st in fresh_store.students.values():
        assert st.email not in text and st.phone not in text and st.address not in text


def test_evaluation_shape(client):
    ev = client.get("/api/students/SYN-24001/evaluation").json()
    assert len(ev["lines"]) == 6
    keys = {"ext_id", "school_code", "term", "course_code", "title", "credits", "calendar", "grade", "state", "status",
            "bu_status_code", "bu_course", "units", "units_if_approved", "reason_code", "flags", "next_step",
            "ai_tier", "ai_overlap_pct"}
    assert keys <= set(ev["lines"][0])
    assert all(isinstance(v, float) for k, v in ev["totals"].items() if k != "no_credit_lines")
    assert ev["totals"] == {"secured_units": 14.67, "approved_units": 0.0, "pending_units": 8.0, "no_credit_lines": 0,
                            "cap_units": 68.0}
    assert client.get("/api/students/NOPE/evaluation").status_code == 404


def test_cors_for_angular_dev_server(client):
    r = client.options("/api/students", headers={"Origin": "http://localhost:4200", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:4200"


# Role matrix tests live in tests/test_roles.py (ADR 0005).


# ------------------------------------------------------------------ batch (R21)
def test_batch_threshold(client):
    assert client.get("/api/courses/NEU%7CBIOL%203611/recommendation").json()["confidence_pct"] == 87
    r = client.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712", "NEU|BIOL 3611"], "evaluator": "E"},
                    headers=role("Evaluator"))
    assert r.status_code == 422
    assert [i["ext_id"] for i in r.json()["detail"]["items"]] == ["NEU|BIOL 3611"]
    assert not any(d.split == "runtime" for d in store_mod.STORE.decisions)   # nothing saved
    r = client.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712", "NEU|ECON 2706"], "evaluator": "E"},
                    headers=role("Evaluator"))
    assert r.status_code == 201
    saved = r.json()
    assert len(saved) == 2 and len({d["decision_id"] for d in saved}) == 2     # one logged decision per course
    assert all(d["decision"] == "Equivalent" and d["ai_agreed"] for d in saved)


def test_review_queue(client):
    q = client.get("/api/review-queue").json()
    ids = {i["ext_id"] for i in q}
    assert {"NYU|PSYCH-UA 10", "NEU|CS 2700", "NYU|ECON-UA 266", "NEU|BIOL 3611"} <= ids
    item = next(i for i in q if i["ext_id"] == "NYU|PSYCH-UA 10")
    assert item["students"] == ["SYN-24001", "SYN-24004"] and item["syllabus_state"] == "complete"
    assert next(i for i in q if i["ext_id"] == "NEU|CS 2700")["syllabus_state"] == "incomplete"
    assert not any(i["batch_eligible"] for i in q)
    psych = client.get("/api/review-queue", params={"department": "Psychology"}).json()
    assert psych and all(i["department"] == "Psychology" for i in psych)


# ------------------------------------------------------------------ T15 reuse after approval
def test_T15_reuse_after_approval(client):
    assert _line(client, "SYN-24004", "NYU|PSYCH-UA 10")["state"] == "maybe_review"
    r = client.post("/api/decisions", json=DEC, headers=role("Evaluator"))
    assert r.status_code == 201
    d = r.json()
    assert d["ai_suggestion"] == "Evaluator decides CAS PS 211" and d["ai_agreed"] is True
    liam = _line(client, "SYN-24004", "NYU|PSYCH-UA 10")
    # matched instantly (no evaluator step) to CAS PS 211; awaiting posting until the Registrar posts it (v0.3.0)
    assert (liam["state"], liam["bu_course"], liam["units"], liam["bu_status_code"]) == ("approved", "CAS PS 211", 4.0, "TP")
    maya = _line(client, "SYN-24001", "NYU|PSYCH-UA 10")
    assert maya["state"] == "approved" and maya["status"].startswith("Approved")
    assert "NYU|PSYCH-UA 10" not in {i["ext_id"] for i in client.get("/api/review-queue").json()}


def test_non_reusable_decision_only_for_waiting_students(client, fresh_store):
    body = dict(DEC, reusable=False)
    assert client.post("/api/decisions", json=body, headers=role("Evaluator")).status_code == 201
    assert _line(client, "SYN-24004", "NYU|PSYCH-UA 10")["state"] == "approved"
    from app.store import TranscriptLine
    fresh_store.lines.append(TranscriptLine("SYN-24002", "NYU", "Fall 2025", "NYU|PSYCH-UA 10", "PSYCH-UA 10", "Stats", 4, "Semester", "A"))
    assert _line(client, "SYN-24002", "NYU|PSYCH-UA 10")["state"].startswith("maybe")


def test_no_credit_decision(client):
    body = dict(DEC, decision="No credit", bu_course="TFRGEN NOCRDT", reason_code="NC-GRADE")
    client.post("/api/decisions", json=body, headers=role("Evaluator"))
    o = _line(client, "SYN-24001", "NYU|PSYCH-UA 10")
    assert (o["state"], o["bu_status_code"], o["units"]) == ("posted_no_credit", "TX", 0.0)


def test_decision_validation(client):
    assert client.post("/api/decisions", json=dict(DEC, ext_id="NYU|NOPE 1"), headers=role("Evaluator")).status_code == 404
    assert client.post("/api/decisions", json=dict(DEC, decision="Maybe"), headers=role("Evaluator")).status_code == 422
    assert client.post("/api/decisions", json=dict(DEC, reason_code="XX"), headers=role("Evaluator")).status_code == 422


def test_recommendation_never_shows_holdout(client):
    hold = {d.decision_id for d in store_mod.STORE.holdout_decisions}
    for d in store_mod.STORE.holdout_decisions:
        rec = client.get(f"/api/courses/{d.ext_id.replace('|', '%7C')}/recommendation").json()
        assert not {p["decision_id"] for p in rec["past_decisions"]} & hold
    assert client.get("/api/courses/NOPE%7CX/recommendation").status_code == 404


# ------------------------------------------------------------------ transcripts
def test_parse_maya_nyu_transcript():
    t = parse_transcript(MAYA_NYU)
    assert t.institution == "New York University" and t.calendar == "Semester" and t.student_ref == "SYN-24001-NYU"
    assert [(l.term, l.course_code, l.credits, l.grade) for l in t.lines] == [
        ("Fall 2024", "PSYCH-UA 1", 4.0, "A-"), ("Fall 2024", "MATH-UA 121", 4.0, "B+"), ("Fall 2024", "ECON-UA 2", 4.0, "B"),
        ("Spring 2025", "PSYCH-UA 10", 4.0, "A"), ("Spring 2025", "PSYCH-UA 25", 4.0, "B+")]


def test_all_transcripts_parse_to_index_counts():
    for r in csv.DictReader(open(os.path.join(SEED, "transcripts_index.csv"))):
        t = parse_transcript(os.path.join(os.path.dirname(TRANSCRIPTS), r["file"]))
        assert len(t.lines) == int(r["courses"]), r["file"]


def test_upload_transcript(client, fresh_store):
    fresh_store.lines = [ln for ln in fresh_store.lines if ln.student_id != "SYN-24001"]
    assert client.get("/api/students/SYN-24001/evaluation").json()["lines"] == []
    with open(MAYA_NYU, "rb") as f:
        r = client.post("/api/students/SYN-24001/transcripts", files={"file": ("t.pdf", f, "application/pdf")}, headers=role("Student"))
    assert r.status_code == 201
    lines = r.json()["lines"]
    assert [o["course_code"] for o in lines] == ["PSYCH-UA 1", "MATH-UA 121", "ECON-UA 2", "PSYCH-UA 10", "PSYCH-UA 25"]
    assert [o["state"] for o in lines] == ["matched", "matched", "matched", "maybe_review", "maybe_ts"]
    psc = os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_PSC_Maya_Delgado.pdf")
    with open(psc, "rb") as f:
        lines = client.post("/api/students/SYN-24001/transcripts", files={"file": ("t.pdf", f)}, headers=role("CreditStaff")).json()["lines"]
    assert len(lines) == 6 and lines[-1]["units"] == 2.67
    with open(MAYA_NYU, "rb") as f:      # re-upload replaces, does not duplicate
        assert len(client.post("/api/students/SYN-24001/transcripts", files={"file": ("t.pdf", f)}, headers=role("CreditStaff")).json()["lines"]) == 6


def test_transcript_student_id_is_not_compared_with_portal_ids(client, fresh_store):
    # The printed id (SYN-24001-NYU) is the previous school's id: stored, never matched against portal ids.
    with open(MAYA_NYU, "rb") as f:
        r = client.post("/api/students/SYN-24002/transcripts", files={"file": ("t.pdf", f)}, headers=role("CreditStaff"))
    assert r.status_code == 201 and r.json()["upload"]["school_student_id"] == "SYN-24001-NYU"
    assert fresh_store.transcripts[-1].student_id == "SYN-24002"


def _upload(client, sid="SYN-24001", extra=b""):
    """`extra` bytes make a different file (different sha256) with the same parse."""
    with open(MAYA_NYU, "rb") as f:
        data = f.read() + extra
    return client.post(f"/api/students/{sid}/transcripts", files={"file": ("t.pdf", data)}, headers=role("CreditStaff"))


def _parsed_as(monkeypatch, ref, edit=None):
    """Make the upload parse as Maya's NYU transcript with Student ID `ref`, optionally edited."""
    from app import main
    parsed = parse_transcript(MAYA_NYU)
    parsed.student_ref = ref
    if edit:
        edit(parsed)
    monkeypatch.setattr(main, "parse_transcript", lambda _src: parsed)


def test_transcript_upload_is_recorded_with_the_schools_student_id(client, fresh_store):
    r = _upload(client)
    assert r.status_code == 201
    up = r.json()["upload"]
    assert up["school_code"] == "NYU" and up["school_student_id"] == "SYN-24001-NYU" and not up["duplicate"]
    [rec] = fresh_store.transcripts
    assert (rec.transcript_id, rec.student_id, rec.school_code) == (up["transcript_id"], "SYN-24001", "NYU")
    assert rec.school_student_id == "SYN-24001-NYU" and len(rec.sha256) == 64 and rec.course_count == 5
    assert rec.uploaded_by == "CreditStaff"


def test_same_transcript_again_is_a_duplicate(client, fresh_store):
    first = _upload(client).json()
    again = _upload(client)
    assert again.status_code == 201 and again.json()["upload"]["duplicate"] is True
    assert again.json()["upload"]["transcript_id"] == first["upload"]["transcript_id"]
    assert len(fresh_store.transcripts) == 1 and again.json()["lines"] == first["lines"]


def test_previous_schools_student_id_differs_from_the_portal_id(client, fresh_store, monkeypatch):
    _parsed_as(monkeypatch, "N12345678")      # a real NYU id, not the BU / portal id
    r = _upload(client)
    assert r.status_code == 201 and r.json()["upload"]["school_student_id"] == "N12345678"


def test_a_different_id_for_the_same_school_is_rejected(client, fresh_store, monkeypatch):
    _parsed_as(monkeypatch, "N12345678")
    assert _upload(client).status_code == 201
    _parsed_as(monkeypatch, "N99999999", edit=lambda p: p.lines.pop())   # different file, different id
    r = _upload(client)
    assert r.status_code == 422 and "N12345678" in r.json()["detail"]
    assert len(fresh_store.transcripts) == 1


def test_replacing_transcript_reports_what_changed(client, fresh_store, monkeypatch):
    assert _upload(client).json()["upload"]["replaced"] is True   # seeded NYU lines, same courses: no changes
    from app.ingest import ParsedLine

    def edit(p):
        p.lines = [ln for ln in p.lines if ln.course_code != "PSYCH-UA 25"]
        p.lines[0].grade = "B"
        p.lines.append(ParsedLine("Fall 2025", "PSYCH-UA 30", "Social Psychology", 4.0, "A"))
    _parsed_as(monkeypatch, "SYN-24001-NYU", edit)
    up = _upload(client, extra=b"\n% updated copy\n").json()["upload"]
    assert up["replaced"] and not up["duplicate"]
    assert up["added"] == ["PSYCH-UA 30 (Fall 2025)"]
    assert up["removed"] == ["PSYCH-UA 25 (Spring 2025)"]
    assert up["updated"] == ["PSYCH-UA 1 (Fall 2024)"]
    assert len(fresh_store.transcripts) == 2


def test_late_syllabus_upload_moves_ts_to_review(client):
    assert _line(client, "SYN-24001", "NYU|PSYCH-UA 25")["bu_status_code"] == "TS"
    with open(os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf"), "rb") as f:
        r = client.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", files={"file": ("s.pdf", f)})
    assert r.json()["status_code"] == "TP"
    o = _line(client, "SYN-24001", "NYU|PSYCH-UA 25")
    assert (o["state"], o["bu_status_code"], o["ai_tier"], o["ai_overlap_pct"]) == ("maybe_review", "TP", "evaluator_decides", 62)


# ------------------------------------------------------------------ export, metrics, reset
def test_export_csv(client):
    client.post("/api/decisions", json=DEC, headers=role("Evaluator"))
    r = client.get("/api/exports/mybu.csv", params={"student_id": "SYN-24001"}, headers=role("Registrar"))
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert r.headers["content-type"].startswith("text/csv")
    assert list(rows[0]) == ["student_id", "ext_course", "bu_course", "units", "grade"]
    got = {(x["ext_course"], x["bu_course"], x["units"], x["grade"]) for x in rows}
    assert ("PSC|PSY 215", "CAS PS 2TR", "2.67", "T") in got
    assert ("NYU|PSYCH-UA 10", "CAS PS 211", "4.00", "T") in got
    assert not any(x["ext_course"] == "NYU|PSYCH-UA 25" for x in rows)       # pending lines are not exported
    allrows = list(csv.DictReader(io.StringIO(client.get("/api/exports/mybu.csv", headers=role("CreditStaff")).text)))
    assert ("SYN-24002", "NEU|MATH 1341", "TFRGEN NOCRDT", "0.00", "TX") in {tuple(x.values()) for x in allrows}


def test_metrics_endpoint(client):
    m = client.get("/api/evaluation/metrics").json()
    assert m["engine"] == "offline-fallback" and m["n"] == 30
    assert m["strict_agreement"] == 0.6 and m["deferrals"] == 12 and "rows" not in m
    assert 0 <= m["top1_agreement"] <= 1 and 0 <= m["wrong_credit_rate"] <= 1 and "by_tier" in m


def test_demo_reset(client):
    client.post("/api/decisions", json=DEC, headers=role("Evaluator"))
    assert _line(client, "SYN-24004", "NYU|PSYCH-UA 10")["state"] == "approved"
    assert client.post("/api/demo/reset", headers=role("CreditStaff")).status_code == 204
    assert _line(client, "SYN-24004", "NYU|PSYCH-UA 10")["state"] == "maybe_review"


def test_T18_quality_gates_on_holdout(client):
    """Scores (never tunes on) the 30 holdout decisions. Gate definitions: app/evaluation.py."""
    m = client.get("/api/evaluation/metrics").json()
    assert m["top1_agreement"] >= 0.80 and m["wrong_credit_rate"] <= 0.02 and m["gates_met"] is True
