import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from . import alerts as alerts_mod
from . import models  # noqa: F401  (register tables)
from .config import settings
from .database import Base, engine
from .migrations import ensure_columns
from .routers import alerts, auth, contacts, journeys, public, telegram
from .scheduler import run_forever

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("safesphere")


def _setup_telegram() -> None:
    tg = alerts_mod.telegram
    if not tg:
        return
    if not tg.username:
        tg.load_username()
    if settings.public_base_url.startswith("https://"):
        ok = tg.set_webhook(f"{settings.public_base_url}/telegram/webhook", settings.telegram_webhook_secret)
        log.info("Telegram webhook registered: %s (bot @%s)", ok, tg.username)
    else:
        log.warning("Telegram needs a public https PUBLIC_BASE_URL for its webhook; skipping registration")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate()
    Base.metadata.create_all(engine)          # use Alembic migrations for real deployments
    ensure_columns(engine)
    tg_task = asyncio.create_task(asyncio.to_thread(_setup_telegram))   # never block startup on Telegram
    task = asyncio.create_task(run_forever()) if settings.scheduler_enabled else None
    yield
    tg_task.cancel()
    if task:
        task.cancel()


app = FastAPI(title="SafeSphere API", version="1.1.0", lifespan=lifespan)
for r in (auth.router, contacts.router, journeys.router, alerts.router, public.router, telegram.router):
    app.include_router(r)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
