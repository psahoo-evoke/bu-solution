"""Registered portal accounts are saved to Blob Storage and survive a restart (app/accounts.py + app/blob_store.py).
Azure is faked in memory; a "restart" re-seeds the store and the account registry from the fake blob."""
import json

import pytest

from app import accounts, blob_store
from app import store as store_mod


class ResourceNotFoundError(Exception):   # same class name as azure.core.exceptions.ResourceNotFoundError
    pass


class FakeBlob:
    def __init__(self, svc, container, name):
        self.svc, self.key = svc, (container, name)

    def upload_blob(self, data, overwrite, content_settings):
        if self.svc.write_fail:
            raise RuntimeError("write boom")
        assert overwrite is True
        self.svc.blobs[self.key] = data

    def download_blob(self):
        if self.svc.read_fail:
            raise RuntimeError("read boom")
        if self.key not in self.svc.blobs:
            raise ResourceNotFoundError()
        data = self.svc.blobs[self.key]
        return type("D", (), {"readall": lambda _self: data})()


class FakeService:
    def __init__(self):
        self.blobs, self.read_fail, self.write_fail = {}, False, False

    def get_blob_client(self, container, name):
        return FakeBlob(self, container, name)

    def doc(self):
        return json.loads(self.blobs[("accounts", "accounts.json")])


@pytest.fixture
def blob(monkeypatch):
    svc = FakeService()
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    monkeypatch.setenv("AZURE_STORAGE_BLOB_ENDPOINT", "https://example.blob.core.windows.net/")
    monkeypatch.setenv("AZURE_STORAGE_CONTAINER_ACCOUNTS", "accounts")
    monkeypatch.setattr(blob_store, "_service", lambda: svc)
    accounts.reset_accounts()
    yield svc
    monkeypatch.delenv("AZURE_STORAGE_BLOB_ENDPOINT")
    accounts.reset_accounts()


def restart():
    """What a new API process does: fresh store from the seed files, then accounts (seeded + stored)."""
    store_mod.reset()
    accounts.reset_accounts()


def register_student(anon, email="sam.patel@bu.edu", password="secret1"):
    return anon.post("/api/auth/register/student", json=dict(
        name="Sam Patel", email=email, password=password, intended_major="Mathematics"))


def login(anon, email, password, portal="student"):
    return anon.post("/api/auth/login", json=dict(email=email, password=password, portal=portal))


def test_registered_student_survives_restart(anon, blob):
    sid = register_student(anon).json()["user"]["student_id"]
    doc = blob.doc()
    assert [a["email"] for a in doc["accounts"]] == ["sam.patel@bu.edu"]
    assert doc["students"] == [dict(student_id=sid, name="Sam Patel", intended_major="Mathematics", bu_start_term="Fall 2026")]
    assert "secret1" not in json.dumps(doc) and doc["accounts"][0]["password_hash"].count("$") == 1   # hash only

    restart()
    r = login(anon, "sam.patel@bu.edu", "secret1")
    assert r.status_code == 200 and r.json()["user"]["student_id"] == sid
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    assert anon.get(f"/api/students/{sid}/evaluation", headers=h).json()["student"]["name"] == "Sam Patel"
    assert login(anon, "maya.delgado@bu.edu", "admin").status_code == 200       # seeded accounts still there


def test_registered_department_survives_restart(anon, blob):
    anon.post("/api/auth/register/department", json=dict(
        name="Dr. Kim", email="kim@bu.edu", password="secret1", department="Economics"))
    restart()
    r = login(anon, "kim@bu.edu", "secret1", portal="department")
    assert r.status_code == 200 and r.json()["user"]["department"] == "Economics"


def test_student_ids_do_not_repeat_after_restart(anon, blob):
    first = register_student(anon, "a.one@bu.edu").json()["user"]["student_id"]
    restart()
    second = register_student(anon, "b.two@bu.edu").json()["user"]["student_id"]
    assert first != second
    restart()
    assert {s["student_id"] for s in blob.doc()["students"]} == {first, second}


def test_failed_save_means_no_account(anon, blob):
    blob.write_fail = True
    r = register_student(anon)
    assert r.status_code == 502 and "Could not save" in r.json()["detail"]
    assert login(anon, "sam.patel@bu.edu", "secret1").status_code == 404
    assert "SYN-24005" not in store_mod.STORE.students
    blob.write_fail = False
    assert register_student(anon).json()["user"]["student_id"] == "SYN-24005"   # nothing left behind


def test_unreadable_storage_pauses_registration_and_never_overwrites(anon, blob):
    register_student(anon)                       # stored: sam.patel
    blob.read_fail = True
    restart()                                    # start-up read fails
    r = register_student(anon, "new.person@bu.edu")
    assert r.status_code == 503
    assert [a["email"] for a in blob.doc()["accounts"]] == ["sam.patel@bu.edu"]   # stored list untouched
    assert login(anon, "maya.delgado@bu.edu", "admin").status_code == 200        # sign-in still works
    blob.read_fail = False                       # storage back: the next registration reloads first, then saves
    assert register_student(anon, "new.person@bu.edu").status_code == 201
    assert {a["email"] for a in blob.doc()["accounts"]} == {"sam.patel@bu.edu", "new.person@bu.edu"}
    assert register_student(anon, "sam.patel@bu.edu").status_code == 409        # duplicate check saw the stored one


def test_nothing_stored_without_blob_endpoint(anon, monkeypatch):
    monkeypatch.setenv("TRANSFERIQ_AUTH_MODE", "portal")
    monkeypatch.delenv("AZURE_STORAGE_BLOB_ENDPOINT", raising=False)
    accounts.reset_accounts()
    assert register_student(anon).status_code == 201
    accounts.reset_accounts()
