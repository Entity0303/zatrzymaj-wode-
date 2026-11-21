"""Aplikacja FastAPI: tylko utworzenie app, middleware i rejestracja routerów.

Endpointy: app/routers/, kontrakty: app/schemas/, źródła danych: app/sources/, obliczenia: app/analysis/.
"""

import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.http import close_client
from app.demo import warmup_loop
from app.routers import analysis, demo, infra_reports, layers, parcel, reports, status, weather


@asynccontextmanager
async def lifespan(_: FastAPI):
    # rozgrzewka cache przykładów demo w tle – nie blokuje startu (DEMO_WARMUP=false wyłącza)
    task = asyncio.create_task(warmup_loop()) if settings.demo_warmup else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await close_client()


app = FastAPI(
    title="Zatrzymaj wodę – API",
    description="Ocena sytuacji wodnej działki rolnej na podstawie danych publicznych.",
    version="0.2.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

for r in (parcel.router, weather.router, analysis.router, layers.router, reports.router, reports.pdf_router,
          infra_reports.router, demo.router, status.router):
    app.include_router(r)


@app.get("/api/health", tags=["infrastruktura"])
async def health() -> dict:
    return {"status": "ok"}
