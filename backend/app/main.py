"""ProductSpy Pro API.

Mounted at /api/v1 to match NEXT_PUBLIC_API_URL in the frontend.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db, migrate
from .routers import billing, matches, products, quotes, status, users, watchlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    # Bring the schema up to date before serving. Migrations used to run only
    # in the ingest cron, so a deploy went live against a schema it didn't
    # match until the next 02:00 run — every query naming a new column failed.
    # Idempotent and ledger-tracked, so this is a no-op when current. A failure
    # aborts startup; Render then keeps the previous version live.
    if config.MIGRATE_ON_START and db.is_connected():
        await migrate.apply_all()
    yield
    await db.disconnect()


app = FastAPI(
    title="ProductSpy Pro API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (users.router, products.router, watchlist.router,
          matches.router, billing.router, status.router, quotes.router):
    app.include_router(r, prefix=config.API_PREFIX)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, object]:
    return {"ok": True, "database": await db.healthy()}
