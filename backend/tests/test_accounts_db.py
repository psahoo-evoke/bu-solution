"""With PostgreSQL configured, portal_accounts is the only account store: nothing is kept in memory and every sign-in,
registration and session check goes to the table (app/accounts.py, app/db.py). The table is faked here (ADR 0003: tests
need no database); the fake enforces the same primary key and role rule as the real one."""
import pytest

from app import accounts, db
from app.guard import ALL_ROLES


class FakeTable:
    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.down = False
        self.reads = 0

    def _check(self):
        if self.down:
            raise db.DBError("down")

    def load_accounts(self):
        self._check()
        return [dict(r) for r in self.rows.values()]

    def get_account(self, email):
        self._check()
        self.reads += 1
        r = self.rows.get(email)
        return dict(r) if r else None

    def registered_student_email(self, student_id):
        self._check()
        return next((r["email"] for r in self.rows.values()
                     if r["student_id"] == student_id and r["role"] == "Student" and not r["seeded"]), None)

    def _insert(self, a, seeded):
        assert a.role in db.ACCOUNT_ROLES, "role rule"
        self.rows[a.email] = dict(email=a.email, name=a.name, role=a.role, password_hash=a.password_hash,
                                  student_id=a.student_id, department=a.department, seeded=seeded)

    def save_registration(self, acct, student=None):
        self._check()
        if acct.email in self.rows:
            raise db.DuplicateAccount("dup")
        self._insert(acct, False)

    def save_seeded(self, new, changed):
        self._check()
        for a in new:
            self._insert(a, True)
        for a in changed:
            assert self.rows[a.email]["seeded"]
            self._insert(a, True)


@pytest.fixture
def table(monkeypatch):
    t = FakeTable()
    monkeypatch.setattr(db, "enabled", lambda: True)
    for name in ("load_accounts", "get_account", "registered_student_email", "save_registration", "save_seeded"):
        monkeypatch.setattr(db, name, getattr(t, name))
    accounts.reset_accounts()
    yield t
    monkeypatch.undo()
    accounts.reset_accounts()


def test_every_account_role_is_allowed_by_the_table_rule():
    assert set(db.ACCOUNT_ROLES) == set(ALL_ROLES)
    for role in ALL_ROLES:
        assert f"'{role}'" in db.EXTRA_TABLES
    assert "'Student','Department')" not in db.EXTRA_TABLES.replace(" ", "")


def test_demo_accounts_are_rows_in_the_table_not_memory(table):
    assert accounts.REGISTRY.accounts == {}
    rows = table.rows
    assert set(accounts.SAMPLE_STUDENTS.values()) <= set(rows)
    assert set(accounts.STAFF_ACCOUNTS.values()) <= set(rows)
    assert {accounts.dept_email(d) for d in accounts.ACADEMIC_DEPARTMENTS} <= set(rows)
    assert all(r["seeded"] for r in rows.values())
    assert {rows[e]["role"] for e in accounts.STAFF_ACCOUNTS.values()} == set(accounts.STAFF_ROLES)


def test_sign_in_reads_the_table_every_time(table):
    assert accounts.authenticate("financialaid@bu.edu", "admin", "staff").role == "FinancialAid"
    # change the password in the table only: the very next sign-in sees it (nothing cached in memory)
    table.rows["financialaid@bu.edu"]["password_hash"] = accounts.hash_password("fresh-pass")
    with pytest.raises(accounts.AccountError) as e:
        accounts.authenticate("financialaid@bu.edu", "admin", "staff")
    assert e.value.status == 401
    assert accounts.authenticate("financialaid@bu.edu", "fresh-pass", "staff").email == "financialaid@bu.edu"


def test_registration_goes_to_the_table_only(table):
    acct = accounts.register_student("Pat Lee", "pat@example.com", "secret1", "Biology", "Fall 2026")
    row = table.rows["pat@example.com"]
    assert (row["role"], row["seeded"], row["student_id"]) == ("Student", False, acct.student_id)
    assert accounts.REGISTRY.accounts == {} and accounts.REGISTRY.students == []
    assert accounts.registered_student_email(acct.student_id) == "pat@example.com"
    assert accounts.authenticate("PAT@example.com", "secret1", "student").student_id == acct.student_id
    dept = accounts.register_department("Dee Kay", "dee@example.com", "secret1", "Biology")
    assert table.rows["dee@example.com"]["department"] == "Biology" and dept.role == "Department"


def test_duplicate_email_is_refused_and_leaves_no_student_record(table, fresh_store):
    before = set(fresh_store.students)
    with pytest.raises(accounts.AccountError) as e:
        accounts.register_student("Maya Again", "maya.delgado@bu.edu", "secret1", "Biology", "Fall 2026")
    assert e.value.status == 409 and set(fresh_store.students) == before
    accounts.register_department("Dee Kay", "dee@example.com", "secret1", "Biology")
    with pytest.raises(accounts.AccountError) as e:
        accounts.register_department("Dee Two", "dee@example.com", "secret1", "Biology")
    assert e.value.status == 409


def test_a_failed_write_registers_nothing(table, fresh_store):
    before = set(fresh_store.students)

    def boom(acct, student=None):
        raise db.DBError("write failed")
    db.save_registration = boom
    with pytest.raises(accounts.AccountError) as e:
        accounts.register_student("Pat Lee", "pat@example.com", "secret1", "Biology", "Fall 2026")
    assert e.value.status == 503 and set(fresh_store.students) == before and "pat@example.com" not in table.rows


def test_a_database_outage_is_a_503_not_a_wrong_password(table):
    table.down = True
    with pytest.raises(accounts.AccountError) as e:
        accounts.authenticate("advisor@bu.edu", "admin", "staff")
    assert e.value.status == 503
    assert accounts.registered_student_email("SYN-24001") is None       # best effort: never raises


def test_session_follows_the_table(table):
    acct = accounts.authenticate("advisor@bu.edu", "admin", "staff")
    token = f"Bearer {accounts.issue_token(acct)}"
    assert accounts.session_user(token)["role"] == "Advisor"
    table.rows["advisor@bu.edu"]["name"] = "Renamed Advisor"
    assert accounts.session_user(token)["name"] == "Renamed Advisor"       # name and role come from the row
    del table.rows["advisor@bu.edu"]
    with pytest.raises(accounts.AccountError) as e:
        accounts.session_user(token)
    assert e.value.status == 401


def test_demo_password_change_refreshes_only_demo_rows(table, monkeypatch):
    mine = accounts.register_department("Dee Kay", "dee@example.com", "secret1", "Biology")
    monkeypatch.setenv("TRANSFERIQ_DEMO_PASSWORD", "new-demo")
    accounts.sync_seeded_accounts()
    assert accounts.authenticate("registrar@bu.edu", "new-demo", "staff").role == "Registrar"
    assert accounts.authenticate("dee@example.com", "secret1", "department").email == mine.email


def test_a_registered_account_on_a_demo_email_is_never_overwritten(table):
    del table.rows["advisor@bu.edu"]
    accounts_row = accounts.Account("advisor@bu.edu", "Someone Else", "Advisor", accounts.hash_password("mine-pass"))
    table._insert(accounts_row, False)
    accounts.sync_seeded_accounts()
    assert table.rows["advisor@bu.edu"]["name"] == "Someone Else" and not table.rows["advisor@bu.edu"]["seeded"]


class _Cur:
    """Cursor stub for db._migrate_portal_accounts: records statements, answers the constraint query."""

    def __init__(self, definition):
        self.definition, self.sql = definition, []

    def execute(self, sql, params=None):
        self.sql.append(" ".join(sql.split()))

    def fetchone(self):
        return None if self.definition is None else (self.definition,)


def test_migration_widens_an_old_role_rule():
    old = "CHECK ((role = ANY (ARRAY['Student'::text, 'Department'::text])))"
    cur = _Cur(old)
    db._migrate_portal_accounts(cur)
    joined = " | ".join(cur.sql)
    assert "add column if not exists seeded" in joined
    assert "drop constraint if exists portal_accounts_role_check" in joined
    assert all(f"'{r}'" in joined for r in ALL_ROLES)


def test_migration_leaves_a_current_rule_alone():
    cur = _Cur("CHECK (role = ANY (ARRAY[" + ", ".join(f"'{r}'::text" for r in db.ACCOUNT_ROLES) + "]))")
    db._migrate_portal_accounts(cur)
    assert not any("drop constraint" in s or "add constraint" in s for s in cur.sql)
    cur = _Cur(None)                                   # no rule at all: add it
    db._migrate_portal_accounts(cur)
    assert any("add constraint portal_accounts_role_check" in s for s in cur.sql)
