"""Apply pending SQL migrations.

Every migration in this project is written to be idempotent (`create table if
not exists`, `add column if not exists`), so re-running is harmless. The
ledger exists for a different reason: so a deploy can tell you *which*
migrations it applied, rather than silently re-executing everything and
leaving you to guess whether the schema is current.

    python -m app.migrate

Safe to run on every deploy and safe to run twice.
"""
import asyncio
import hashlib
import logging
import pathlib
import sys

from . import db

log = logging.getLogger("migrate")

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent / "migrations"

LEDGER = """
create table if not exists schema_migrations (
    filename    text primary key,
    checksum    text not null,
    applied_at  timestamptz not null default now()
)
"""


def migration_files() -> list[pathlib.Path]:
    """Sorted by filename, so the 001_/002_ prefixes define the order."""
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


async def apply_all() -> dict[str, int]:
    stats = {"applied": 0, "skipped": 0, "changed": 0}

    await db.execute(LEDGER)
    applied = {
        r["filename"]: r["checksum"]
        for r in await db.fetch("select filename, checksum from schema_migrations")
    }

    for path in migration_files():
        sql = path.read_text()
        digest = checksum(sql)

        if path.name in applied:
            if applied[path.name] != digest:
                # The file changed after being applied. Re-running is safe
                # because migrations are idempotent, but silence would hide a
                # real divergence between this checkout and the database.
                log.warning(
                    "%s changed since it was applied (%s -> %s); re-applying",
                    path.name, applied[path.name], digest,
                )
                stats["changed"] += 1
            else:
                stats["skipped"] += 1
                continue

        log.info("applying %s", path.name)
        async with db.pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "insert into schema_migrations (filename, checksum) "
                    "values ($1, $2) on conflict (filename) do update set "
                    "checksum = excluded.checksum, applied_at = now()",
                    path.name,
                    digest,
                )
        stats["applied"] += 1

    return stats


async def run() -> dict[str, int]:
    await db.connect()
    try:
        stats = await apply_all()
        log.info(
            "migrations: %d applied, %d already current, %d re-applied after change",
            stats["applied"], stats["skipped"], stats["changed"],
        )
        return stats
    finally:
        await db.disconnect()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    try:
        asyncio.run(run())
    except Exception:
        # A failed migration must stop the deploy, not let the app start
        # against a schema it does not match.
        log.exception("migration failed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
