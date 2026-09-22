"""Demo travel simulator: moves the patient towards the hospital, one simulated minute per tick."""
import asyncio

from ..config import get_settings
from ..db import SessionLocal
from ..events import hub
from ..models import EmergencyCase
from . import ops


def _tick(case_id: int):
    with SessionLocal() as db:
        c = db.get(EmergencyCase, case_id)
        if not c or c.status in ("PATIENT_ARRIVED", "COMPLETED"):
            return "stop", None, None
        if not c.hospital_id or not c.initial_eta_minutes:
            return "wait", None, None
        remaining = max(0, (c.eta_minutes or 0) - 1)
        frac = 1 - remaining / c.initial_eta_minutes
        h = c.hospital
        c.current_lat, c.current_lng = c.lat + (h.lat - c.lat) * frac, c.lng + (h.lng - c.lng) * frac
        c.eta_minutes = remaining
        event = "EtaUpdated"
        if remaining == 0:
            if ops.status_idx(c.status) < ops.status_idx("SUMMARY_GENERATED"):
                db.commit()
                return "wait", ops.event_info(c), "EtaUpdated"  # hold at the door until the pipeline caught up
            ops.touch_arrival(c)
            ops.log_event(db, c.id, "PATIENT_ARRIVED", f"Patient arrived at {h.name}", "system")
            ops.notify_case_users(db, c, f"Arrived at {h.name}.", f"Patient {c.patient.user.full_name} has arrived.", "Patient arrived")
            event = "PatientArrived"
        db.commit()
        return ("stop" if event == "PatientArrived" else "go"), ops.event_info(c), event


async def simulate_travel(case_id: int) -> None:
    tick = get_settings().demo_tick_seconds
    while True:
        await asyncio.sleep(tick)
        state, info, event = await asyncio.to_thread(_tick, case_id)
        if info:
            await hub.emit(event, info)
        if state == "stop":
            return
