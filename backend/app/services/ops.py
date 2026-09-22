"""Synchronous domain operations shared by the REST routers, the pipeline and the travel simulator."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import (STATUS_FLOW, ActivityLog, Doctor, EmergencyCase, HospitalResource, Notification, Patient, User)
from . import notifier


def status_idx(s: str) -> int:
    return STATUS_FLOW.index(s)


def log_event(db: Session, case_id: int, event: str, detail: str, actor: str = "system") -> None:
    db.add(ActivityLog(case_id=case_id, event=event, detail=detail, actor=actor))


def event_info(c: EmergencyCase) -> dict:
    return {"case_id": c.id, "patient_id": c.patient_id, "hospital_id": c.hospital_id, "doctor_id": c.doctor_id,
            "status": c.status, "eta_minutes": c.eta_minutes}


def reserve_resource(db: Session, case: EmergencyCase, rtype: str) -> bool:
    """Atomic decrement (UPDATE ... WHERE available > 0) so concurrent reservations cannot oversell."""
    if not case.hospital_id:
        return False
    n = (db.query(HospitalResource)
         .filter(HospitalResource.hospital_id == case.hospital_id, HospitalResource.resource_type == rtype,
                 HospitalResource.available > 0)
         .update({HospitalResource.available: HospitalResource.available - 1}, synchronize_session=False))
    if n and rtype not in (case.reserved_resources or []):
        case.reserved_resources = [*(case.reserved_resources or []), rtype]
    return bool(n)


def release_resources(db: Session, case: EmergencyCase) -> None:
    for rtype in case.reserved_resources or []:
        db.query(HospitalResource).filter(
            HospitalResource.hospital_id == case.hospital_id, HospitalResource.resource_type == rtype,
            HospitalResource.available < HospitalResource.total
        ).update({HospitalResource.available: HospitalResource.available + 1}, synchronize_session=False)


def set_doctor(db: Session, case: EmergencyCase, doctor: Doctor, actor: str = "system") -> None:
    if case.doctor_id and case.doctor_id != doctor.id:
        prev = db.get(Doctor, case.doctor_id)
        if prev:
            prev.is_available = True
    case.doctor_id, doctor.is_available = doctor.id, False
    if status_idx(case.status) < status_idx("DOCTOR_ASSIGNED"):
        case.status = "DOCTOR_ASSIGNED"
    log_event(db, case.id, "DOCTOR_ASSIGNED", f"Dr. {doctor.user.full_name} ({doctor.specialty}) assigned", actor)


def notify_case_users(db: Session, case: EmergencyCase, patient_msg: str, staff_msg: str, title: str) -> None:
    """Dashboard notification for patient, linked family, hospital staff, assigned doctor (+ mock SMS/push)."""
    patient = db.get(Patient, case.patient_id)
    pname = patient.user.full_name
    targets: list[tuple[User, str]] = [(patient.user, patient_msg)]
    targets += [(u, f"{pname}: {patient_msg}") for u in db.query(User).filter(
        User.role == "family", User.linked_patient_id == case.patient_id)]
    if case.hospital_id:
        targets += [(u, staff_msg) for u in db.query(User).filter(User.role == "hospital", User.hospital_id == case.hospital_id)]
    if case.doctor_id:
        targets.append((db.get(Doctor, case.doctor_id).user, staff_msg))
    for user, msg in targets:
        db.add(Notification(user_id=user.id, case_id=case.id, title=title, message=msg, channel="dashboard"))
        notifier.send_push(user.id, title, msg)
        if user.role in ("family", "patient"):
            db.add(Notification(user_id=user.id, case_id=case.id, title=f"SMS (simulated): {title}", message=msg, channel="sms"))
            notifier.send_sms(user.phone, msg)


def touch_arrival(case: EmergencyCase) -> None:
    case.status, case.eta_minutes, case.arrived_at = "PATIENT_ARRIVED", 0, datetime.now(timezone.utc)


def create_case(db: Session, patient_id: int, lat: float, lng: float, etype: str, symptoms: str | None,
                actor: str = "patient") -> EmergencyCase:
    c = EmergencyCase(patient_id=patient_id, lat=lat, lng=lng, current_lat=lat, current_lng=lng,
                      emergency_type=etype, symptoms=symptoms, status="CREATED", checklist=[], reserved_resources=[])
    db.add(c)
    db.flush()
    log_event(db, c.id, "CREATED", f"SOS triggered ({etype}); GPS {lat:.4f}, {lng:.4f}", actor)
    return c


def active_case(db: Session, patient_id: int) -> EmergencyCase | None:
    return db.query(EmergencyCase).filter(EmergencyCase.patient_id == patient_id,
                                          EmergencyCase.status != "COMPLETED").first()
