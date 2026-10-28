"""Upload limits (checklist section 2), input validation, CORS from env, reason codes, CSV escaping."""
import importlib
import os

from fastapi.testclient import TestClient

from app.guard import MAX_UPLOAD_BYTES

from .conftest import SEED, SYLLABI, role

SYL_URL = "/api/courses/NYU%7CPSYCH-UA%2025/syllabus"
TR_URL = "/api/students/SYN-24001/transcripts"


def make_pdf(pages: int, text: str = "Hello") -> bytes:
    """Minimal valid PDF with `pages` pages (no third-party dependency)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for i in range(pages):
        stream = f"BT /F1 12 Tf 72 720 Td ({text} {i + 1}) Tj ET"
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        content_no = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_no} 0 R "
                    f"/Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>"
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def test_make_pdf_is_readable():
    from app.ingest import pdf_text
    assert "Hello 3" in pdf_text(make_pdf(3))


def test_oversize_upload_413_by_content_length(client):
    big = b"%PDF-1.4\n" + b"0" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(SYL_URL, files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413


def test_oversize_upload_413_when_chunked(client):
    """No Content-Length: the guard counts streamed bytes and stops at the limit."""
    def gen():
        yield b"--b\r\nContent-Disposition: form-data; name=\"file\"; filename=\"x.pdf\"\r\n\r\n%PDF-1.4\n"
        chunk = b"0" * (1024 * 1024)
        for _ in range(12):
            yield chunk
        yield b"\r\n--b--\r\n"
    r = client.post(SYL_URL, content=gen(), headers={"Content-Type": "multipart/form-data; boundary=b",
                                                     "X-Demo-Role": "Evaluator"})
    assert r.status_code == 413


def test_upload_at_limit_is_not_413(client):
    """Exactly 10 MB of junk after the magic -> passes the size check, then fails parsing cleanly (422)."""
    data = b"%PDF-1.4\n" + b"0" * (MAX_UPLOAD_BYTES - 9)
    assert len(data) == MAX_UPLOAD_BYTES
    assert client.post(SYL_URL, files={"file": ("a.pdf", data, "application/pdf")}).status_code == 422


def test_non_pdf_is_415(client):
    r = client.post(SYL_URL, files={"file": ("evil.pdf", b"<html>not a pdf</html>", "application/pdf")})
    assert r.status_code == 415
    r = client.post(TR_URL, files={"file": ("t.pdf", b"PK\x03\x04zip", "application/pdf")}, headers=role("Student"))
    assert r.status_code == 415


def test_malformed_pdf_is_422_not_500(client):
    for junk in (b"%PDF-1.7\n garbage garbage", b"%PDF-" + os.urandom(2048)):
        r = client.post(SYL_URL, files={"file": ("m.pdf", junk, "application/pdf")})
        assert r.status_code == 422
        assert "Traceback" not in r.text and "/home" not in r.text
        r = client.post(TR_URL, files={"file": ("m.pdf", junk, "application/pdf")}, headers=role("CreditStaff"))
        assert r.status_code == 422


def test_page_limit(client):
    assert client.post(SYL_URL, files={"file": ("p.pdf", make_pdf(30), "application/pdf")}).status_code == 201
    r = client.post(SYL_URL, files={"file": ("p.pdf", make_pdf(31), "application/pdf")})
    assert r.status_code == 422 and "30 pages" in r.json()["detail"]


def test_real_syllabus_still_accepted(client):
    with open(os.path.join(SYLLABI, "Syllabus_NYU_PSYCH-UA-25.pdf"), "rb") as f:
        assert client.post(SYL_URL, files={"file": ("s.pdf", f, "application/pdf")}).status_code == 201


def test_path_param_validation(client):
    assert client.get("/api/students/SYN-24001%3BDROP/evaluation").status_code == 422
    assert client.get("/api/students/" + "A" * 40 + "/evaluation").status_code == 422
    assert client.get("/api/courses/..%7C..etc/recommendation").status_code == 422
    assert client.get("/api/courses/..%7C..%2Fetc/recommendation").status_code in (404, 422)   # slash: no route
    assert client.get("/api/courses/nyu%7Cpsych/recommendation").status_code == 422
    assert client.get("/api/courses/NYU%7CNOPE%201/recommendation").status_code == 404     # valid shape, unknown
    assert client.get("/api/exports/mybu.csv", params={"student_id": "x;y"}, headers=role("Registrar")).status_code == 422
    bad = dict(ext_id="<script>", decision="Equivalent", bu_course="X", reason_code="EQ-CONTENT", evaluator="E")
    assert client.post("/api/decisions", json=bad).status_code == 422
    assert client.post("/api/decisions/batch", json={"ext_ids": ["bad id"], "evaluator": "E"}).status_code == 422


def test_reason_codes(client):
    import csv
    want = list(csv.DictReader(open(os.path.join(SEED, "reason_codes.csv"), encoding="utf-8")))
    got = client.get("/api/reason-codes", headers=role("Student")).json()
    assert got == [dict(reason_code=r["reason_code"], decision=r["decision"], meaning=r["meaning"]) for r in want]
    assert len(got) == 22


def test_cors_origins_from_env(monkeypatch):
    import app.main as main_mod
    monkeypatch.setenv("TRANSFERIQ_CORS_ORIGINS", "https://a.example, https://b.example,*")
    assert main_mod.cors_origins() == ["https://a.example", "https://b.example"]
    monkeypatch.delenv("TRANSFERIQ_CORS_ORIGINS")
    assert main_mod.cors_origins() == ["http://localhost:4200"]
    monkeypatch.setenv("TRANSFERIQ_CORS_ORIGINS", "https://swa.example")
    reloaded = importlib.reload(main_mod)
    try:
        c = TestClient(reloaded.app)
        pre = {"Origin": "https://swa.example", "Access-Control-Request-Method": "GET",
               "Access-Control-Request-Headers": "X-Demo-Role"}
        assert c.options("/api/students", headers=pre).headers.get("access-control-allow-origin") == "https://swa.example"
        assert "access-control-allow-origin" not in c.options("/api/students", headers=dict(pre, Origin="http://localhost:4200")).headers
    finally:
        monkeypatch.delenv("TRANSFERIQ_CORS_ORIGINS")
        importlib.reload(main_mod)


def test_csv_formula_escaping():
    from app.main import _csv_safe
    assert _csv_safe("=HYPERLINK(1)") == "'=HYPERLINK(1)" and _csv_safe("@x") == "'@x" and _csv_safe("CAS PS 101") == "CAS PS 101"
