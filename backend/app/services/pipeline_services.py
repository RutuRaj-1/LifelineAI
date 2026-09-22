"""Backend implementation of ai.agents.Services: DB access in worker threads + WebSocket broadcasts."""
import asyncio
from typing import Callable

from ..config import get_settings
from ..db import SessionLocal
from ..events import hub
from ..models import Doctor, EmergencyCase, Hospital, HospitalResource, MedicalReport, Patient
from . import ops
from .maps import eta_minutes, haversine_km

settings = get_settings()


def _in_db(fn: Callable):
    def run():
        with SessionLocal() as db:
            out = fn(db)
            db.commit()
            return out
    return asyncio.to_thread(run)


class DbServices:
    async def _emit(self, event: str, case_id: int, **data):
        info = await _in_db(lambda db: ops.event_info(db.get(EmergencyCase, case_id)))
        await hub.emit(event, info, **data)

    async def log(self, case_id, event, detail):
        await _in_db(lambda db: ops.log_event(db, case_id, event, detail, "agent"))

    async def set_status(self, case_id, status, detail, event):
        def work(db):
            c = db.get(EmergencyCase, case_id)
            if ops.status_idx(status) > ops.status_idx(c.status):
                c.status = status
            ops.log_event(db, case_id, status, detail, "agent")
        await _in_db(work)
        await self._emit(event, case_id, detail=detail)
        await asyncio.sleep(settings.pipeline_step_delay)

    async def route_hospital(self, case_id):
        def load(db):
            c = db.get(EmergencyCase, case_id)
            rows = []
            for h in db.query(Hospital).all():
                er = db.query(HospitalResource).filter_by(hospital_id=h.id, resource_type="ER_BED").first()
                rows.append({"id": h.id, "name": h.name, "lat": h.lat, "lng": h.lng,
                             "capable": c.emergency_type in (h.capabilities or []) or c.emergency_type == "other",
                             "er": er.available if er else 0, "km": haversine_km(c.lat, c.lng, h.lat, h.lng)})
            return c.lat, c.lng, rows
        lat, lng, rows = await _in_db(load)
        ranked = sorted(rows, key=lambda r: (not (r["capable"] and r["er"] > 0), r["km"]))[:3]
        etas = await asyncio.gather(*[eta_minutes(lat, lng, r["lat"], r["lng"]) for r in ranked])
        ok = [(e, r) for e, r in zip(etas, ranked) if r["capable"] and r["er"] > 0] or list(zip(etas, ranked))
        eta, best = min(ok, key=lambda t: t[0])

        def save(db):
            c = db.get(EmergencyCase, case_id)
            c.hospital_id, c.eta_minutes, c.initial_eta_minutes = best["id"], eta, eta
            c.current_lat, c.current_lng = c.lat, c.lng
            ops.log_event(db, case_id, "HOSPITAL_ROUTED",
                          f"{best['name']} selected ({best['km']:.1f} km, ETA {eta} min, capable={best['capable']})", "agent")
        await _in_db(save)
        await self._emit("HospitalAlerted", case_id, hospital=best["name"], eta=eta)
        return {"id": best["id"], "name": best["name"], "eta": eta}

    async def load_reports(self, patient_id):
        def work(db):
            p = db.get(Patient, patient_id)
            if not p.consent_ai_summary:
                return []
            rs = db.query(MedicalReport).filter(MedicalReport.patient_id == patient_id,
                                                MedicalReport.extracted_text.isnot(None)).order_by(MedicalReport.report_date.desc()).all()
            return [{"id": r.id, "title": r.title, "date": r.report_date, "text": r.extracted_text} for r in rs if r.extracted_text.strip()]
        return await _in_db(work)

    async def save_summary(self, case_id, brief):
        def work(db):
            db.get(EmergencyCase, case_id).ai_summary = brief
        await _in_db(work)

    async def assign_doctor(self, case_id, specialty, checklist):
        def work(db):
            c = db.get(EmergencyCase, case_id)
            c.specialty, c.checklist = specialty, checklist
            base = db.query(Doctor).filter(Doctor.hospital_id == c.hospital_id, Doctor.is_available.is_(True))
            doc = (base.filter(Doctor.specialty == specialty).first() or base.filter(Doctor.specialty == "Emergency Medicine").first()
                   or base.first())
            if not doc:
                ops.log_event(db, case_id, "NO_DOCTOR_AVAILABLE", "No available doctor; hospital staff must assign manually", "agent")
                return None
            ops.set_doctor(db, c, doc, "agent")
            return {"id": doc.id, "name": doc.user.full_name, "specialty": doc.specialty}
        doc = await _in_db(work)
        if doc:
            await self._emit("DoctorAssigned", case_id, doctor=doc["name"])
            await asyncio.sleep(settings.pipeline_step_delay)
        return doc

    async def reserve(self, case_id, needs):
        def work(db):
            c = db.get(EmergencyCase, case_id)
            got = {n: ops.reserve_resource(db, c, n) for n in needs}
            if got.get("ER_BED") and ops.status_idx(c.status) < ops.status_idx("ROOM_RESERVED"):
                c.status = "ROOM_RESERVED"
            missing = [n for n, ok in got.items() if not ok]
            ops.log_event(db, case_id, "ROOM_RESERVED" if got.get("ER_BED") else "RESERVATION_INCOMPLETE",
                          f"Reserved: {', '.join(n for n, ok in got.items() if ok) or 'none'}"
                          + (f"; unavailable: {', '.join(missing)}" if missing else ""), "agent")
            return got
        got = await _in_db(work)
        await self._emit("RoomReserved", case_id, reserved=[n for n, ok in got.items() if ok])
        await self._emit("ResourceUpdated", case_id)
        await asyncio.sleep(settings.pipeline_step_delay)
        return got

    async def notify_all(self, case_id, event, message):
        def work(db):
            c = db.get(EmergencyCase, case_id)
            p = c.patient.user.full_name
            ops.notify_case_users(
                db, c, message,
                f"P{c.priority} {c.emergency_type} patient {p} arriving in ~{c.eta_minutes} min. Brief ready; resources reserved.",
                "Hospital is ready")
            ops.log_event(db, case_id, "NOTIFICATIONS_SENT", "Dashboards, push and SMS (mock) notifications sent", "agent")
        await _in_db(work)
        await self._emit("NotificationsSent", case_id)
