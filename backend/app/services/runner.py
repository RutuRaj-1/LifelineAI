import asyncio
import logging

from ai.embeddings import get_embedder
from ai.graph import build_pipeline
from ai.rag import RagPipeline

from ..cache import cache_get, cache_set
from ..config import get_settings
from ..db import SessionLocal
from ..models import EmergencyCase
from .pipeline_services import DbServices, _in_db
from . import ops
from .travel import simulate_travel

log = logging.getLogger("lifeline.pipeline")
_tasks: set[asyncio.Task] = set()
_pipeline = None
_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once from FastAPI's startup event, where a running loop is guaranteed to exist."""
    global _loop
    _loop = loop


def spawn(coro) -> None:
    """Schedule a coroutine onto the app's event loop. Safe to call both from async request handlers
    (already on that loop) and from FastAPI's sync (threadpool) request handlers (no running loop)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is _loop and loop is not None:
        t = loop.create_task(coro)
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)
    elif _loop is not None:
        asyncio.run_coroutine_threadsafe(coro, _loop)
    else:  # pragma: no cover - only if called before startup
        asyncio.get_event_loop().run_until_complete(coro)


def get_rag() -> RagPipeline:
    s = get_settings()
    return RagPipeline(get_embedder(s.openai_api_key, s.openai_embedding_model, cache_get, cache_set))


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        s = get_settings()
        _pipeline = build_pipeline(DbServices(), get_rag(), s.openai_api_key, s.openai_model)
    return _pipeline


async def run_pipeline(case_id: int) -> None:
    def load(db):
        c = db.get(EmergencyCase, case_id)
        return {"case_id": c.id, "patient_id": c.patient_id, "emergency_type": c.emergency_type,
                "symptoms": c.symptoms, "lat": c.lat, "lng": c.lng}
    try:
        state = await _in_db(load)
        result = await get_pipeline().run(state)
        if result.get("priority"):
            await _in_db(lambda db: setattr(db.get(EmergencyCase, case_id), "priority", result["priority"]))
    except Exception as exc:  # noqa: BLE001
        log.exception("pipeline failed for case %s", case_id)
        await _in_db(lambda db: ops.log_event(db, case_id, "PIPELINE_ERROR", f"{type(exc).__name__}: {exc}"))


def start_case(case_id: int) -> None:
    spawn(run_pipeline(case_id))
    if get_settings().simulate_travel:
        spawn(simulate_travel(case_id))
