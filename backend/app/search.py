"""Azure AI Search: the candidate shortlist of BU courses for the model (matcher._azure_rank).

Enabled when AZURE_SEARCH_ENDPOINT is set; AZURE_SEARCH_INDEX (default bu-courses). Auth: AZURE_SEARCH_API_KEY if set
(local dev), else DefaultAzureCredential (the API's managed identity needs Search Index Data Reader; building the
index needs an admin key or Search Service Contributor + Search Index Data Contributor).

The index holds the BU catalog only (public course data, no student data). Retrieval uses what the service offers:
- keyword (BM25) always;
- semantic ranking when the index has the `default` semantic configuration and the service's semantic ranker is on;
- vectors when AZURE_OPENAI_EMBEDDING_DEPLOYMENT answers and the index was built with a vector field.
A feature the service rejects (HTTP 400) is dropped for the rest of the process. Any other failure returns None and the
matcher keeps the offline shortlist, so search can never break a page (ADR 0003: offline still works without Azure).

Query text is built from the external course only (title, description, outcomes, topics, sanitised syllabus): never a
student name, ID or grade. It is reduced to plain words, so search syntax and injected instructions cannot steer it.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Optional

from .safety import sanitize

log = logging.getLogger("transferiq.search")

API_VERSION = "2024-07-01"
SEARCH_SCOPE = "https://search.azure.com/.default"
SEMANTIC_CONFIG = "default"
VECTOR_FIELD = "content_vector"
MAX_QUERY_TERMS = 120           # plain words sent as the keyword query
MAX_EMBED_CHARS = 8000          # well under the embedding models' 8191-token input limit
TIMEOUT_S = 10
_disabled_features: set[str] = set()     # "semantic" / "vector" once the service rejected them
_lock = threading.Lock()
_EMBED_CACHE: "OrderedDict[str, list[float]]" = OrderedDict()
_EMBED_CACHE_MAX = 2048
# Shortlists by query text: they change only when the course text or the index changes (restart after a rebuild).
_SHORTLIST_CACHE: "OrderedDict[str, list[str]]" = OrderedDict()
_SHORTLIST_CACHE_MAX = 2048


class SearchError(Exception):
    pass


def endpoint() -> str:
    return os.environ.get("AZURE_SEARCH_ENDPOINT", "").strip().rstrip("/")


def enabled() -> bool:
    return bool(endpoint())


def index_name() -> str:
    return os.environ.get("AZURE_SEARCH_INDEX", "").strip() or "bu-courses"


def reset() -> None:
    """Forget dropped features and cached embeddings (tests, or after rebuilding the index)."""
    with _lock:
        _disabled_features.clear()
        _EMBED_CACHE.clear()
        _SHORTLIST_CACHE.clear()


# ------------------------------------------------------------------ HTTP
def _headers() -> dict:
    key = os.environ.get("AZURE_SEARCH_API_KEY", "").strip()
    if key:
        return {"api-key": key}
    from .ingest import azure_credential
    return {"Authorization": f"Bearer {azure_credential().get_token(SEARCH_SCOPE).token}"}


def _request(method: str, path: str, body: Optional[dict] = None) -> dict:
    """One call to the Search REST API. Retries once on 429/503 (throttling); raises SearchError otherwise."""
    url = f"{endpoint()}{path}{'&' if '?' in path else '?'}api-version={API_VERSION}"
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(2):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json", **_headers()})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
                raw = resp.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt == 0:
                time.sleep(1.0)
                continue
            detail = e.read().decode("utf-8", "replace")[:300]
            raise SearchError(f"{e.code} {detail}") from e
        except Exception as e:                       # timeout, DNS, TLS, …
            raise SearchError(type(e).__name__) from e
    raise SearchError("throttled")


# ------------------------------------------------------------------ embeddings (optional)
def embedding_deployment() -> str:
    return os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "").strip()


def _embedding_target() -> tuple[str, dict]:
    """Endpoint and auth for embeddings. AZURE_OPENAI_EMBEDDING_ENDPOINT (+ _API_KEY) points at another Azure OpenAI /
    Foundry resource, e.g. in a region with embedding quota; otherwise the chat model's resource and auth are used."""
    own = os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT", "").strip()
    if own:
        key = os.environ.get("AZURE_OPENAI_EMBEDDING_API_KEY", "").strip()
        if key:
            return own.rstrip("/"), {"api-key": key}
        from .ingest import azure_credential
        return own.rstrip("/"), {"Authorization": "Bearer " + azure_credential().get_token(
            "https://cognitiveservices.azure.com/.default").token}
    from .matcher import _openai_auth_headers       # same auth as the chat model (lazy: matcher imports this module)
    return os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/"), _openai_auth_headers()


def embed(text: str) -> Optional[list[float]]:
    """Embedding of `text`, or None when no embedding deployment is configured or it fails."""
    dep = embedding_deployment()
    if not dep or "vector" in _disabled_features or not (
            os.environ.get("AZURE_OPENAI_EMBEDDING_ENDPOINT") or os.environ.get("AZURE_OPENAI_ENDPOINT")):
        return None
    text = text[:MAX_EMBED_CHARS]
    key = hashlib.sha256(f"{dep}\n{text}".encode()).hexdigest()
    with _lock:
        if key in _EMBED_CACHE:
            _EMBED_CACHE.move_to_end(key)
            return list(_EMBED_CACHE[key])
    version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01")
    try:
        base, auth = _embedding_target()
        req = urllib.request.Request(f"{base}/openai/deployments/{dep}/embeddings?api-version={version}",
                                     data=json.dumps({"input": text}).encode(), method="POST",
                                     headers={"Content-Type": "application/json", **auth})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            vec = json.loads(resp.read())["data"][0]["embedding"]
    except urllib.error.HTTPError as e:
        if e.code == 404:                            # no such deployment: stop trying for this process
            with _lock:
                _disabled_features.add("vector")
            log.warning("embedding deployment %r not found; vector search off", dep)
        return None
    except Exception:
        return None
    with _lock:
        _EMBED_CACHE[key] = vec
        while len(_EMBED_CACHE) > _EMBED_CACHE_MAX:
            _EMBED_CACHE.popitem(last=False)
    return list(vec)


# ------------------------------------------------------------------ index (BU catalog)
def _bu_text(b) -> str:
    return " . ".join([b.title, b.description, *b.learning_outcomes, *b.topics])


def doc_key(bu_code: str) -> str:
    """Document key: keys allow only letters, digits, _ - =, and BU codes contain spaces, so URL-safe base64."""
    return base64.urlsafe_b64encode(bu_code.encode()).decode()


def index_definition(vector_dims: Optional[int]) -> dict:
    fields = [
        dict(name="id", type="Edm.String", key=True, searchable=False),
        dict(name="bu_code", type="Edm.String", filterable=True, searchable=False),
        dict(name="dept", type="Edm.String", filterable=True, searchable=False),
        dict(name="title", type="Edm.String", searchable=True),
        dict(name="description", type="Edm.String", searchable=True),
        dict(name="learning_outcomes", type="Collection(Edm.String)", searchable=True),
        dict(name="topics", type="Collection(Edm.String)", searchable=True),
        dict(name="content_hash", type="Edm.String", filterable=True, searchable=False),
    ]
    out = dict(name=index_name(), fields=fields, semantic=dict(configurations=[dict(
        name=SEMANTIC_CONFIG, prioritizedFields=dict(
            titleField=dict(fieldName="title"),
            prioritizedContentFields=[dict(fieldName="description"), dict(fieldName="learning_outcomes")],
            prioritizedKeywordsFields=[dict(fieldName="topics")]))]))
    if vector_dims:
        fields.append(dict(name=VECTOR_FIELD, type="Collection(Edm.Single)", searchable=True, retrievable=False,
                           dimensions=vector_dims, vectorSearchProfile="vprofile"))
        out["vectorSearch"] = dict(algorithms=[dict(name="hnsw", kind="hnsw")],
                                   profiles=[dict(name="vprofile", algorithm="hnsw")])
    return out


def sync_index(bus: list, recreate: bool = False) -> dict:
    """Create (or recreate) the index and make its documents match the BU catalog exactly. Needs admin rights.
    Vectors are included when an embedding deployment answers; the field size is taken from the model."""
    sample = embed(_bu_text(bus[0])) if bus else None
    dims = len(sample) if sample else None
    existing = None
    try:
        existing = _request("GET", f"/indexes/{index_name()}")
    except SearchError as e:
        if not str(e).startswith("404"):
            raise
    wanted = {f["name"] for f in index_definition(dims)["fields"]}
    if existing and (recreate or {f["name"] for f in existing.get("fields", [])} != wanted):   # layout changed
        _request("DELETE", f"/indexes/{index_name()}")
        existing = None
    if not existing:
        _request("PUT", f"/indexes/{index_name()}", index_definition(dims))
    docs = []
    for b in bus:
        text = _bu_text(b)
        doc = {"@search.action": "mergeOrUpload", "id": doc_key(b.bu_code), "bu_code": b.bu_code, "dept": b.dept, "title": b.title,
               "description": b.description, "learning_outcomes": list(b.learning_outcomes),
               "topics": list(b.topics), "content_hash": hashlib.sha256(text.encode()).hexdigest()}
        if dims:
            vec = embed(text)
            if vec is None or len(vec) != dims:
                raise SearchError(f"embedding failed for {b.bu_code}")
            doc[VECTOR_FIELD] = vec
        docs.append(doc)
    for i in range(0, len(docs), 500):
        _request("POST", f"/indexes/{index_name()}/docs/index", {"value": docs[i:i + 500]})
    keep = {b.bu_code for b in bus}
    found = _request("POST", f"/indexes/{index_name()}/docs/search", {"search": "*", "select": "id,bu_code", "top": 1000})
    stale = [d["id"] for d in found.get("value", []) if d.get("bu_code") not in keep]
    if stale:
        _request("POST", f"/indexes/{index_name()}/docs/index",
                 {"value": [{"@search.action": "delete", "id": c} for c in stale]})
    return dict(index=index_name(), documents=len(docs), deleted=len(stale), vector_dims=dims)


# ------------------------------------------------------------------ query
def query_text(course, syllabus_text: str) -> str:
    """Plain words from the external course: no search operators, no injected sentences, bounded length."""
    raw = sanitize(" . ".join([course.title, course.description, *course.learning_outcomes, *course.topics,
                               syllabus_text or ""]))
    words, seen = [], set()
    for w in re.findall(r"[A-Za-z][A-Za-z0-9]+", raw):
        lw = w.lower()
        if lw not in seen:
            seen.add(lw)
            words.append(w)
        if len(words) >= MAX_QUERY_TERMS:
            break
    return " ".join(words)


def shortlist(course, syllabus_text: str, k: int = 10) -> Optional[list[str]]:
    """Up to k BU codes, best first, or None when search is off or failed (the caller keeps its own shortlist)."""
    if not enabled():
        return None
    q = query_text(course, syllabus_text)
    if not q:
        return None
    ckey = hashlib.sha256(f"{index_name()}\n{k}\n{q}\n{course.description}\n{syllabus_text}".encode()).hexdigest()
    with _lock:
        if ckey in _SHORTLIST_CACHE:
            _SHORTLIST_CACHE.move_to_end(ckey)
            return list(_SHORTLIST_CACHE[ckey])
    codes = _search(course, syllabus_text, q, k)
    if codes:                                           # failures are not cached: the next request retries
        with _lock:
            _SHORTLIST_CACHE[ckey] = codes
            while len(_SHORTLIST_CACHE) > _SHORTLIST_CACHE_MAX:
                _SHORTLIST_CACHE.popitem(last=False)
    return codes


def _search(course, syllabus_text: str, q: str, k: int) -> Optional[list[str]]:
    vec = embed(" . ".join([course.title, course.description, *course.learning_outcomes, *course.topics,
                            sanitize(syllabus_text or "")]))
    for _ in range(3):                                  # at most: full, then without semantic, then without vector
        body = {"search": q, "searchMode": "any", "queryType": "simple", "select": "bu_code", "top": k}
        use_semantic = "semantic" not in _disabled_features
        use_vector = vec is not None and "vector" not in _disabled_features
        if use_semantic:
            body.update(queryType="semantic", semanticConfiguration=SEMANTIC_CONFIG)
        if use_vector:
            body["vectorQueries"] = [dict(kind="vector", vector=vec, fields=VECTOR_FIELD, k=k)]
        try:
            res = _request("POST", f"/indexes/{index_name()}/docs/search", body)
            return [d["bu_code"] for d in res.get("value", [])][:k]
        except SearchError as e:
            if str(e).startswith("400") and (use_semantic or use_vector):
                msg = str(e).lower()
                feature = ("vector" if use_vector and "vector" in msg and "semantic" not in msg
                           else "semantic" if use_semantic else "vector")
                with _lock:
                    _disabled_features.add(feature)
                log.warning("search rejected %s; retrying without it: %s", feature, e)
                continue
            log.warning("search failed, using the offline shortlist: %s", e)
            return None
    return None
