"""Archive of uploaded PDFs (transcripts, syllabi) in Azure Blob Storage.

Configured by the env contract in infra/README.md: AZURE_STORAGE_BLOB_ENDPOINT plus AZURE_STORAGE_CONTAINER_TRANSCRIPTS
and AZURE_STORAGE_CONTAINER_SYLLABI. Auth is managed identity via DefaultAzureCredential (no account keys).
Without an endpoint the archive is disabled and save_pdf() returns None, so tests and local runs need no Azure
(ADR 0003). When it is configured, a failed write raises BlobStoreError and the upload is rejected (no silent loss).
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re
import uuid
from typing import Literal, Optional

log = logging.getLogger("transferiq.blob")

Kind = Literal["transcripts", "syllabi", "accounts"]
_DEFAULT_CONTAINERS = {"transcripts": "transcripts", "syllabi": "syllabi", "accounts": "accounts"}
_CLIENT = None


class BlobStoreError(Exception):
    pass


def endpoint() -> str:
    return os.environ.get("AZURE_STORAGE_BLOB_ENDPOINT", "").strip()


def enabled() -> bool:
    return bool(endpoint())


def container_for(kind: Kind) -> str:
    return os.environ.get(f"AZURE_STORAGE_CONTAINER_{kind.upper()}") or _DEFAULT_CONTAINERS[kind]


def blob_name(key: str, now: Optional[dt.datetime] = None) -> str:
    """<key>/<UTC timestamp>-<random>.pdf; every upload is kept (no overwrite). Key characters outside
    [A-Za-z0-9._-] become '_' (course ids contain '|' and spaces)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", key)
    return f"{safe}/{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:12]}.pdf"


def _service():
    """Shared BlobServiceClient, created on first use (lazy import keeps offline tests free of azure-*)."""
    global _CLIENT
    if _CLIENT is None:
        from azure.storage.blob import BlobServiceClient  # noqa: WPS433 (lazy on purpose)
        from .ingest import azure_credential
        _CLIENT = BlobServiceClient(account_url=endpoint(), credential=azure_credential())
    return _CLIENT


def save_pdf(kind: Kind, key: str, data: bytes) -> Optional[str]:
    """Store one uploaded PDF. Returns '<container>/<blob name>', or None when the archive is not configured.
    Blocking (Azure SDK); call it from a worker thread in async routes."""
    if not enabled():
        return None
    from azure.storage.blob import ContentSettings  # noqa: WPS433

    container, name = container_for(kind), blob_name(key)
    try:
        _service().get_blob_client(container, name).upload_blob(
            data, overwrite=False, content_settings=ContentSettings(content_type="application/pdf"))
    except Exception as e:  # SDK raises many types (auth, network, HTTP); the route maps all of them to 502
        log.error("blob upload failed: %s/%s: %s", container, name, type(e).__name__)
        raise BlobStoreError(f"Could not store the file ({type(e).__name__})") from e
    log.info("stored upload %s/%s (%d bytes)", container, name, len(data))
    return f"{container}/{name}"


def save_json(kind: Kind, name: str, doc: dict) -> None:
    """Overwrite one JSON document (e.g. accounts/accounts.json). No-op when the archive is not configured."""
    if not enabled():
        return
    import json

    from azure.storage.blob import ContentSettings  # noqa: WPS433

    container = container_for(kind)
    try:
        _service().get_blob_client(container, name).upload_blob(
            json.dumps(doc, separators=(",", ":")).encode(), overwrite=True,
            content_settings=ContentSettings(content_type="application/json"))
    except Exception as e:
        log.error("blob write failed: %s/%s: %s", container, name, type(e).__name__)
        raise BlobStoreError(f"Could not save {name} ({type(e).__name__})") from e


def load_json(kind: Kind, name: str) -> Optional[dict]:
    """Read one JSON document. None when it does not exist yet or the archive is not configured;
    BlobStoreError when it exists but cannot be read (callers must not overwrite it then)."""
    if not enabled():
        return None
    import json

    container = container_for(kind)
    try:
        data = _service().get_blob_client(container, name).download_blob().readall()
    except Exception as e:
        if type(e).__name__ == "ResourceNotFoundError":   # azure.core.exceptions; no import needed offline
            return None
        log.error("blob read failed: %s/%s: %s", container, name, type(e).__name__)
        raise BlobStoreError(f"Could not read {name} ({type(e).__name__})") from e
    return json.loads(data)
