"""Email notifications ("syllabus needed, please upload") via Azure Communication Services Email.

Configured by env (infra/README.md): AZURE_COMMUNICATION_ENDPOINT + ACS_SENDER_ADDRESS (the service and its verified
sender), SYLLABUS_REQUEST_TO / SYLLABUS_REQUEST_CC (comma-separated recipients) and APP_BASE_URL (for the link in the
mail). Auth is managed identity via DefaultAzureCredential, no keys.

Hackathon rule: the student's own address is never emailed. The sample students' addresses are made up on the real
bu.edu domain, so a request goes to the notification list and names the student and course inside the mail.

Without a mail service (tests, local, or until ACS exists) send() returns "not_sent" and the request is still recorded.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

log = logging.getLogger("transferiq.notify")


class NotifyError(Exception):
    pass


def _list(var: str) -> list[str]:
    return [a.strip() for a in os.environ.get(var, "").split(",") if a.strip()]


def recipients() -> tuple[list[str], list[str]]:
    return _list("SYLLABUS_REQUEST_TO"), _list("SYLLABUS_REQUEST_CC")


def configured() -> bool:
    to, _ = recipients()
    return bool(os.environ.get("AZURE_COMMUNICATION_ENDPOINT") and os.environ.get("ACS_SENDER_ADDRESS") and to)


def app_link(path: str) -> Optional[str]:
    base = os.environ.get("APP_BASE_URL", "").rstrip("/")
    return f"{base}{path}" if base else None


_CLIENT = None


def _client():
    """Shared EmailClient, created on first use (lazy import keeps offline tests free of azure-*)."""
    global _CLIENT
    if _CLIENT is None:
        from azure.communication.email import EmailClient  # noqa: WPS433 (lazy on purpose)
        from .ingest import azure_credential
        _CLIENT = EmailClient(os.environ["AZURE_COMMUNICATION_ENDPOINT"], azure_credential())
    return _CLIENT


def send(subject: str, text: str, html: str) -> str:
    """Send to the notification list. Returns "sent" or "not_sent" (no mail service configured).
    Raises NotifyError when the service rejects the mail. Blocking; call from a worker thread in async routes."""
    to, cc = recipients()
    if not configured():
        log.info("email not sent (no mail service configured): %s", subject)
        return "not_sent"
    message = {
        "senderAddress": os.environ["ACS_SENDER_ADDRESS"],
        "recipients": {"to": [{"address": a} for a in to], "cc": [{"address": a} for a in cc]},
        "content": {"subject": subject, "plainText": text, "html": html},
    }
    try:
        result = _client().begin_send(message).result()
    except Exception as e:  # SDK raises auth, network and HTTP errors; the route maps all of them to 502
        log.error("email send failed: %s", type(e).__name__)
        raise NotifyError(f"The email could not be sent ({type(e).__name__})") from e
    status = (result or {}).get("status") if isinstance(result, dict) else getattr(result, "status", None)
    if str(status).lower() not in ("succeeded", "none"):
        log.error("email send status %s", status)
        raise NotifyError(f"The email could not be sent (status {status})")
    log.info("email sent to %d recipient(s): %s", len(to) + len(cc), subject)
    return "sent"
