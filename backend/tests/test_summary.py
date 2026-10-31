"""GET /students/summary: the advisor caseload and financial aid view (read-only, no contact data, no AI call)."""
import datetime as dt

from app.rules import CAP_UNITS, evaluate_student, summarize_student, totals, transfer_deadline

from .conftest import role

ROW_KEYS = {"student_id", "name", "intended_major", "bu_school", "bu_start_term", "previous_school_name", "course_count",
            "secured_units", "approved_units", "pending_units", "projected_units", "no_credit_lines", "cap_units",
            "awaiting_student", "awaiting_evaluator", "awaiting_posting", "transfer_deadline", "days_to_deadline",
            "past_deadline", "advisory_flags", "attention", "attention_reasons", "aid_status"}


def _rows(client, who="Advisor"):
    r = client.get("/api/students/summary", headers=role(who))
    assert r.status_code == 200
    return {row["student_id"]: row for row in r.json()}


def test_summary_matches_the_status_page_totals(anon, fresh_store):
    rows = _rows(anon)
    assert set(rows) == set(fresh_store.students)
    for sid, row in rows.items():
        t = totals(evaluate_student(fresh_store, fresh_store.students[sid]))
        assert (row["secured_units"], row["pending_units"], row["no_credit_lines"]) == (
            t["secured_units"], t["pending_units"], t["no_credit_lines"])
        assert row["projected_units"] <= CAP_UNITS


def test_summary_has_no_contact_data(anon):
    for row in _rows(anon).values():
        assert set(row) == ROW_KEYS
        assert not {"email", "phone", "address"} & set(row)


def test_only_advisor_financial_aid_and_credit_staff_may_read_it(anon):
    for who in ("Advisor", "FinancialAid", "CreditStaff"):
        assert anon.get("/api/students/summary", headers=role(who)).status_code == 200
    for who in ("Student", "Evaluator", "Department", "Registrar"):
        assert anon.get("/api/students/summary", headers=role(who)).status_code == 403


def test_financial_aid_can_read_the_shared_endpoints_but_not_write(anon):
    h = role("FinancialAid")
    assert anon.get("/api/students", headers=h).status_code == 200
    assert anon.get("/api/students/SYN-24001/evaluation", headers=h).status_code == 200
    assert anon.post("/api/postings", json={}, headers=h).status_code == 403
    assert anon.post("/api/demo/reset", headers=h).status_code == 403


def test_open_items_make_the_aid_status_provisional(anon):
    row = _rows(anon, "FinancialAid")["SYN-24001"]          # Maya: 2 "maybe" lines at seed
    assert row["aid_status"] == "provisional"
    assert row["awaiting_student"] + row["awaiting_evaluator"] + row["awaiting_posting"] > 0
    assert row["pending_units"] > 0


def test_student_without_a_transcript(fresh_store):
    st = fresh_store.students["SYN-24001"]
    fresh_store.lines = [ln for ln in fresh_store.lines if ln.student_id != st.student_id]
    s = summarize_student(fresh_store, st)
    assert (s["attention"], s["aid_status"], s["course_count"], s["secured_units"]) == ("no_transcript", "no_data", 0, 0)
    assert s["attention_reasons"] == ["No transcript on file yet"]


def test_everything_posted_is_confirmed_and_on_track(fresh_store):
    st = fresh_store.students["SYN-24001"]
    keep = [ln for ln in fresh_store.lines if ln.student_id != st.student_id]
    done = [ln for ln in fresh_store.lines_for(st.student_id)
            if next(o for o in evaluate_student(fresh_store, st) if o["ext_id"] == ln.ext_id and o["term"] == ln.term)["state"]
            in ("matched", "posted_no_credit")]
    fresh_store.lines = keep + done
    s = summarize_student(fresh_store, st)
    assert (s["attention"], s["aid_status"], s["pending_units"]) == ("on_track", "confirmed", 0)


def test_deadline_drives_attention(fresh_store):
    st = fresh_store.students["SYN-24001"]
    deadline = transfer_deadline(st)
    assert deadline == dt.date(2027, 9, 1)                  # Fall 2026 start
    far = summarize_student(fresh_store, st, today=dt.date(2026, 10, 30))
    assert not far["past_deadline"] and far["days_to_deadline"] > 60
    near = summarize_student(fresh_store, st, today=deadline - dt.timedelta(days=10))
    assert near["attention"] == "action_needed" and "Transfer deadline in 10 days" in near["attention_reasons"]
    past = summarize_student(fresh_store, st, today=deadline + dt.timedelta(days=1))
    assert past["past_deadline"] and "Past the one-year transfer deadline" in past["attention_reasons"]


def test_winter_style_start_uses_january(fresh_store):
    st = fresh_store.students["SYN-24001"]
    st.bu_start_term = "Spring 2026"
    assert transfer_deadline(st) == dt.date(2027, 1, 1)


def test_projected_units_never_exceed_the_cap(fresh_store):
    for st in fresh_store.students.values():
        assert summarize_student(fresh_store, st)["projected_units"] <= CAP_UNITS
    liam = summarize_student(fresh_store, fresh_store.students["SYN-24004"])   # showcases the 68-unit cap
    assert liam["projected_units"] <= CAP_UNITS
