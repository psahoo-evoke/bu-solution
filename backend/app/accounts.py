"""Portal accounts (TRANSFERIQ_AUTH_MODE=portal): per-user sign-in for students, departments and staff.

- Seeded accounts: the four sample students (student_loginsample.txt), one account per academic department and one
  per staff role. Their password is TRANSFERIQ_DEMO_PASSWORD (default "admin"): a hackathon convenience for
  synthetic data only, never for real users.
- Self-registration: a student account creates a new (empty) student record; a department account is bound to one
  department. Passwords are stored as salted PBKDF2-SHA256 hashes.
- Sessions: HS256 JWT signed with TRANSFERIQ_SESSION_SECRET (random per process when unset, so a restart signs
  everyone out). Accounts live in memory like the rest of the store (ADR: in-memory demo store); a demo reset keeps
  them and re-creates registered students' records.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from . import store as store_mod
from .store import Student

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
    return reg


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
        if email in REGISTRY.accounts:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        with store_mod.STORE.lock:
            taken = [int(s[4:]) for s in store_mod.STORE.students if re.fullmatch(r"SYN-\d+", s)]
            sid = f"SYN-{max(taken, default=24000) + 1}"
            st = Student(sid, name, intended_major.strip()[:60], (start_term or "Fall 2026").strip()[:20])
            store_mod.STORE.students[sid] = st
        REGISTRY.students.append(st)
        acct = Account(email, name, "Student", hash_password(password), student_id=sid, registered=True)
        REGISTRY.accounts[email] = acct
    return acct


def register_department(name: str, email: str, password: str, department: str) -> Account:
    email, name = _norm_email(email), (name or "").strip()
    if not 2 <= len(name) <= 80:
        raise AccountError(422, "Enter your full name")
    if department not in ACADEMIC_DEPARTMENTS:
        raise AccountError(422, "Choose a department from the list")
    _check_new_password(password)
    with REGISTRY.lock:
        if email in REGISTRY.accounts:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        acct = Account(email, name, "Department", hash_password(password), department=department, registered=True)
        REGISTRY.accounts[email] = acct
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
