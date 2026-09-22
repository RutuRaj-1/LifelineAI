import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - registers models on Base.metadata
from .config import get_settings
from .db import Base, engine
from .routers import ai_routes, auth, doctor, emergency, hospital, notifications, patient, scenarios
from .ws import router as ws_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio

    from .services.runner import bind_loop

    Base.metadata.create_all(bind=engine)  # for a first run without Alembic; see database/schema.sql for migrations
    bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(
    title="LifeLine AI API",
    description="Patient-Triggered Emergency Pre-Arrival Intelligence. AI never diagnoses; it only summarises "
                "uploaded records with citations. Doctors make all clinical decisions.",
    version="0.6.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "lifeline-ai-backend", "version": app.version}


for r in (auth.router, patient.router, emergency.router, doctor.router, hospital.router, ai_routes.router,
         notifications.router, scenarios.router):
    app.include_router(r, prefix="/api")
app.include_router(ws_router)  # /ws (unprefixed - kept at root for simple reverse-proxy rules)
