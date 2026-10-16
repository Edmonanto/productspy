"""The API applies pending migrations before it serves requests."""
from fastapi.testclient import TestClient

from app import config, db, migrate
from app.main import app


async def _noop():
    return None


def _run(monkeypatch, connected: bool, enabled: bool = True) -> list[str]:
    calls: list[str] = []

    async def apply_all():
        calls.append("migrated")
        return {"applied": 0, "skipped": 0, "changed": 0}

    monkeypatch.setattr(db, "connect", lambda: _noop())
    monkeypatch.setattr(db, "disconnect", lambda: _noop())
    monkeypatch.setattr(db, "is_connected", lambda: connected)
    monkeypatch.setattr(migrate, "apply_all", apply_all)
    monkeypatch.setattr(config, "MIGRATE_ON_START", enabled)
    with TestClient(app):
        pass
    return calls


def test_migrates_on_start(monkeypatch):
    assert _run(monkeypatch, connected=True) == ["migrated"]


def test_skips_without_a_database(monkeypatch):
    assert _run(monkeypatch, connected=False) == []


def test_can_be_disabled(monkeypatch):
    assert _run(monkeypatch, connected=True, enabled=False) == []
