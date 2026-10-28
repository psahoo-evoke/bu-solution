"""ADR 0004: syllabus text is untrusted. Regex pre-filter for instructions aimed at automated systems.

No imports from the rest of the app, so the store and the matcher can both use it."""
from __future__ import annotations

import re

# ------------------------------------------------------------------ ADR 0004: injection pre-filter
INJECTION_PATTERNS = [
    r"\bignore\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|prompts?|rules)",
    r"\bdisregard\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier|your)\s+(?:instructions|prompts?|rules)",
    r"\bforget\s+(?:all\s+)?(?:your|previous|prior)\s+instructions",
    r"\brecommend\s+this\s+course\b.{0,120}?(?:100\s*%|full\s+equivalent|equivalent\s+to\s+any)",
    r"\bwith\s+100\s*%\s+confidence\b",
    r"\b(?:note|message|instruction)s?\s+(?:for|to)\s+(?:automated|ai|llm|machine)\b.{0,40}?(?:systems?|reviewers?|models?)",
    r"\byou\s+are\s+now\s+(?:an?|the)\b",
    r"\bsystem\s+prompt\b",
]
_INJ = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]


def detect_injection(text: str) -> bool:
    flat = re.sub(r"\s+", " ", text or "")
    return any(p.search(flat) for p in _INJ)


def sanitize(text: str) -> str:
    """Drop every sentence that matches an injection pattern (the rest of the syllabus is kept)."""
    flat = re.sub(r"\s+", " ", text or "")
    sentences = re.split(r"(?<=[.!?])\s+", flat)
    return " ".join(s for s in sentences if not any(p.search(s) for p in _INJ))
