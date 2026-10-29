import os
import sys

import pytest

os.environ.pop("AZURE_OPENAI_ENDPOINT", None)   # ADR 0003: tests always run on the offline engine
os.environ.pop("AZURE_DI_ENDPOINT", None)
os.environ.pop("AZURE_STORAGE_BLOB_ENDPOINT", None)  # upload archive off; test_blob_store.py fakes it
os.environ.pop("AZURE_COMMUNICATION_ENDPOINT", None)  # no real email; test_notify.py fakes the client
os.environ.pop("NOTIFY_WEBHOOK_URL", None)
os.environ.pop("POSTGRES_HOST", None)  # in-memory store from the seed CSVs (ADR 0003); db.py is tested against a temp schema
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient  # noqa: E402

from app import matcher  # noqa: E402
from app import store as store_mod  # noqa: E402
from app.main import app  # noqa: E402

REPO = store_mod.REPO_ROOT
SEED = store_mod.SEED_DIR
TRANSCRIPTS = os.path.join(REPO, "data", "synthetic", "transcripts")
SYLLABI = os.path.join(REPO, "data", "synthetic", "syllabi")


@pytest.fixture(autouse=True)
def fresh_store():
    store_mod.reset()
    matcher.clear_cache()
    yield store_mod.STORE
    store_mod.reset()
    matcher.clear_cache()


@pytest.fixture
def client():
    """Client with a default role (Evaluator) so functional tests read naturally; tests that need another role
    pass X-Demo-Role explicitly. Role-matrix tests use `anon` instead."""
    return TestClient(app, headers={"X-Demo-Role": "Evaluator"})


@pytest.fixture
def anon():
    return TestClient(app)


def role(r):
    return {"X-Demo-Role": r}
