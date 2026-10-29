"""Ingest: transcript PDF -> lines, syllabus PDF -> completeness check.

Text-based PDFs (all synthetic test files) are read with pdfplumber, offline. If a PDF yields no text (a scan) and
AZURE_DI_ENDPOINT is set, Azure AI Document Intelligence (prebuilt-layout) is used, authenticated with
DefaultAzureCredential (managed identity in the cloud; infra disables key auth). AZURE_DI_KEY is honoured only as an
optional local-dev fallback. azure-identity is imported lazily so offline tests never need it.

Upload hardening (docs/security/checklist.md section 2): `%PDF-` magic check, page limit, and every parser
failure becomes an UploadError with a generic message (never a 500 or a stack trace).
"""
from __future__ import annotations

import io
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, Union

import pdfplumber

PdfSource = Union[str, bytes]
MAX_PAGES = 30
MAX_COURSE_LINES = 60     # the longest synthetic transcript has 14; a real one rarely passes 40
MAX_TITLE_CHARS = 120     # course titles feed the AI prompt: keep them short
MAX_REF_CHARS = 40
PDF_MAGIC = b"%PDF-"
COGNITIVE_SCOPE = "https://cognitiveservices.azure.com/.default"


class UploadError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


_CREDENTIAL = None


def azure_credential():
    """Shared DefaultAzureCredential, created on first use (lazy import keeps offline tests free of azure-*)."""
    global _CREDENTIAL
    if _CREDENTIAL is None:
        from azure.identity import DefaultAzureCredential  # noqa: WPS433 (lazy on purpose)
        _CREDENTIAL = DefaultAzureCredential()
    return _CREDENTIAL


class DocumentIntelligenceAdapter:
    """Azure AI Document Intelligence, prebuilt-layout model, REST API 2024-11-30. Not exercised offline."""

    API_VERSION = "2024-11-30"

    def __init__(self, endpoint: Optional[str] = None):
        self.endpoint = (endpoint or os.environ.get("AZURE_DI_ENDPOINT") or "").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.endpoint)

    def _auth_headers(self) -> dict:
        key = os.environ.get("AZURE_DI_KEY")
        if key:                                   # local-dev fallback only; cloud uses managed identity
            return {"Ocp-Apim-Subscription-Key": key}
        return {"Authorization": f"Bearer {azure_credential().get_token(COGNITIVE_SCOPE).token}"}

    def extract_text(self, data: bytes, timeout_s: float = 60.0) -> str:  # pragma: no cover - needs Azure
        url = f"{self.endpoint}/documentintelligence/documentModels/prebuilt-layout:analyze?api-version={self.API_VERSION}"
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/pdf", **self._auth_headers()})
        with urllib.request.urlopen(req, timeout=30) as resp:
            op_url = resp.headers["Operation-Location"]
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            poll = urllib.request.Request(op_url, headers=self._auth_headers())
            with urllib.request.urlopen(poll, timeout=30) as resp:
                body = json.loads(resp.read())
            if body.get("status") == "succeeded":
                return body.get("analyzeResult", {}).get("content", "")
            if body.get("status") == "failed":
                raise RuntimeError("Document Intelligence analysis failed")
            time.sleep(1.0)
        raise TimeoutError("Document Intelligence analysis timed out")


def check_pdf_bytes(data: bytes) -> None:
    """Magic-byte type check (not Content-Type or file extension)."""
    if not data.lstrip()[:5] == PDF_MAGIC:
        raise UploadError(415, "Only PDF files are accepted")


def pdf_text(src: PdfSource, max_pages: int = MAX_PAGES) -> str:
    """Text of a PDF. Raises UploadError(422) for malformed/encrypted/oversized documents."""
    data = src if isinstance(src, bytes) else open(src, "rb").read()
    check_pdf_bytes(data)
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > max_pages:
                raise UploadError(422, f"PDF has more than {max_pages} pages")
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    except UploadError:
        raise
    except Exception:
        raise UploadError(422, "The PDF could not be read (malformed or encrypted)")
    if not text.strip():
        di = DocumentIntelligenceAdapter()
        if di.configured:                        # scanned PDF -> OCR in the cloud
            try:
                text = di.extract_text(data)
            except Exception:
                raise UploadError(422, "The PDF has no readable text")
    if not text.strip():
        raise UploadError(422, "No readable text was found in this PDF. If it is a scan or a photo, upload a "
                               "text-based PDF instead.")
    return text


# ------------------------------------------------------------------ transcripts
@dataclass
class ParsedLine:
    term: str
    course_code: str
    title: str
    credits: float
    grade: str


@dataclass
class ParsedTranscript:
    institution: str
    calendar: str
    student_ref: str
    lines: list[ParsedLine] = field(default_factory=list)


_TERM = re.compile(r"^(FALL|SPRING|SUMMER|WINTER)\s+(\d{4})$")
_COURSE = re.compile(
    r"^(?P<code>[A-Z]{2,6}(?:-[A-Z]{2})?\s\d{1,4}[A-Z]?)\s+(?P<title>.+?)\s+(?P<att>\d+(?:\.\d+)?)\s+(?P<earn>\d+(?:\.\d+)?)"
    r"\s+(?P<grade>[A-F][+-]?|P|NP|S|U|W|I)\s+(?P<qp>\d+(?:\.\d+)?|-)$")
# OCR (Document Intelligence) returns a table one cell per line: code / title / attempted / earned / grade / points.
_CODE = re.compile(r"^[A-Z]{2,6}(?:-[A-Z]{2})?\s\d{1,4}[A-Z]?$")
_NUM = re.compile(r"^\d+(?:\.\d+)?$")
_GRADE = re.compile(r"^(?:[A-F][+-]?|P|NP|S|U|W|I)$")
_POINTS = re.compile(r"^(?:\d+(?:\.\d+)?|-)$")


def _cell_course(cells: list[str]) -> Optional[tuple[tuple[str, str, str, str], int]]:
    """((code, title, attempted, grade), cells used) when consecutive OCR lines form one course row. The 'earned'
    cell may be missing (OCR drops a cell under a watermark); only 'attempted' is used."""
    if len(cells) < 5 or not _CODE.match(cells[0]) or not cells[1] or not _NUM.match(cells[2]):
        return None
    if len(cells) >= 6 and _NUM.match(cells[3]) and _GRADE.match(cells[4]) and _POINTS.match(cells[5]):
        return (cells[0], cells[1], cells[2], cells[4]), 6
    if _GRADE.match(cells[3]) and _POINTS.match(cells[4]):
        return (cells[0], cells[1], cells[2], cells[3]), 5
    return None


def parse_transcript(src: PdfSource) -> ParsedTranscript:
    return parse_transcript_text(pdf_text(src))


def parse_transcript_text(text: str) -> ParsedTranscript:
    """Transcript text (pdfplumber: one course per line; OCR: one table cell per line) -> institution, id, lines."""
    inst, cal, ref = "", "Semester", ""
    m = re.search(r"Institution:\s*(.+?)\s*\|\s*(Semester|Quarter)\s+calendar", text)
    if m:
        inst, cal = m.group(1).strip(), m.group(2)
    else:
        raise UploadError(422, "This does not look like a transcript: no 'Institution:' line was found.")
    m = re.search(r"Student ID\s+(\S+)", text)
    if m:
        ref = m.group(1)[:MAX_REF_CHARS]
    out = ParsedTranscript(inst, cal, ref)
    term = ""
    lines = [raw.strip() for raw in text.splitlines() if raw.strip()]
    i = 0
    while i < len(lines):
        line, row, step = lines[i], None, 1
        tm = _TERM.match(line)
        if tm:
            term = f"{tm.group(1).title()} {tm.group(2)}"
            i += 1
            continue
        cm = _COURSE.match(line)
        if cm:
            row = cm.group("code"), cm.group("title"), cm.group("att"), cm.group("grade")
        elif (cell := _cell_course(lines[i:i + 6])) is not None:
            row, step = cell
        if row and term:
            code, title, att, grade = row
            out.lines.append(ParsedLine(term, code, title[:MAX_TITLE_CHARS].strip(), float(att), grade))
            if len(out.lines) > MAX_COURSE_LINES:
                raise UploadError(422, f"The transcript has more than {MAX_COURSE_LINES} course lines.")
        i += step
    return out


# ------------------------------------------------------------------ syllabi (R23 completeness)
_SECTION_HEADS = r"(?:Course description|Learning outcomes|Weekly schedule|Course schedule|Schedule|Assessment|Materials and policies)"


def _section(text: str, head_regex: str) -> Optional[str]:
    m = re.search(rf"^\s*{head_regex}\s*$(.*?)(?=^\s*{_SECTION_HEADS}\s*$|\Z)", text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    return m.group(1) if m else None


def check_syllabus(text: str) -> dict:
    """Complete = learning outcomes listed AND a dated/weekly schedule present."""
    outcomes = _section(text, r"Learning outcomes") or ""
    schedule = _section(text, r"(?:Weekly schedule|Course schedule|Schedule)") or ""
    n_outcomes = len(re.findall(r"^\s*\d+[.)]\s+\S", outcomes, re.MULTILINE))
    n_weeks = len(re.findall(r"^\s*\d{1,2}\s+[A-Za-z]", schedule, re.MULTILINE))
    missing = []
    if n_outcomes < 2:
        missing.append("learning_outcomes")
    if n_weeks < 3:
        missing.append("schedule")
    code = None
    m = re.search(r"^([A-Z]{2,6}(?:-[A-Z]{2})?\s\d{1,4}[A-Z]?):\s", text, re.MULTILINE)
    if m:
        code = m.group(1)
    # Not a syllabus at all (a recipe, an invoice, …): no "CODE: title" line and no syllabus section heading.
    has_section = re.search(rf"^\s*{_SECTION_HEADS}\s*$", text, re.IGNORECASE | re.MULTILINE) is not None
    return dict(complete=not missing, missing_sections=missing, course_code=code,
                looks_like_syllabus=bool(code) or has_section)
