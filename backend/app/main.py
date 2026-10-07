import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import models  # noqa: F401  (register tables)
from .config import settings
from .database import Base, engine
from .migrations import ensure_columns
from .routers import alerts, auth, contacts, journeys, public, status
from .scheduler import run_forever

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    Base.metadata.create_all(engine)          # use Alembic migrations for real deployments
    ensure_columns(engine)                    # adds newer columns to an existing database
    task = asyncio.create_task(run_forever()) if settings.scheduler_enabled else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="SafeSphere API", version="1.2.0", lifespan=lifespan)
for r in (auth.router, contacts.router, journeys.router, alerts.router, public.router, status.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
