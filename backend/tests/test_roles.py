"""ADR 0005 default-deny role matrix, generated from `x-roles` in docs/api/openapi.yaml (v0.8.0).

Every route except the public allowlist (guard.PUBLIC, ADR 0006): missing/unknown X-Demo-Role -> 401, role not in x-roles -> 403, allowed role -> neither.
Refusals happen before any side effect.
"""
import os
import re

import pytest
import yaml

from app.guard import ALL_ROLES, PUBLIC, ROUTE_ROLES
from app.main import api

from .conftest import REPO, role

SPEC = yaml.safe_load(open(os.path.join(REPO, "docs", "api", "openapi.yaml"), encoding="utf-8"))
SAMPLE = {"student_id": "SYN-24001", "ext_id": "NYU%7CPSYCH-UA%2010"}
BODIES = {
    ("POST", "/decisions"): dict(json=dict(ext_id="NYU|PSYCH-UA 10", decision="Equivalent", bu_course="CAS PS 211",
                                           reason_code="EQ-EVALUATOR", reusable=True, evaluator="E")),
    ("POST", "/decisions/batch"): dict(json=dict(ext_ids=["NEU|BIOL 3712"], evaluator="E")),
}
OPS = [(m.upper(), path, op.get("x-roles"))
       for path, item in SPEC["paths"].items() for m, op in item.items() if m in ("get", "post")]
PROTECTED = [(m, p, set(r)) for m, p, r in OPS if (m, p) not in PUBLIC]


def _url(path):
    return "/api" + re.sub(r"\{(\w+)\}", lambda mt: SAMPLE[mt.group(1)], path)


def _call(client, method, path, headers):
    kw = BODIES.get((method, path), {})
    return client.request(method, _url(path), headers=headers, **kw)


def test_contract_and_guard_table_are_identical():
    assert {(m, p): set(r) for m, p, r in PROTECTED} == {(m, p): r for m, p, r in ROUTE_ROLES}
    assert all(r is not None for m, p, r in PROTECTED), "every protected operation declares x-roles"


def test_public_operations_in_the_contract_are_exactly_the_guard_allowlist():
    # /auth/* (portal sign-in and registration) is public but not part of the contract yet.
    public_in_spec = {(m.upper(), p) for p, item in SPEC["paths"].items() for m, op in item.items()
                      if isinstance(op, dict) and op.get("security") == []}
    assert public_in_spec == {(m, p) for m, p in PUBLIC if not p.startswith("/auth/")}
    assert all(op.get("x-roles") is None for p, item in SPEC["paths"].items() for op in item.values()
               if isinstance(op, dict) and op.get("security") == [])


def test_every_api_route_is_in_the_contract():
    served = {(m, r.path[len("/api"):] if r.path.startswith("/api") else r.path)
              for r in api.routes for m in getattr(r, "methods", set()) if m in ("GET", "POST")}
    assert served
    assert served == {(m, p) for m, p, _ in OPS}


def test_health_is_public(anon):
    assert anon.get("/api/health").status_code == 200


@pytest.mark.parametrize("method,path", [(m, p) for m, p, _ in PROTECTED])
@pytest.mark.parametrize("header", [None, "", "Hacker", "evaluator"])
def test_missing_or_unknown_role_is_401(anon, method, path, header):
    h = {} if header is None else {"X-Demo-Role": header}
    assert _call(anon, method, path, h).status_code == 401


@pytest.mark.parametrize("method,path,allowed", PROTECTED, ids=[f"{m} {p}" for m, p, _ in PROTECTED])
@pytest.mark.parametrize("who", ALL_ROLES)
def test_role_matrix(anon, method, path, allowed, who):
    status = _call(anon, method, path, role(who)).status_code
    if who in allowed:
        assert status not in (401, 403), f"{who} should reach {method} {path}"
    else:
        assert status == 403, f"{who} must be refused on {method} {path}"


def test_refusal_has_no_side_effect(anon, fresh_store):
    body = BODIES[("POST", "/decisions")]["json"]
    for who in ("Student", "CreditStaff", "Registrar", "Advisor"):
        assert anon.post("/api/decisions", json=body, headers=role(who)).status_code == 403
    assert anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "E"},
                     headers=role("Registrar")).status_code == 403
    assert not any(d.split == "runtime" for d in fresh_store.decisions)
    assert fresh_store.audit_log == []
    # a refused reset leaves a real decision in place
    assert anon.post("/api/decisions", json=body, headers=role("Evaluator")).status_code == 201
    assert anon.post("/api/demo/reset", headers=role("Evaluator")).status_code == 403
    assert any(d.split == "runtime" for d in fresh_store.decisions)


def test_decision_audit_records_actor_role(anon, fresh_store):
    body = BODIES[("POST", "/decisions")]["json"]
    anon.post("/api/decisions", json=body, headers=role("Department"))
    [entry] = fresh_store.audit_log
    assert entry["actor_role"] == "Department" and entry["action"] == "decision" and entry["ext_id"] == "NYU|PSYCH-UA 10"


def test_batch_allows_department(anon):
    r = anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "D"}, headers=role("Department"))
    assert r.status_code == 201


def test_entra_mode_fails_closed(anon, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "entra")
    assert anon.get("/api/students", headers=role("Registrar")).status_code == 401
    assert anon.get("/api/health").status_code == 200


def test_security_headers(anon):
    r = anon.get("/api/students", headers=role("Advisor"))
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer" and r.headers["cache-control"] == "no-store"
    assert anon.get("/api/students").headers["x-content-type-options"] == "nosniff"     # also on 401
