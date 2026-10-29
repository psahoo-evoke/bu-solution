"""Azure OpenAI engine with a fake client: output validation (checklist section 3), prompt PII (section 4),
fallback, and lazy azure-identity import. No network."""
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
    def reply(messages):
        codes = _shortlist_codes(messages)
        b = store_mod.STORE.bu_courses[codes[0]]
        return json.dumps({"candidates": [
            {"bu_code": codes[0], "overlap_pct": 85, "tier": "equivalent", "covered": b.learning_outcomes[:5] + ["invented"]},
            {"bu_code": codes[1], "overlap_pct": 140},                 # clamped to 100
            {"bu_code": codes[2], "overlap_pct": -3}]})                # clamped to 0
    azure(reply)
    rec = matcher.recommend(*_course())
    assert rec["engine"] == "azure-openai"
    pcts = sorted(c["overlap_pct"] for c in rec["candidates"])
    assert pcts == [0, 85, 100]
    top85 = next(c for c in rec["candidates"] if c["overlap_pct"] == 85)
    assert "invented" not in top85["covered"] and len(top85["covered"]) == 5
    assert all(c["tier"] in matcher.TIERS for c in rec["candidates"])


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


def _top_at(pct):
    return lambda m: json.dumps({"candidates": [{"bu_code": _shortlist_codes(m)[0], "overlap_pct": pct}]})


def test_same_prompt_is_answered_from_cache(azure):
    calls = azure(_top_at(70))
    first = matcher.recommend(*_course())
    first["candidates"][0]["overlap_pct"] = 1            # callers may mutate what they get back
    first["past_decisions"] = ["x"]
    second = matcher.recommend(*_course())
    assert len(calls) == 1
    assert second["engine"] == "azure-openai"
    assert second["candidates"][0]["overlap_pct"] == 70 and "past_decisions" not in second


def test_changed_syllabus_is_a_new_model_call(azure):
    from app.store import SyllabusRecord
    calls = azure(_top_at(70))
    course, bus, syl = _course()
    matcher.recommend(course, bus, syl)
    new = SyllabusRecord(ext_id=course.ext_id, state="complete", text=syl.text + "\nWeek 15: panel data methods.")
    matcher.recommend(course, bus, new)
    assert len(calls) == 2


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
