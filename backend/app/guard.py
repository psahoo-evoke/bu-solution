"""Default-deny role guard and upload size limit (ADR 0005, docs/security/checklist.md sections 1, 2 and 6).

A pure ASGI middleware, so the role check and the Content-Length check run BEFORE the request body is read and
before any route code runs. A refused request therefore cannot cause a side effect.

- Every /api route except /api/health needs a valid X-Demo-Role: missing or unknown -> 401, not allowed -> 403.
- Allowed roles per operation mirror `x-roles` in docs/api/openapi.yaml (v0.3.0). tests/test_roles.py checks that
  this table and the contract stay identical.
- Upload routes: a body over MAX_UPLOAD_BYTES -> 413. Content-Length is checked up front; chunked bodies are
  counted while streaming.
- TRANSFERIQ_AUTH_MODE=entra fails closed: JWT validation is not built in this slice, so the demo header is
  refused (401) rather than trusted.
"""
from __future__ import annotations

import json
import os
import re

ALL_ROLES = ("Student", "CreditStaff", "Evaluator", "Department", "Registrar", "Advisor")
EVERYONE = set(ALL_ROLES)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
_MULTIPART_SLACK = 64 * 1024        # multipart boundaries/headers around the file part

# (method, path template under /api, allowed roles). Keep in sync with docs/api/openapi.yaml x-roles.
ROUTE_ROLES: list[tuple[str, str, set[str]]] = [
    ("GET", "/students", EVERYONE),
    ("GET", "/students/{student_id}/evaluation", EVERYONE),
    ("POST", "/students/{student_id}/transcripts", {"Student", "CreditStaff"}),
    ("POST", "/courses/{ext_id}/syllabus", {"Student", "CreditStaff", "Evaluator", "Department"}),
    ("GET", "/courses/{ext_id}/recommendation", {"CreditStaff", "Evaluator", "Department"}),
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
PUBLIC = {("GET", "/health")}


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
        if (method, sub) in PUBLIC:
            return await self.app(scope, receive, send_with_headers)

        headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        role = headers.get("x-demo-role")
        if auth_mode() == "entra":
            return await _send_json(send, 401, "Entra ID bearer authentication is required")
        if role not in EVERYONE:
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

        limit = MAX_UPLOAD_BYTES + _MULTIPART_SLACK
        try:
            declared = int(headers.get("content-length", "0") or 0)
        except ValueError:
            declared = 0
        if declared > limit:
            return await _send_json(send, 413, f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")

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
                await _send_json(send, 413, f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
