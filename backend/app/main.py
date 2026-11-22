import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models  # noqa: F401 - registers models on Base.metadata
from .config import get_settings
from .db import Base, check_db_health, engine
from .routers import (
    admin,
    ai_routes,
    auth,
    doctor,
    emergency,
    hospital,
    hospital_registry,
    notifications,
    patient,
    post_emergency,
    referrals,
    scenarios,
)
from .ws import router as ws_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio

    from .services.runner import bind_loop

    # In development/test environments, auto-create tables if running without migrations
    if settings.app_env in ("development", "test"):
        Base.metadata.create_all(bind=engine)
    else:
        logging.getLogger("uvicorn.info").info("Production mode: schema managed via Alembic migrations.")

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
@app.get("/api/health", tags=["System"])
def health():
    db_ok = check_db_health()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "lifeline-ai-backend",
        "version": app.version,
        "database": "connected" if db_ok else "unreachable",
    }


for r in (
    auth.router,
    patient.router,
    emergency.router,
    doctor.router,
    hospital.router,
    hospital_registry.router,
    admin.router,
    ai_routes.router,
    notifications.router,
    referrals.router,
    scenarios.router,
    post_emergency.router,
    post_emergency.follow_up_router,
):
    app.include_router(r, prefix="/api")
app.include_router(ws_router)  # /ws (unprefixed - kept at root for simple reverse-proxy rules)
