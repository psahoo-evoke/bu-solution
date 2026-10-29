"""Upload archive (app/blob_store.py): uploads are stored in Blob Storage before any state changes.
Azure is faked; no network (ADR 0003)."""
import datetime as dt
import os

import pytest

from app import blob_store
from .conftest import SYLLABI, TRANSCRIPTS, role

MAYA_NYU = os.path.join(TRANSCRIPTS, "Transcript_SYN-24001_NYU_Maya_Delgado.pdf")
SYL_25 = os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf")


class FakeBlob:
    def __init__(self, svc, container, name):
        self.svc, self.container, self.name = svc, container, name

    def upload_blob(self, data, overwrite, content_settings):
        if self.svc.fail:
            raise RuntimeError("boom")
        assert overwrite is False
        self.svc.saved.append((self.container, self.name, data, content_settings.content_type))


class FakeService:
    def __init__(self):
        self.saved, self.fail = [], False

    def get_blob_client(self, container, name):
        return FakeBlob(self, container, name)


@pytest.fixture
def blob(monkeypatch):
    svc = FakeService()
    monkeypatch.setenv("AZURE_STORAGE_BLOB_ENDPOINT", "https://example.blob.core.windows.net/")
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER_TRANSCRIPTS", "transcripts")
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER_SYLLABI", "syllabi")
    monkeypatch.setattr(blob_store, "_service", lambda: svc)
    return svc


def _upload_transcript(client):
    with open(MAYA_NYU, "rb") as f:
        return client.post("/api/students/SYN-24001/transcripts", files={"file": ("t.pdf", f)}, headers=role("Student"))


def _upload_syllabus(client):
    with open(SYL_25, "rb") as f:
        return client.post("/api/courses/NYU%7CPSYCH-UA%2025/syllabus", files={"file": ("s.pdf", f)})


def test_disabled_without_endpoint(client):
    assert not blob_store.enabled()
    assert blob_store.save_pdf("transcripts", "SYN-24001", b"%PDF-") is None
    assert _upload_transcript(client).status_code == 201


def test_blob_name_is_safe_and_unique():
    now = dt.datetime(2026, 10, 29, 9, 30, tzinfo=dt.timezone.utc)
    a, b = blob_store.blob_name("NYU|PSYCH-UA 25", now), blob_store.blob_name("NYU|PSYCH-UA 25", now)
    assert a.startswith("NYU_PSYCH-UA_25/20261029T093000Z-") and a.endswith(".pdf") and a != b


def test_transcript_upload_is_stored(client, blob):
    with open(MAYA_NYU, "rb") as f:
        original = f.read()
    assert _upload_transcript(client).status_code == 201
    [(container, name, data, ctype)] = blob.saved
    assert (container, ctype, data) == ("transcripts", "application/pdf", original)
    assert name.startswith("SYN-24001/")


def test_syllabus_upload_is_stored_and_recorded(client, blob, fresh_store):
    assert _upload_syllabus(client).status_code == 201
    [(container, name, _, _)] = blob.saved
    assert container == "syllabi" and name.startswith("NYU_PSYCH-UA_25/")
    assert fresh_store.syllabi["NYU|PSYCH-UA 25"].file == f"syllabi/{name}"


def test_store_failure_rejects_upload_and_changes_nothing(client, blob, fresh_store):
    blob.fail = True
    lines_before = list(fresh_store.lines)
    syl_before = fresh_store.syllabi.get("NYU|PSYCH-UA 25")
    r = _upload_transcript(client)
    assert r.status_code == 502 and "Could not store the file" in r.json()["detail"]
    assert _upload_syllabus(client).status_code == 502
    assert fresh_store.lines == lines_before
    assert fresh_store.syllabi.get("NYU|PSYCH-UA 25") is syl_before


def test_rejected_upload_is_not_stored(client, blob):
    with open(MAYA_NYU, "rb") as f:   # Maya's transcript posted for another student -> 422, nothing archived
        r = client.post("/api/students/SYN-24002/transcripts", files={"file": ("t.pdf", f)}, headers=role("Student"))
    assert r.status_code == 422 and blob.saved == []
