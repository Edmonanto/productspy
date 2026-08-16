"""ProductSpy Pro API.

Mounted at /api/v1 to match NEXT_PUBLIC_API_URL in the frontend.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db
from .routers import billing, products, users, watchlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
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

for r in (users.router, products.router, watchlist.router, billing.router):
    app.include_router(r, prefix=config.API_PREFIX)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, object]:
    return {"ok": True, "database": await db.healthy()}
