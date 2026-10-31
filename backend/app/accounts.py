"""Portal accounts (TRANSFERIQ_AUTH_MODE=portal): per-user sign-in for students, departments and staff.

- Seeded accounts: the four sample students (student_loginsample.txt), one account per academic department and one
  per staff role. Their password is TRANSFERIQ_DEMO_PASSWORD (default "admin"): a hackathon convenience for
  synthetic data only, never for real users.
- Self-registration: a student account creates a new (empty) student record; a department account is bound to one
  department. Passwords are stored as salted PBKDF2-SHA256 hashes.
- Sessions: HS256 JWT signed with TRANSFERIQ_SESSION_SECRET (random per process when unset, so a restart signs
  everyone out).
- Staff registration (Advisor, FinancialAid, Evaluator, CreditStaff, Registrar) needs the staff invite code in
  TRANSFERIQ_STAFF_INVITE_CODE (default "bu-staff", a demo convenience like the demo password; set it to an empty
  value to switch staff registration off). Without the code anyone could register as Registrar and post credit.
- PostgreSQL (POSTGRES_HOST set): the portal_accounts table is the only store. Seeded and registered accounts are
  rows in it (seeded = true for the demo ones, which are inserted at start-up and refreshed when the demo password
  changes); sign-in, registration and every session check read or write the table, nothing is cached in memory, so a
  change in the table applies on the next request. Only password hashes are stored. A demo reset keeps the table.
- Without a database (tests, local runs; ADR 0003) accounts live in the in-memory REGISTRY. There, registered accounts
  and their student records can be saved to Blob Storage (<accounts container>/accounts.json, via app/blob_store.py)
  BEFORE a registration is accepted and are loaded at start-up; if that document cannot be read, registration is
  refused (never overwrite stored accounts with a partial list).
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

from . import blob_store, db
from . import store as store_mod
from .store import Student

log = logging.getLogger("transferiq.accounts")

ACCOUNTS_BLOB = "accounts.json"
SESSION_HOURS = 8
PASSWORD_MIN = 5
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$")   # any domain, not only bu.edu
STAFF_ROLES = ("Evaluator", "CreditStaff", "Registrar", "Advisor", "FinancialAid")
PORTALS = {"student": {"Student"}, "department": {"Department"}, "staff": set(STAFF_ROLES)}

SAMPLE_STUDENTS = {   # student_loginsample.txt
    "SYN-24001": "maya.delgado@bu.edu",
    "SYN-24002": "jordan.reyes@bu.edu",
    "SYN-24003": "aisha.bello@bu.edu",
    "SYN-24004": "liam.novak@bu.edu",
}
ACADEMIC_DEPARTMENTS = ("Psychology", "Biology", "Economics", "Computer Science", "Mathematics", "General education")
STAFF_ACCOUNTS = {"Evaluator": "evaluator@bu.edu", "CreditStaff": "creditstaff@bu.edu",
                  "Registrar": "registrar@bu.edu", "Advisor": "advisor@bu.edu",
                  "FinancialAid": "financialaid@bu.edu"}
STAFF_NAMES = {"Evaluator": "Transfer Evaluator", "CreditStaff": "Transfer Credit Staff",
               "Registrar": "Registrar's Office", "Advisor": "Academic Advisor",
               "FinancialAid": "Financial Aid Office"}


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


STAFF_INVITE_ENV = "TRANSFERIQ_STAFF_INVITE_CODE"


def staff_invite_code() -> str:
    """The code a new staff member must enter; empty means staff registration is switched off."""
    return os.environ.get(STAFF_INVITE_ENV, "bu-staff").strip()


def staff_registration_open() -> bool:
    return bool(staff_invite_code())


def _demo_password() -> str:
    return os.environ.get("TRANSFERIQ_DEMO_PASSWORD", "admin")


def _seeded_accounts(pw_hash: str, only_known_students: bool = False) -> list[Account]:
    """The demo accounts: sample students, one per department, one per staff role. With only_known_students, a
    sample student missing from the store is skipped (the table links accounts to student records)."""
    out: list[Account] = []
    for sid, email in SAMPLE_STUDENTS.items():
        st = store_mod.STORE.students.get(sid)
        if st is None and only_known_students:
            continue
        out.append(Account(email, st.name if st else sid, "Student", pw_hash, student_id=sid))
    for dept in ACADEMIC_DEPARTMENTS:
        out.append(Account(dept_email(dept), f"{dept} Department", "Department", pw_hash, department=dept))
    for role, email in STAFF_ACCOUNTS.items():
        out.append(Account(email, STAFF_NAMES[role], role, pw_hash))
    return out


def sync_seeded_accounts() -> None:
    """PostgreSQL mode: make sure every demo account is a row in portal_accounts, with the current demo password.
    Accounts people registered themselves are never touched; a registered account that already uses a demo email
    keeps it."""
    pw = _demo_password()
    wanted = _seeded_accounts(hash_password(pw), only_known_students=True)
    have = {r["email"]: r for r in db.load_accounts()}
    if not any(not r["seeded"] for r in have.values()):
        _import_blob_accounts()                                  # one-off: accounts saved before PostgreSQL was used
        have = {r["email"]: r for r in db.load_accounts()}
    new, changed = [], []
    for a in wanted:
        row = have.get(a.email)
        if row is None:
            new.append(a)
        elif row["seeded"] and (not check_password(pw, row["password_hash"]) or (row["name"], row["role"],
                row["student_id"], row["department"]) != (a.name, a.role, a.student_id, a.department)):
            changed.append(a)
    if new or changed:
        db.save_seeded(new, changed)
        log.info("portal_accounts: %d demo account(s) added, %d refreshed", len(new), len(changed))


def _seed() -> _Registry:
    reg = _Registry()
    if db.enabled():                 # the table is the store: nothing is kept in the registry
        sync_seeded_accounts()
        return reg
    for a in _seeded_accounts(hash_password(_demo_password())):
        reg.accounts[a.email] = a
    _load_registered(reg)
    return reg


# ------------------------------------------------------------------ persistence (Blob Storage)
def _load_registered(reg: _Registry) -> None:
    """No database: merge registrations saved in Blob Storage into the registry and the store. On a read error the
    registry is marked not loaded; registration stays refused until a later read succeeds."""
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
        st = Student(s["student_id"], s["name"], s["intended_major"], s["bu_start_term"], email=s.get("email", ""))
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


def _import_blob_accounts() -> None:
    """One-off move of accounts registered before PostgreSQL was used (accounts/accounts.json) into the table."""
    if not blob_store.enabled():
        return
    try:
        doc = blob_store.load_json("accounts", ACCOUNTS_BLOB)
    except (blob_store.BlobStoreError, ValueError) as e:
        log.error("accounts saved in Blob Storage could not be read; not copied to PostgreSQL: %s", e)
        return
    if not doc:
        return
    students = {s["student_id"]: Student(s["student_id"], s["name"], s["intended_major"], s["bu_start_term"])
                for s in doc.get("students", [])}
    for a in doc.get("accounts", []):
        acct = Account(a["email"], a["name"], a["role"], a["password_hash"], student_id=a.get("student_id"),
                       department=a.get("department"), registered=True)
        st = students.get(acct.student_id or "")
        try:
            db.save_registration(acct, st if st and st.student_id not in store_mod.STORE.students else None)
        except db.DuplicateAccount:
            continue
        if st:
            with store_mod.STORE.lock:
                store_mod.STORE.students.setdefault(st.student_id, st)
    log.info("copied %d account(s) from Blob Storage to PostgreSQL", len(doc.get("accounts", [])))


def _save_registered(reg: _Registry) -> None:
    """No database: save the registered accounts to Blob Storage (the whole document). Caller holds reg.lock.
    Raises AccountError when it cannot be stored."""
    if not blob_store.enabled():
        return
    doc = dict(
        version=1,
        accounts=[dict(email=a.email, name=a.name, role=a.role, password_hash=a.password_hash,
                       student_id=a.student_id, department=a.department)
                  for a in reg.accounts.values() if a.registered],
        students=[dict(student_id=s.student_id, name=s.name, intended_major=s.intended_major,
                       bu_start_term=s.bu_start_term, email=s.email) for s in reg.students],
    )
    try:
        blob_store.save_json("accounts", ACCOUNTS_BLOB, doc)
    except blob_store.BlobStoreError:
        raise AccountError(502, "Could not save your account. Please try again.")


def _ensure_loaded(reg: _Registry) -> None:
    """Caller holds reg.lock. Before accepting a registration, stored accounts must be known (duplicate check and
    no overwrite with a partial list): retry a failed start-up read, refuse while storage stays unreadable."""
    if not db.enabled() and blob_store.enabled() and not reg.loaded:
        _load_registered(reg)
        if not reg.loaded:
            raise AccountError(503, "Registration is temporarily unavailable. Please try again in a few minutes.")


REGISTRY = _seed()


def reset_accounts() -> None:
    """Tests: back to the seeded accounts only (memory), or the seeded rows refreshed (table)."""
    global REGISTRY
    REGISTRY = _seed()


def restore_registered_students() -> None:
    """After a demo reset of the store, put registered students' records back so their accounts still work.
    With a database the reset reloads them from the students table, so there is nothing to restore."""
    with store_mod.STORE.lock:
        for st in REGISTRY.students:
            store_mod.STORE.students.setdefault(st.student_id, st)


def registered_student_email(student_id: str) -> Optional[str]:
    """The address a student registered with, or None. Seeded sample students (made-up addresses) never have one,
    so they are never emailed (app/notify.py)."""
    if db.enabled():
        try:
            return db.registered_student_email(student_id)
        except db.DBError:
            log.error("registered email of %s could not be read; no email address used", student_id)
            return None
    with REGISTRY.lock:
        return next((a.email for a in REGISTRY.accounts.values()
                     if a.registered and a.role == "Student" and a.student_id == student_id), None)


def _from_row(row: dict) -> Account:
    return Account(row["email"], row["name"], row["role"], row["password_hash"], student_id=row["student_id"],
                   department=row["department"], registered=not row["seeded"])


def _lookup(email: str) -> Optional[Account]:
    """The account for a normalised email. With a database this reads the table on every call."""
    if not db.enabled():
        return REGISTRY.accounts.get(email)
    try:
        row = db.get_account(email)
    except db.DBError:
        raise AccountError(503, "Sign-in is temporarily unavailable. Please try again in a moment.")
    return _from_row(row) if row else None


def _store_new_account(acct: Account, student: Optional[Student]) -> None:
    """Persist a registration, or raise AccountError with nothing registered. Caller holds REGISTRY.lock and has
    already created `student` in the store (it is removed again when the account cannot be stored)."""
    try:
        if db.enabled():
            try:
                db.save_registration(acct, student)           # the account and its student record, one transaction
            except db.DuplicateAccount:
                raise AccountError(409, "An account with this email already exists. Sign in instead.")
            except db.DBError:
                raise AccountError(503, "Could not save your account. Please try again.")
            return
        REGISTRY.accounts[acct.email] = acct
        if student is not None:
            REGISTRY.students.append(student)
        _save_registered(REGISTRY)
    except AccountError:                                       # not stored -> not registered
        REGISTRY.accounts.pop(acct.email, None)
        if student is not None:
            if student in REGISTRY.students:
                REGISTRY.students.remove(student)
            with store_mod.STORE.lock:
                store_mod.STORE.students.pop(student.student_id, None)
        raise


def departments() -> list[str]:
    return list(ACADEMIC_DEPARTMENTS)


# ------------------------------------------------------------------ sign-in and registration
def _norm_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AccountError(422, "Enter a valid email address (name@example.com)")
    return email


def _check_new_password(password: str) -> None:
    if len(password or "") < PASSWORD_MIN:
        raise AccountError(422, f"Password must be at least {PASSWORD_MIN} characters")


def authenticate(email: str, password: str, portal: str) -> Account:
    email = _norm_email(email)
    acct = _lookup(email)
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
        if _lookup(email) is not None:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        with store_mod.STORE.lock:
            taken = [int(s[4:]) for s in store_mod.STORE.students if re.fullmatch(r"SYN-\d+", s)]
            taken += [int(s.student_id[4:]) for s in REGISTRY.students]   # ids survive a store reset (no database)
            sid = f"SYN-{max(taken, default=24000) + 1}"
            st = Student(sid, name, intended_major.strip()[:60], (start_term or "Fall 2026").strip()[:20], email=email)
            store_mod.STORE.students[sid] = st
        acct = Account(email, name, "Student", hash_password(password), student_id=sid, registered=True)
        _store_new_account(acct, st)
    return acct


def register_staff(name: str, email: str, password: str, role: str, invite_code: str) -> Account:
    """A staff account (Advisor, FinancialAid, Evaluator, CreditStaff or Registrar), only with the staff invite code.
    The code is checked before anything else about the account is, so it cannot be used to probe which emails exist."""
    code = staff_invite_code()
    if not code:
        raise AccountError(403, "Staff registration is switched off. Ask your administrator for an account.")
    if not hmac.compare_digest((invite_code or "").strip().encode(), code.encode()):
        raise AccountError(403, "That staff code is not correct. Ask your administrator for it.")
    email, name = _norm_email(email), (name or "").strip()
    if not 2 <= len(name) <= 80:
        raise AccountError(422, "Enter your full name")
    if role not in STAFF_ROLES:
        raise AccountError(422, "Choose a staff role from the list")
    _check_new_password(password)
    with REGISTRY.lock:
        _ensure_loaded(REGISTRY)
        if _lookup(email) is not None:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        acct = Account(email, name, role, hash_password(password), registered=True)
        _store_new_account(acct, None)
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
        if _lookup(email) is not None:
            raise AccountError(409, "An account with this email already exists. Sign in instead.")
        acct = Account(email, name, "Department", hash_password(password), department=department, registered=True)
        _store_new_account(acct, None)
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
    acct = _lookup(claims["sub"])
    if acct is None:                                     # removed, or accounts reset after a restart
        raise AccountError(401, "Your session has expired. Sign in again.")
    if db.enabled():                                     # the table decides: a changed role or name applies at once
        return dict(email=acct.email, name=acct.name, role=acct.role, student_id=acct.student_id,
                    department=acct.department)
    return dict(email=claims["sub"], name=claims.get("name"), role=claims["role"], student_id=claims.get("sid"),
                department=claims.get("dept"))
