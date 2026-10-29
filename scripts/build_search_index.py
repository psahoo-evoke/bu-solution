"""Create or update the Azure AI Search index of the BU catalog (backend/app/search.py).

Usage (from the repo root, with AZURE_SEARCH_ENDPOINT and an admin AZURE_SEARCH_API_KEY, or an Azure login with
Search Service Contributor + Search Index Data Contributor; vectors are added when
AZURE_OPENAI_EMBEDDING_DEPLOYMENT answers):

    backend/.venv/Scripts/python.exe scripts/build_search_index.py [--recreate]

Only the BU catalog (data/synthetic/seed/bu_courses.csv) is indexed: public course data, no student data. Safe to
re-run: documents are upserted and courses no longer in the catalog are deleted. Restart the API afterwards so its
shortlist cache is empty.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.environ.pop("POSTGRES_HOST", None)   # the catalog comes from the seed CSV; no database needed

from app import search  # noqa: E402
from app.store import load  # noqa: E402  (seed CSVs)


def main() -> int:
    if not search.enabled():
        print("AZURE_SEARCH_ENDPOINT is not set")
        return 1
    bus = list(load().bu_courses.values())
    result = search.sync_index(bus, recreate="--recreate" in sys.argv)
    print(f"index {result['index']}: {result['documents']} BU courses, {result['deleted']} stale deleted, "
          f"vectors: {result['vector_dims'] or 'off'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
