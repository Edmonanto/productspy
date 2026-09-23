"""Migration runner.

These run without Postgres, so they cover ordering, the ledger's skip/re-apply
decision, and the shape of what gets executed — not the SQL itself, which
tests/test_sql_integrity.py already parses against the real grammar.
"""
import pytest

from app import db, migrate


def test_migrations_are_ordered_by_filename():
    """The 001_/002_ prefixes define dependency order: 002 adds columns to
    tables 001 creates, so a wrong order fails on a real database."""
    names = [p.name for p in migrate.migration_files()]
    assert names == sorted(names)
    assert names[0].startswith("001_")
    assert len(names) >= 4


def test_every_migration_is_discovered():
    names = {p.name for p in migrate.migration_files()}
    for expected in ("001_init.sql", "002_ingestion.sql",
                     "003_billing.sql", "004_matching.sql"):
        assert expected in names


def test_checksum_is_stable_and_content_sensitive():
    assert migrate.checksum("create table x()") == migrate.checksum("create table x()")
    assert migrate.checksum("a") != migrate.checksum("b")


class FakeConn:
    def __init__(self, log):
        self.log = log

    def transaction(self):
        conn = self

        class Tx:
            async def __aenter__(self_inner):
                conn.log.append(("BEGIN",))
                return self_inner

            async def __aexit__(self_inner, *a):
                conn.log.append(("COMMIT",))
                return False

        return Tx()

    async def execute(self, sql, *args):
        self.log.append(("exec", sql, args))


class FakePool:
    def __init__(self, log):
        self.log = log

    def acquire(self):
        conn = FakeConn(self.log)

        class Ctx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *a):
                return False

        return Ctx()


@pytest.fixture
def fake_db(monkeypatch):
    log: list = []
    state = {"applied": []}

    async def execute(sql, *args):
        log.append(("execute", sql))

    async def fetch(sql, *args):
        return state["applied"]

    monkeypatch.setattr(db, "execute", execute)
    monkeypatch.setattr(db, "fetch", fetch)
    monkeypatch.setattr(db, "pool", lambda: FakePool(log))
    return log, state


@pytest.mark.asyncio
async def test_applies_everything_on_a_fresh_database(fake_db):
    log, state = fake_db
    stats = await migrate.apply_all()

    assert stats["applied"] == len(migrate.migration_files())
    assert stats["skipped"] == 0
    # Each migration is wrapped in its own transaction.
    assert log.count(("BEGIN",)) == stats["applied"]
    assert log.count(("COMMIT",)) == stats["applied"]


@pytest.mark.asyncio
async def test_skips_migrations_already_applied(fake_db):
    log, state = fake_db
    state["applied"] = [
        {"filename": p.name, "checksum": migrate.checksum(p.read_text())}
        for p in migrate.migration_files()
    ]

    stats = await migrate.apply_all()
    assert stats["applied"] == 0
    assert stats["skipped"] == len(migrate.migration_files())
    assert ("BEGIN",) not in log          # nothing executed


@pytest.mark.asyncio
async def test_reapplies_a_migration_whose_content_changed(fake_db):
    """Idempotent SQL makes this safe, but it must be visible rather than
    silently skipped — a checksum drift means the DB and the checkout differ."""
    log, state = fake_db
    files = migrate.migration_files()
    state["applied"] = [
        {"filename": p.name, "checksum": migrate.checksum(p.read_text())}
        for p in files
    ]
    state["applied"][0]["checksum"] = "deadbeefdeadbeef"   # pretend it changed

    stats = await migrate.apply_all()
    assert stats["changed"] == 1
    assert stats["applied"] == 1
    assert stats["skipped"] == len(files) - 1


@pytest.mark.asyncio
async def test_ledger_table_is_created_before_anything_is_read(fake_db):
    log, _ = fake_db
    await migrate.apply_all()
    assert any("schema_migrations" in entry[1] for entry in log if entry[0] == "execute")
