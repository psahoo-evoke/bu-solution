"""Portal accounts (TRANSFERIQ_AUTH_MODE=portal): per-user sign-in for students, departments and staff.

- Seeded accounts: the four sample students (student_loginsample.txt), one account per academic department and one
  per staff role. Their password is TRANSFERIQ_DEMO_PASSWORD (default "admin"): a hackathon convenience for
  synthetic data only, never for real users.
- Self-registration: a student account creates a new (empty) student record; a department account is bound to one
  department. Passwords are stored as salted PBKDF2-SHA256 hashes.
- Sessions: HS256 JWT signed with TRANSFERIQ_SESSION_SECRET (random per process when unset, so a restart signs
  everyone out).
- Persistence: registered accounts and the student records they created are saved to Blob Storage
  (<accounts container>/accounts.json, via app/blob_store.py) BEFORE a registration is accepted, and loaded at start-up,
  so they survive restarts. Only password hashes are stored. If the document cannot be read, registration is refused
  (never overwrite stored accounts with a partial list). Without a blob endpoint (tests, local) they stay in memory.
  A demo reset keeps them and re-creates registered students' records.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from . import blob_store
from . import store as store_mod
from .store import Student

log = logging.getLogger("transferiq.accounts")

ACCOUNTS_BLOB = "accounts.json"
SESSION_HOURS = 8
PASSWORD_MIN = 5
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@bu\.edu$")
STAFF_ROLES = ("Evaluator", "CreditStaff", "Registrar", "Advisor")
PORTALS = {"student": {"Student"}, "department": {"Department"}, "staff": set(STAFF_ROLES)}

SAMPLE_STUDENTS = {   # student_loginsample.txt
    "SYN-24001": "maya.delgado@bu.edu",
    "SYN-24002": "jordan.reyes@bu.edu",
    "SYN-24003": "aisha.bello@bu.edu",
    "SYN-24004": "liam.novak@bu.edu",
}
ACADEMIC_DEPARTMENTS = ("Psychology", "Biology", "Economics", "Computer Science", "Mathematics", "General education")
STAFF_ACCOUNTS = {"Evaluator": "evaluator@bu.edu", "CreditStaff": "creditstaff@bu.edu",
                  "Registrar": "registrar@bu.edu", "Advisor": "advisor@bu.edu"}
STAFF_NAMES = {"Evaluator": "Transfer Evaluator", "CreditStaff": "Transfer Credit Staff",
               "Registrar": "Registrar's Office", "Advisor": "Academic Advisor"}


class AccountError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


@dataclass
class Account:
    email: str
    name: str
    role: str
    password_hash: str
    student_id: Optional[str] = None
    department: Optional[str] = None
    registered: bool = False          # self-registered (vs seeded)

    def public(self) -> dict:
        return dict(email=self.email, name=self.name, role=self.role, student_id=self.student_id,
                    department=self.department)


@dataclass
class _Registry:
    accounts: dict[str, Account] = field(default_factory=dict)
    students: list[Student] = field(default_factory=list)       # records created by registration
    lock: threading.Lock = field(default_factory=threading.Lock)
    loaded: bool = True                                          # False: stored accounts could not be read yet


def dept_email(department: str) -> str:
    return re.sub(r"[^a-z]", "", department.lower()) + ".dept@bu.edu"


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1], digest_hex)


def _seed() -> _Registry:
    reg = _Registry()
    pw = hash_password(os.environ.get("TRANSFERIQ_DEMO_PASSWORD", "admin"))
    for sid, email in SAMPLE_STUDENTS.items():
        st = store_mod.STORE.students.get(sid)
        reg.accounts[email] = Account(email, st.name if st else sid, "Student", pw, student_id=sid)
    for dept in ACADEMIC_DEPARTMENTS:
        reg.accounts[dept_email(dept)] = Account(dept_email(dept), f"{dept} Department", "Department", pw,
                                                 department=dept)
    for role, email in STAFF_ACCOUNTS.items():
        reg.accounts[email] = Account(email, STAFF_NAMES[role], role, pw)
    _load_registered(reg)
    return reg


# ------------------------------------------------------------------ persistence (Blob Storage)
def _load_registered(reg: _Registry) -> None:
    """Merge stored registrations into the registry and the store. On a read error the registry is marked not
    loaded; registration stays refused until a later read succeeds."""
    try:
        doc = blob_store.load_json("accounts", ACCOUNTS_BLOB)
    except (blob_store.BlobStoreError, ValueError) as e:      # ValueError: unreadable JSON
        reg.loaded = False
        log.error("stored accounts could not be read; registration is paused: %s", e)
        return
    reg.loaded = True
    if not doc:
        return
    for s in doc.get("students", []):
        st = Student(s["student_id"], s["name"], s["intended_major"], s["bu_start_term"])
        if all(x.student_id != st.student_id for x in reg.students):
            reg.students.append(st)
        with store_mod.STORE.lock:
            store_mod.STORE.students.setdefault(st.student_id, st)
    for a in doc.get("accounts", []):
        if a["email"] not in reg.accounts:                       # seeded accounts always win
            reg.accounts[a["email"]] = Account(a["email"], a["name"], a["role"], a["password_hash"],
                                               student_id=a.get("student_id"), department=a.get("department"),
                                               registered=True)
    log.info("loaded %d registered account(s) from storage", sum(a.registered for a in reg.accounts.values()))


def _save_registered(reg: _Registry) -> None:
    """Write all registrations. Caller holds reg.lock. Raises AccountError when they cannot be stored."""
    if not blob_store.enabled():
        return
    doc = dict(
        version=1,
        accounts=[dict(email=a.email, name=a.name, role=a.role, password_hash=a.password_hash,
                       student_id=a.student_id, department=a.department)
                  for a in reg.accounts.values() if a.registered],
        students=[dict(student_id=s.student_id, name=s.name, intended_major=s.intended_major,
                       bu_start_term=s.bu_start_term) for s in reg.students],
    )
    try:
        blob_store.save_json("accounts", ACCOUNTS_BLOB, doc)
    except blob_store.BlobStoreError:
        raise AccountError(502, "Could not save your account. Please try again.")


def _ensure_loaded(reg: _Registry) -> None:
    """Caller holds reg.lock. Before accepting a registration, stored accounts must be known (duplicate check and
    no overwrite with a partial list): retry a failed start-up read, refuse while storage stays unreadable."""
    if blob_store.enabled() and not reg.loaded:
        _load_registered(reg)
        if not reg.loaded:
            raise AccountError(503, "Registration is temporarily unavailable. Please try again in a few minutes.")


REGISTRY = _seed()


def reset_accounts() -> None:
    """Tests: back to the seeded accounts only."""
    global REGISTRY
    REGISTRY = _seed()


def restore_registered_students() -> None:
    """After a demo reset of the store, put registered students' records back so their accounts still work."""
    with store_mod.STORE.lock:
        for st in REGISTRY.students:
            store_mod.STORE.students.setdefault(st.student_id, st)


def departments() -> list[str]:
    return list(ACADEMIC_DEPARTMENTS)


# ------------------------------------------------------------------ sign-in and registration
def _norm_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AccountError(422, "Use your BU email address (name@bu.edu)")
    return email


def _check_new_password(password: str) -> None:
    if len(password or "") < PASSWORD_MIN:
        raise AccountError(422, f"Password must be at least {PASSWORD_MIN} characters")


def authenticate(email: str, password: str, portal: str) -> Account:
    email = _norm_email(email)
    acct = REGISTRY.accounts.get(email)
    if acct is None:
        raise AccountError(404, "No account found for this email. Register first.")
    if not check_password(password or "", acct.password_hash):
        raise AccountError(401, "Incorrect password")
    allowed = PORTALS.get(portal, set())
    if acct.role not in allowed:
        where = "Student" if acct.role == "Student" else "Department" if acct.role == "Department" else "Staff"
        raise AccountError(403, f"This is a {acct.role} account. Use the {where} sign-in.")
    return acct


def register_student(name: str, email: str, password: str, intended_major: str, start_term: str) -> Account:
    email, name = _norm_email(email), (name or "").strip()
    if not 2 <= len(name) <= 80:
        raise AccountError(422, "Enter your full name")
    if not (intended_major or "").strip():
        raise AccountError(422, "Choose your intended major")
    _check_new_password(password)
    with REGISTRY.lock:
        _ensure_loaded(REGISTRY)
        if email in REGISTRY.accounts:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        with store_mod.STORE.lock:
            taken = [int(s[4:]) for s in store_mod.STORE.students if re.fullmatch(r"SYN-\d+", s)]
            taken += [int(s.student_id[4:]) for s in REGISTRY.students]   # ids survive a store reset
            sid = f"SYN-{max(taken, default=24000) + 1}"
            st = Student(sid, name, intended_major.strip()[:60], (start_term or "Fall 2026").strip()[:20])
            store_mod.STORE.students[sid] = st
        REGISTRY.students.append(st)
        acct = Account(email, name, "Student", hash_password(password), student_id=sid, registered=True)
        REGISTRY.accounts[email] = acct
        try:
            _save_registered(REGISTRY)
        except AccountError:                                     # not stored -> not registered
            del REGISTRY.accounts[email]
            REGISTRY.students.remove(st)
            with store_mod.STORE.lock:
                store_mod.STORE.students.pop(sid, None)
            raise
    return acct


def register_department(name: str, email: str, password: str, department: str) -> Account:
    email, name = _norm_email(email), (name or "").strip()
    if not 2 <= len(name) <= 80:
        raise AccountError(422, "Enter your full name")
    if department not in ACADEMIC_DEPARTMENTS:
        raise AccountError(422, "Choose a department from the list")
    _check_new_password(password)
    with REGISTRY.lock:
        _ensure_loaded(REGISTRY)
        if email in REGISTRY.accounts:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        acct = Account(email, name, "Department", hash_password(password), department=department, registered=True)
        REGISTRY.accounts[email] = acct
        try:
            _save_registered(REGISTRY)
        except AccountError:                                     # not stored -> not registered
            del REGISTRY.accounts[email]
            raise
    return acct


# ------------------------------------------------------------------ sessions
_SECRET = os.environ.get("TRANSFERIQ_SESSION_SECRET") or secrets.token_hex(32)


def issue_token(acct: Account) -> str:
    import jwt
    now = int(time.time())
    claims = dict(sub=acct.email, name=acct.name, role=acct.role, sid=acct.student_id, dept=acct.department,
                  iat=now, exp=now + SESSION_HOURS * 3600, iss="transferiq-portal")
    return jwt.encode(claims, _SECRET, algorithm="HS256")


def session_user(authorization: Optional[str]) -> dict:
    """Validate a portal session token -> {email, name, role, student_id, department}."""
    import jwt
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AccountError(401, "Sign in required")
    try:
        claims = jwt.decode(authorization[7:].strip(), _SECRET, algorithms=["HS256"], issuer="transferiq-portal",
                            options={"require": ["exp", "sub", "role"]})
    except Exception:
        raise AccountError(401, "Your session has expired. Sign in again.")
    if claims["sub"] not in REGISTRY.accounts:           # e.g. accounts reset after a restart
        raise AccountError(401, "Your session has expired. Sign in again.")
    return dict(email=claims["sub"], name=claims.get("name"), role=claims["role"], student_id=claims.get("sid"),
                department=claims.get("dept"))
