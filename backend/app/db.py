"""Postgres connection pool (asyncpg) and query helpers."""
from typing import Any

import asyncpg

from . import config

_pool: asyncpg.Pool | None = None


async def connect() -> None:
    """Open the shared pool. Called once on app startup."""
    global _pool
    if _pool is not None:
        return
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set")
    _pool = await asyncpg.create_pool(
        config.DATABASE_URL,
        min_size=1,
        max_size=10,
        # Supabase's pooler does not support prepared statement caching.
        statement_cache_size=0,
    )


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    return _pool


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    async with pool().acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    async with pool().acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    async with pool().acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    async with pool().acquire() as conn:
        return await conn.execute(query, *args)


async def healthy() -> bool:
    try:
        return await fetchval("select 1") == 1
    except Exception:
        return False
