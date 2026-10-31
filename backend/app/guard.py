"""Default-deny role guard and upload size limit (ADR 0005, docs/security/checklist.md sections 1, 2 and 6).

A pure ASGI middleware, so the role check and the Content-Length check run BEFORE the request body is read and
before any route code runs. A refused request therefore cannot cause a side effect.

- Every /api route except the PUBLIC allowlist (health, /auth/*, the credit check and chat; ADR 0006) needs a valid
  X-Demo-Role: missing or unknown -> 401, not allowed -> 403. Public routes: a body over MAX_PUBLIC_BODY -> 413.
- Allowed roles per operation mirror `x-roles` in docs/api/openapi.yaml (v0.8.0). tests/test_roles.py checks that
  this table and the contract stay identical.
- Upload routes: a body over MAX_UPLOAD_BYTES -> 413. Content-Length is checked up front; chunked bodies are
  counted while streaming.
- TRANSFERIQ_AUTH_MODE=entra: every /api route except /api/health needs `Authorization: Bearer <Entra access
  token>` for the app registration ENTRA_CLIENT_ID in tenant ENTRA_TENANT_ID (RS256 signature from the tenant's
  JWKS, issuer, audience, expiry). The caller's roles are the token's `roles` claim (Entra app roles with the same
  names as ALL_ROLES). X-Demo-Role then only picks the ACTIVE role and must be one of those roles (403 otherwise);
  without it the first assigned role is used. The chosen role is written back into X-Demo-Role for the routes.
  Not configured (no tenant/client id) -> 401, never the demo header.
- TRANSFERIQ_AUTH_MODE=portal: per-user portal accounts (app/accounts.py). `Authorization: Bearer <session token>`
  from POST /api/auth/login; the role comes from the account, not from X-Demo-Role. A Student may only touch
  /students/{own id}/... (403 otherwise). The signed-in user is passed to the routes in scope["state"]["user"]
  (routes narrow lists: a student sees only their record, a department only its department's courses).
  /api/auth/* (login, registration, options) is public in every mode.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Optional

ALL_ROLES = ("Student", "CreditStaff", "Evaluator", "Department", "Registrar", "Advisor", "FinancialAid")
EVERYONE = set(ALL_ROLES)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_MULTIPART_SLACK = 64 * 1024        # multipart boundaries/headers around the file part
MAX_PUBLIC_BODY = 64 * 1024         # public routes take small JSON only

# (method, path template under /api, allowed roles). Keep in sync with docs/api/openapi.yaml x-roles.
ROUTE_ROLES: list[tuple[str, str, set[str]]] = [
    ("GET", "/students", EVERYONE),
    ("GET", "/students/summary", {"Advisor", "FinancialAid"}),
    ("GET", "/students/{student_id}/evaluation", EVERYONE),
    ("GET", "/students/{student_id}/notifications", EVERYONE),
    ("POST", "/students/{student_id}/notifications/seen", {"Student"}),
    ("POST", "/students/{student_id}/transcripts", {"Student", "CreditStaff"}),
    ("POST", "/courses/{ext_id}/syllabus", {"Student", "CreditStaff", "Evaluator", "Department"}),
    ("POST", "/students/{student_id}/courses/{ext_id}/syllabus-request", {"Student", "CreditStaff", "Evaluator", "Department"}),
    ("GET", "/courses/{ext_id}/recommendation", {"CreditStaff", "Evaluator", "Department"}),
    ("GET", "/courses/{ext_id}/syllabus", {"CreditStaff", "Evaluator", "Department"}),
    ("POST", "/syllabus-reminders/run", {"CreditStaff"}),
    ("GET", "/review-queue", {"CreditStaff", "Evaluator", "Department"}),
    ("POST", "/decisions", {"Evaluator", "Department"}),
    ("POST", "/decisions/batch", {"Evaluator", "Department"}),
    ("GET", "/exports/mybu.csv", {"Registrar", "CreditStaff"}),
    ("POST", "/postings", {"Registrar", "CreditStaff"}),
    ("GET", "/evaluation/metrics", EVERYONE),
    ("GET", "/rules", EVERYONE),
    ("GET", "/reason-codes", EVERYONE),
    ("POST", "/demo/reset", {"CreditStaff", "Registrar"}),
]
UPLOAD_ROUTES = {"/students/{student_id}/transcripts", "/courses/{ext_id}/syllabus"}
PUBLIC = {("GET", "/health"), ("POST", "/auth/login"), ("POST", "/auth/register/student"),
          ("GET", "/credit-check/schools"), ("GET", "/credit-check/courses"),("POST", "/credit-check"), ("POST", "/credit-chat"),   # public, no login
          ("POST", "/auth/register/department"), ("POST", "/auth/register/staff"), ("GET", "/auth/options")}
_STUDENT_PATH = re.compile(r"^/students/([^/]+)(/|$)")


def _compile(template: str) -> re.Pattern:
    return re.compile("^" + re.sub(r"\{[^}]+\}", r"[^/]+", re.escape(template).replace(r"\{", "{").replace(r"\}", "}")) + "$")


_TABLE = [(m, t, _compile(t), roles) for m, t, roles in ROUTE_ROLES]

SECURITY_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"cache-control", b"no-store"),
]


def auth_mode() -> str:
    return os.environ.get("TRANSFERIQ_AUTH_MODE", "demo").lower()


# ------------------------------------------------------------------ Entra ID (TRANSFERIQ_AUTH_MODE=entra)
class AuthError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def entra_config() -> tuple[str, str]:
    return os.environ.get("ENTRA_TENANT_ID", "").strip(), os.environ.get("ENTRA_CLIENT_ID", "").strip()


_JWKS = None


def _signing_key(token: str):
    """Public key for the token's `kid` from the tenant JWKS (cached by PyJWKClient). Blocking on a cache miss.
    Tests replace this function."""
    global _JWKS
    if _JWKS is None:
        from jwt import PyJWKClient  # lazy: demo mode and offline tests never need it
        tenant, _ = entra_config()
        _JWKS = PyJWKClient(f"https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys", lifespan=3600)
    return _JWKS.get_signing_key_from_jwt(token).key


def entra_roles(authorization: Optional[str]) -> list[str]:
    """The caller's TransferIQ roles in ALL_ROLES order (see entra_user)."""
    return entra_user(authorization)[0]


def entra_user(authorization: Optional[str]) -> tuple[list[str], dict]:
    """Validate an Entra access token: (roles in ALL_ROLES order, identity {name, email}). Accepts v1 and v2 tokens
    (issuer differs) whose audience is the client id or api://<client id>. The identity is the token's sign-in name
    (preferred_username / upn / email) and display name; oid when there is no sign-in name."""
    import jwt  # lazy

    tenant, client = entra_config()
    if not tenant or not client:
        raise AuthError(401, "Entra ID is not configured on the API (ENTRA_TENANT_ID / ENTRA_CLIENT_ID)")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError(401, "Sign in required: missing Entra ID bearer token")
    token = authorization[7:].strip()
    try:
        claims = jwt.decode(
            token, _signing_key(token), algorithms=["RS256"], audience=[client, f"api://{client}"],
            issuer=[f"https://login.microsoftonline.com/{tenant}/v2.0", f"https://sts.windows.net/{tenant}/"],
            options={"require": ["exp", "iss", "aud"]}, leeway=60)
    except Exception as e:  # PyJWT and JWKS errors: expired, bad signature, wrong audience/issuer, unknown kid ...
        raise AuthError(401, f"Invalid or expired sign-in token ({type(e).__name__})")
    if claims.get("tid") != tenant:
        raise AuthError(401, "Token is from another tenant")
    granted = set(claims.get("roles") or [])
    login = claims.get("preferred_username") or claims.get("upn") or claims.get("email") or claims.get("oid") or ""
    return [r for r in ALL_ROLES if r in granted], dict(name=claims.get("name") or "", email=login)


def choose_role(granted: list[str], requested: Optional[str]) -> str:
    """Active role for this request: the requested one if the token grants it, else the first granted role."""
    if not granted:
        raise AuthError(403, "Your account has no TransferIQ role. Ask an administrator to assign one "
                             "(Student, CreditStaff, Evaluator, Department, Registrar, Advisor or FinancialAid).")
    if requested:
        if requested not in granted:
            raise AuthError(403, f"Role '{requested}' is not assigned to your account (assigned: {', '.join(granted)})")
        return requested
    return granted[0]


class _TooLarge(BaseException):  # BaseException: must not be swallowed by FastAPI body-parsing handlers
    pass


async def _send_json(send, status: int, detail: str):
    body = json.dumps({"detail": detail}).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            *SECURITY_HEADERS]})
    await send({"type": "http.response.body", "body": body})


class RoleGuardMiddleware:
    def __init__(self, app, prefix: str = "/api"):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                names = {k.lower() for k, _ in message.get("headers", [])}
                message = dict(message, headers=list(message.get("headers", [])) +
                               [h for h in SECURITY_HEADERS if h[0] not in names])
            await send(message)

        path, method = scope["path"], scope["method"]
        if not path.startswith(self.prefix) or method == "OPTIONS":      # docs, CORS preflight
            return await self.app(scope, receive, send_with_headers)
        sub = path[len(self.prefix):] or "/"
        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        if (method, sub) in PUBLIC:              # no login; small JSON bodies only (the auth forms, credit check/chat)
            return await self._capped(scope, headers, receive, send, send_with_headers, MAX_PUBLIC_BODY,
                                      f"Request too large (max {MAX_PUBLIC_BODY // 1024} KB)")
        role = headers.get("x-demo-role")
        if auth_mode() == "entra":
            try:
                # JWKS fetch on a cache miss is blocking network I/O: keep it off the event loop.
                granted, identity = await asyncio.to_thread(entra_user, headers.get("authorization"))
                role = choose_role(granted, role)
            except AuthError as e:
                return await _send_json(send, e.status, e.detail)
            # Routes read X-Demo-Role (audit actor); make it the verified active role. "identity" (who decided) only;
            # entra users are not portal users, so state["user"] (portal record scoping) stays unset.
            scope = dict(scope, state={**scope.get("state", {}), "identity": identity}, headers=[(k, v) for k, v in scope.get("headers", []) if k.lower() != b"x-demo-role"]
                         + [(b"x-demo-role", role.encode())])
        elif auth_mode() == "portal":
            from .accounts import AccountError, session_user  # lazy: avoids an import cycle with the store
            try:
                user = session_user(headers.get("authorization"))
            except AccountError as e:
                return await _send_json(send, e.status, e.detail)
            role = user["role"]
            own = _STUDENT_PATH.match(sub)
            if role == "Student" and own and own.group(1) != user["student_id"]:
                return await _send_json(send, 403, "Students can only see their own record")
            scope = dict(scope, state={**scope.get("state", {}), "user": user,
                                       "identity": dict(name=user.get("name") or "", email=user["email"])},
                         headers=[(k, v) for k, v in scope.get("headers", []) if k.lower() != b"x-demo-role"]
                         + [(b"x-demo-role", role.encode())])
        elif role not in EVERYONE:
            return await _send_json(send, 401, "Missing or unknown X-Demo-Role")
        match = next(((t, roles) for m, t, rx, roles in _TABLE if m == method and rx.match(sub)), None)
        if match is None:
            # Unknown route/method: authenticated callers get the router's normal 404/405.
            return await self.app(scope, receive, send_with_headers)
        template, roles = match
        if role not in roles:
            return await _send_json(send, 403, f"Role '{role}' is not allowed for {method} {template}")

        if template not in UPLOAD_ROUTES:
            return await self.app(scope, receive, send_with_headers)
        return await self._capped(scope, headers, receive, send, send_with_headers, MAX_UPLOAD_BYTES + _MULTIPART_SLACK,
                                  f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

    async def _capped(self, scope, headers, receive, send, send_with_headers, limit: int, too_large: str):
        """Run the app with the request body capped at `limit` bytes: Content-Length up front, chunks while streaming."""
        try:
            declared = int(headers.get("content-length", "0") or 0)
        except ValueError:
            declared = 0
        if declared > limit:
            return await _send_json(send, 413, too_large)

        seen = 0
        started = False

        async def counting_receive():
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise _TooLarge()
            return message

        async def tracking_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send_with_headers(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if not started:
                await _send_json(send, 413, too_large)
