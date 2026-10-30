"""Azure OpenAI engine with a fake client: output validation (checklist section 3), prompt PII (section 4),
fallback, and lazy azure-identity import. No network."""
import dataclasses
import json
import re
import sys

import pytest

from app import matcher
from app import store as store_mod


@pytest.fixture
def azure(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com")
    calls = []

    def install(reply):
        def fake(messages):
            calls.append(messages)
            return reply(messages) if callable(reply) else reply
        monkeypatch.setattr(matcher, "llm_client", fake)
        matcher.clear_cache()                 # a new fake model must not see the previous one's cached answers
        return calls
    return install


def _course(ext_id="NYU|ECON-UA 266"):
    s = store_mod.STORE
    return s.ext_courses[ext_id], list(s.bu_courses.values()), s.syllabi.get(ext_id)


def _shortlist_codes(messages):
    return [c["bu_code"] for c in json.loads(messages[1]["content"].split("Candidate BU courses (trusted):\n")[1])]


def test_valid_output_is_used(azure):
    seen = {}

    def reply(messages):
        codes = _shortlist_codes(messages)
        seen["codes"] = codes
        b0, b1 = (store_mod.STORE.bu_courses[c] for c in codes[:2])
        return json.dumps({"candidates": [
            {"bu_code": codes[0], "overlap_pct": 85, "tier": "equivalent", "covered": b0.learning_outcomes[:2] + ["invented"]},
            {"bu_code": codes[1], "overlap_pct": 140, "covered": b1.learning_outcomes * 2},   # duplicates count once
            {"bu_code": codes[2], "overlap_pct": -3}]})
    azure(reply)
    rec = matcher.recommend(*_course())
    assert rec["engine"] == "azure-openai"
    by = {c["bu_code"]: c for c in rec["candidates"]}
    c0, c1, c2 = (by[code] for code in seen["codes"][:3])
    n0 = len(store_mod.STORE.bu_courses[c0["bu_code"]].learning_outcomes)
    assert c0["covered"] == store_mod.STORE.bu_courses[c0["bu_code"]].learning_outcomes[:2]
    assert c0["overlap_pct"] == round(100 * 2 / n0)              # from the covered list, not the model's 85
    assert c1["overlap_pct"] == 100 and c1["missing"] == []
    assert c2["overlap_pct"] == 0 and c2["covered"] == []
    for c in rec["candidates"]:                                   # the % always matches the lists shown
        assert c["overlap_pct"] == round(100 * len(c["covered"]) / (len(c["covered"]) + len(c["missing"])))
        assert c["tier"] == matcher.tier_of(c["overlap_pct"])


def test_description_match_comes_from_the_model_with_offline_fallback(azure):
    seen = {}

    def reply(messages):
        codes = seen["codes"] = _shortlist_codes(messages)
        return json.dumps({"candidates": [
            {"bu_code": codes[0], "overlap_pct": 0, "description_match_pct": 140},      # clamped
            {"bu_code": codes[1], "overlap_pct": 0, "description_match_pct": 42},
            {"bu_code": codes[2], "overlap_pct": 0, "description_match_pct": "high"},   # not a number: offline
            {"bu_code": codes[3], "overlap_pct": 0}]})                                  # missing: offline
    azure(reply)
    course, bus, syl = _course()
    rec = matcher.recommend(course, bus, syl)
    assert rec["engine"] == "azure-openai"             # a bad description figure does not reject the answer
    by = {c["bu_code"]: c for c in matcher._azure_rank(course, bus, matcher.sanitize(syl.text))[0]}
    s = store_mod.STORE.bu_courses
    codes = seen["codes"]
    assert by[codes[0]]["description_match_pct"] == 100
    assert by[codes[1]]["description_match_pct"] == 42
    for code in codes[2:4]:
        assert by[code]["description_match_pct"] == matcher.description_match(course, s[code])


def test_prompt_carries_bu_descriptions(azure):
    calls = azure(_top_at(50))
    matcher.recommend(*_course())
    cands = json.loads(calls[-1][1]["content"].split("Candidate BU courses (trusted):\n")[1])
    assert all(c["description"] == store_mod.STORE.bu_courses[c["bu_code"]].description for c in cands)
    assert "description_match_pct" in calls[-1][0]["content"]


def test_offline_description_match():
    course = store_mod.STORE.ext_courses["NYU|ECON-UA 266"]
    b = next(iter(store_mod.STORE.bu_courses.values()))
    named = dataclasses.replace(course, description=" and ".join(b.topics[:2]) + ".")
    assert matcher.description_match(named, b) == round(100 * 2 / len(b.topics))
    assert matcher.description_match(dataclasses.replace(course, description=""), b) is None
    assert matcher.description_match(course, dataclasses.replace(b, topics=[])) is None


def test_model_overlap_is_kept_only_without_bu_outcomes():
    b = next(iter(store_mod.STORE.bu_courses.values()))
    bare = dataclasses.replace(b, learning_outcomes=[])
    out = matcher.validate_llm_output(json.dumps({"candidates": [{"bu_code": b.bu_code, "overlap_pct": 140}]}),
                                      [{"bu_code": b.bu_code}], {b.bu_code: bare})
    assert out[0]["overlap_pct"] == 100 and out[0]["covered"] == [] and out[0]["missing"] == []


@pytest.mark.parametrize("bad", [
    "not json at all",
    json.dumps([1, 2]),
    json.dumps({"candidates": []}),
    json.dumps({"candidates": [{"bu_code": "CAS ZZ 999", "overlap_pct": 90}]}),        # not a search candidate
    json.dumps({"candidates": [{"bu_code": "__FIRST__", "overlap_pct": "ninety"}]}),
    json.dumps({"candidates": [{"bu_code": "__FIRST__", "overlap_pct": 90, "tier": "credit_granted"}]}),
    json.dumps({"candidates": [{"bu_code": "__FIRST__", "overlap_pct": True}]}),
])
def test_invalid_output_falls_back_to_offline(azure, bad):
    azure(lambda m: bad.replace("__FIRST__", _shortlist_codes(m)[0]))
    rec = matcher.recommend(*_course())
    offline_top = rec["candidates"][0]
    assert rec["engine"] == "offline-fallback"
    assert (offline_top["bu_code"], offline_top["overlap_pct"], offline_top["tier"]) == ("CAS EC 204", 62, "evaluator_decides")


def test_client_error_falls_back(azure):
    def boom(messages):
        raise TimeoutError("quota")
    azure(boom)
    assert matcher.recommend(*_course())["engine"] == "offline-fallback"


def test_injection_cannot_raise_tier_through_the_model(azure):
    """Even if a compromised model obeys the injected line, it can only score candidates; tier comes from the
    clamped overlap, and the injection flag is still raised for the evaluator."""
    azure(lambda m: json.dumps({"candidates": [{"bu_code": _shortlist_codes(m)[0], "overlap_pct": 100}]}))
    rec = matcher.recommend(*_course())
    assert rec["injection_detected"] is True
    assert rec["engine"] == "azure-openai"
    # the injected sentence never reached the prompt
    calls = azure(lambda m: json.dumps({"candidates": [{"bu_code": _shortlist_codes(m)[0], "overlap_pct": 60}]}))
    matcher.recommend(*_course())
    assert "ignore all previous instructions" not in calls[-1][1]["content"].lower()


def test_prompt_contains_course_data_only(azure):
    calls = azure(lambda m: "bad")       # forces fallback, but the prompt is still captured
    s = store_mod.STORE
    for sid in s.students:
        for ln in s.lines_for(sid):
            matcher.recommend(s.ext_courses[ln.ext_id], list(s.bu_courses.values()), s.syllabi.get(ln.ext_id))
    assert calls
    names = [n for st in s.students.values() for n in st.name.replace(".", "").split() if len(n) > 2]
    for msgs in calls:
        text = json.dumps(msgs)
        assert not re.search(r"SYN-\d+", text)
        assert "gt_" not in text and "gt_counterpart" not in text
        assert not any(re.search(rf"\b{re.escape(n)}\b", text) for n in names)
        for st in s.students.values():                       # contact fields are personal data: never in a prompt
            assert st.email and st.phone and st.address
            assert st.email not in text and st.email.split("@")[0] not in text
            assert st.phone not in text and st.phone.replace("-", "") not in text
            assert st.address not in text and st.address.split(",")[0] not in text
        assert '"grade"' not in text
        user = msgs[1]["content"]
        assert user.startswith("<course_data>") and "</course_data>" in user
        assert "UNTRUSTED DATA" in msgs[0]["content"]
        # Workbook notes name the expected BU course: staff reference only, never a model input. One-word notes
        # ("Algorithms.") also occur in ordinary descriptions, so only the distinctive ones are checked.
        long_notes = [n["note"] for ns in s.workbook_notes.values() for n in ns if len(n["note"]) > 40]
        assert long_notes and not any(n in text for n in long_notes)


def _top_at(pct):
    def reply(m):
        code = _shortlist_codes(m)[0]
        outcomes = store_mod.STORE.bu_courses[code].learning_outcomes
        covered = outcomes[:round(len(outcomes) * pct / 100)]
        return json.dumps({"candidates": [{"bu_code": code, "overlap_pct": pct, "covered": covered}]})
    return reply


def test_same_prompt_is_answered_from_cache(azure):
    calls = azure(_top_at(70))
    first = matcher.recommend(*_course())
    expected = first["candidates"][0]["overlap_pct"]
    assert expected > 0
    first["candidates"][0]["overlap_pct"] = 1            # callers may mutate what they get back
    first["past_decisions"] = ["x"]
    second = matcher.recommend(*_course())
    assert len(calls) == 1
    assert second["engine"] == "azure-openai"
    assert second["candidates"][0]["overlap_pct"] == expected and "past_decisions" not in second


def test_changed_syllabus_is_a_new_model_call(azure):
    from app.store import SyllabusRecord
    calls = azure(_top_at(70))
    course, bus, syl = _course()
    matcher.recommend(course, bus, syl)
    new = SyllabusRecord(ext_id=course.ext_id, state="complete", text=syl.text + "\nWeek 15: panel data methods.")
    matcher.recommend(course, bus, new)
    assert len(calls) == 2


def test_wait_false_answers_offline_now_and_warms_the_model_for_next_time(azure):
    """Status-page hints (wait=False) never block on the model: offline now, the model ranking in the background,
    then the cached model ranking. A reload while it is still running does not start a second call."""
    import threading
    release, started = threading.Event(), threading.Event()

    def slow(messages):
        started.set()
        assert release.wait(5)
        return _top_at(70)(messages)
    calls = azure(slow)
    first = matcher.recommend(*_course(), wait=False)
    assert first["engine"] == "offline-fallback"
    assert started.wait(5)
    assert matcher.recommend(*_course(), wait=False)["engine"] == "offline-fallback"   # still running: no 2nd call
    assert len(calls) == 1
    release.set()
    for t in [t for t in threading.enumerate() if t.name == "rank-warm"]:
        t.join(5)
    warmed = matcher.recommend(*_course(), wait=False)
    assert warmed["engine"] == "azure-openai" and len(calls) == 1


def test_a_failed_background_call_is_retried_later(azure):
    import threading
    state = {"fail": True}

    def flaky(messages):
        if state["fail"]:
            raise TimeoutError("quota")
        return _top_at(70)(messages)
    calls = azure(flaky)
    assert matcher.recommend(*_course(), wait=False)["engine"] == "offline-fallback"
    for t in [t for t in threading.enumerate() if t.name == "rank-warm"]:
        t.join(5)
    state["fail"] = False
    assert matcher.recommend(*_course())["engine"] == "azure-openai"           # a waiting call retries the model
    assert len(calls) == 2


def test_status_page_does_not_wait_on_the_model(azure, client):
    """Right after a syllabus upload the status page must not wait 15-20 s on a model call (the rows looked stuck)."""
    import time
    from .conftest import role

    def slow(messages):
        time.sleep(1.5)
        return _top_at(70)(messages)
    azure(slow)
    t0 = time.monotonic()
    r = client.get("/api/students/SYN-24001/evaluation", headers=role("Student"))
    assert r.status_code == 200 and time.monotonic() - t0 < 1.5
    assert {"NYU|PSYCH-UA 25", "NYU|PSYCH-UA 10"} <= {ln["ext_id"] for ln in r.json()["lines"]}
    import threading
    for t in [t for t in threading.enumerate() if t.name == "rank-warm"]:    # no late writes into the next test
        t.join(5)
    matcher.clear_cache()


def test_failures_are_not_cached(azure):
    state = {"fail": True}

    def flaky(messages):
        if state["fail"]:
            raise TimeoutError("quota")
        return _top_at(70)(messages)
    calls = azure(flaky)
    assert matcher.recommend(*_course())["engine"] == "offline-fallback"
    state["fail"] = False
    assert matcher.recommend(*_course())["engine"] == "azure-openai"
    assert len(calls) == 2


def test_recommend_many_keeps_input_order(azure):
    azure(_top_at(70))
    s = store_mod.STORE
    jobs = [(c, list(s.bu_courses.values()), s.syllabi.get(c.ext_id)) for c in list(s.ext_courses.values())[:12]]
    out = matcher.recommend_many(jobs)
    assert [r["ext_id"] for r in out] == [j[0].ext_id for j in jobs]
    assert all(r["engine"] == "azure-openai" for r in out)


@pytest.mark.parametrize("endpoint, expected", [("https://fake.openai.azure.com", True), (None, False)])
def test_startup_prewarms_only_with_the_model(monkeypatch, endpoint, expected):
    import threading
    from fastapi.testclient import TestClient
    from app import main
    if endpoint:
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", endpoint)
    ran = threading.Event()
    monkeypatch.setattr(main, "_prewarm", ran.set)
    with TestClient(main.app):
        assert ran.wait(2) is expected


def test_auth_prefers_managed_identity(monkeypatch):
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(matcher, "_token_provider", lambda: "tok123")
    assert matcher._openai_auth_headers() == {"Authorization": "Bearer tok123"}
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "local-dev")
    assert matcher._openai_auth_headers() == {"api-key": "local-dev"}


def test_di_auth_prefers_managed_identity(monkeypatch):
    from app import ingest

    class FakeCred:
        def get_token(self, scope):
            assert scope == ingest.COGNITIVE_SCOPE
            return type("T", (), {"token": "di-tok"})()
    monkeypatch.delenv("AZURE_DI_KEY", raising=False)
    monkeypatch.setattr(ingest, "_CREDENTIAL", FakeCred())
    assert ingest.DocumentIntelligenceAdapter("https://di.example")._auth_headers() == {"Authorization": "Bearer di-tok"}


def test_offline_import_does_not_load_azure():
    import subprocess
    code = ("import sys; sys.path.insert(0, '.'); import app.main, app.matcher, app.ingest; "
            "print(any(m.startswith('azure') for m in sys.modules))")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         cwd=str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    assert out.stdout.strip() == "False", out.stderr
