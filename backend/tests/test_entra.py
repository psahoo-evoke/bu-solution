"""Entra ID mode (app/guard.py): roles come from a validated access token, X-Demo-Role only picks among them.
Tokens are signed with a throwaway RSA key; the JWKS lookup is replaced, so no network (ADR 0003)."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import guard

TENANT = "11111111-1111-1111-1111-111111111111"
CLIENT = "22222222-2222-2222-2222-222222222222"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def entra(monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "entra")
    monkeypatch.setenv("ENTRA_TENANT_ID", TENANT)
    monkeypatch.setenv("ENTRA_CLIENT_ID", CLIENT)
    monkeypatch.setattr(guard, "_signing_key", lambda token: KEY.public_key())


def token(roles=None, key=KEY, v2=True, **over):
    now = int(time.time())
    claims = dict(aud=CLIENT, tid=TENANT, oid="user-1", iat=now, nbf=now, exp=now + 3600,
                  iss=f"https://login.microsoftonline.com/{TENANT}/v2.0" if v2 else f"https://sts.windows.net/{TENANT}/")
    if roles is not None:
        claims["roles"] = roles
    claims.update(over)
    return jwt.encode(claims, key, algorithm="RS256")


def auth(tok, active=None):
    h = {"Authorization": f"Bearer {tok}"}
    if active:
        h["X-Demo-Role"] = active
    return h


def test_health_stays_public(anon):
    assert anon.get("/api/health").status_code == 200


def test_missing_token_401(anon):
    r = anon.get("/api/students", headers={"X-Demo-Role": "Registrar"})   # the demo header alone is not trusted
    assert r.status_code == 401 and "Sign in required" in r.json()["detail"]


@pytest.mark.parametrize("bad", [
    dict(key=OTHER_KEY),                                     # wrong signature
    dict(exp=int(time.time()) - 3600),                      # expired
    dict(aud="someone-else"),                               # token for another API
    dict(iss="https://login.microsoftonline.com/evil/v2.0"),  # wrong issuer
])
def test_invalid_tokens_401(anon, bad):
    key = bad.pop("key", KEY)
    r = anon.get("/api/students", headers=auth(token(["Student"], key=key, **bad)))
    assert r.status_code == 401 and "Invalid or expired" in r.json()["detail"]


def test_other_tenant_401(anon):
    assert anon.get("/api/students", headers=auth(token(["Student"], tid="other"))).status_code == 401


def test_not_configured_401(anon, monkeypatch):
    monkeypatch.delenv("ENTRA_CLIENT_ID")
    assert anon.get("/api/students", headers=auth(token(["Student"]))).status_code == 401


def test_v1_token_and_api_uri_audience_accepted(anon):
    assert anon.get("/api/students", headers=auth(token(["Student"], v2=False))).status_code == 200
    assert anon.get("/api/students", headers=auth(token(["Student"], aud=f"api://{CLIENT}"))).status_code == 200


def test_no_role_assigned_403(anon):
    for roles in (None, [], ["SomethingElse"]):
        r = anon.get("/api/students", headers=auth(token(roles)))
        assert r.status_code == 403 and "no TransferIQ role" in r.json()["detail"]


# ------------------------------------------------------------------ Student
def test_student_can_read_and_upload_transcript_but_not_review(anon):
    t = token(["Student"])
    assert anon.get("/api/students/SYN-24001/evaluation", headers=auth(t)).status_code == 200
    assert anon.post("/api/students/SYN-24001/transcripts", headers=auth(t), files={"file": ("t.pdf", b"x")}).status_code != 403
    for method, path in [("GET", "/api/review-queue"), ("POST", "/api/decisions"), ("GET", "/api/exports/mybu.csv")]:
        assert anon.request(method, path, headers=auth(t)).status_code == 403, path


def test_student_cannot_claim_department(anon):
    r = anon.get("/api/review-queue", headers=auth(token(["Student"]), active="Department"))
    assert r.status_code == 403 and "not assigned to your account" in r.json()["detail"]


# ------------------------------------------------------------------ Department
def test_department_can_review_and_decide_but_not_post_or_upload_transcript(anon):
    t = token(["Department"])
    assert anon.get("/api/review-queue", headers=auth(t)).status_code == 200
    r = anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "D"}, headers=auth(t))
    assert r.status_code == 201
    assert anon.post("/api/postings", headers=auth(t)).status_code == 403
    assert anon.post("/api/students/SYN-24001/transcripts", headers=auth(t), files={"file": ("t.pdf", b"x")}).status_code == 403


def test_multi_role_user_picks_active_role(anon, fresh_store):
    t = token(["Department", "Student"])
    assert anon.get("/api/review-queue", headers=auth(t)).status_code == 403            # default = first in ALL_ROLES: Student
    assert anon.get("/api/review-queue", headers=auth(t, active="Department")).status_code == 200
    anon.post("/api/decisions/batch", json={"ext_ids": ["NEU|BIOL 3712"], "evaluator": "D"}, headers=auth(t, "Department"))
    assert fresh_store.audit_log[-1]["actor_role"] == "Department"                              # verified role reaches routes


def test_decisions_record_the_verified_entra_identity(anon, fresh_store):
    # architect S1 / security M-1: in entra mode the typed evaluator name used to be recorded.
    t = token(["Evaluator"], name="Jordan Lee", preferred_username="jlee@bu.edu")
    dec = dict(ext_id="NYU|PSYCH-UA 10", decision="Equivalent", bu_course="CAS PS 211", reason_code="EQ-EVALUATOR",
               evaluator="Registrar Jane Doe")
    r = anon.post("/api/decisions", json=dec, headers=auth(t))
    assert r.status_code == 201 and r.json()["evaluator"] == "Jordan Lee <jlee@bu.edu>"
    decision = next(e for e in fresh_store.audit_log if e["action"] == "decision")
    assert decision["after"]["evaluator"] == "Jordan Lee <jlee@bu.edu>"
