from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ActivityLog, EmergencyCase, Patient, User
from ..schemas import EmergencyIn, LocationIn
from ..security import can_access_patient, current_user, require_roles
from ..services import ops
from ..services.runner import start_case
from ..services.serialize import case_dict

router = APIRouter(prefix="/emergency", tags=["Emergency"])


def _own_patient(db: Session, user: User) -> Patient:
    p = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Patient profile not found")
    return p


@router.post("", status_code=201)
def create_emergency(body: EmergencyIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    p = _own_patient(db, user)
    if ops.active_case(db, p.id):
        raise HTTPException(409, "An emergency is already active for this patient")
    case = ops.create_case(db, p.id, body.lat, body.lng, body.emergency_type, body.symptoms)
    db.commit()
    start_case(case.id)  # kicks off the async agent pipeline + demo travel simulation
    return case_dict(case, "patient", detail=True)


@router.get("/active")
def my_active_emergency(user: User = Depends(require_roles("patient", "family")), db: Session = Depends(get_db)):
    patient_id = _own_patient(db, user).id if user.role == "patient" else user.linked_patient_id
    if not patient_id:
        raise HTTPException(404, "No linked patient")
    c = ops.active_case(db, patient_id)
    return case_dict(c, user.role, detail=True) if c else None


@router.get("/{case_id}")
def get_emergency(case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(404, "Emergency case not found")
    if not can_access_patient(db, user, c.patient_id):
        raise HTTPException(403, "Not allowed to view this emergency")
    return case_dict(c, user.role, detail=True)


@router.get("/{case_id}/timeline")
def get_timeline(case_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(404, "Emergency case not found")
    if not can_access_patient(db, user, c.patient_id):
        raise HTTPException(403, "Not allowed to view this emergency")
    rows = db.query(ActivityLog).filter(ActivityLog.case_id == case_id).order_by(ActivityLog.created_at).all()
    hide_clinical = user.role == "family"
    return [{"event": r.event, "detail": "Status update" if hide_clinical and "SUMMARY" in r.event else r.detail,
            "actor": r.actor, "at": r.created_at.isoformat()} for r in rows]


@router.put("/{case_id}/location")
def update_location(case_id: int, body: LocationIn, user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    """Manual GPS ping from the patient app (in the demo, the server-side simulator also moves the marker)."""
    c = db.get(EmergencyCase, case_id)
    if not c or not can_access_patient(db, user, c.patient_id):
        raise HTTPException(404, "Emergency case not found")
    c.current_lat, c.current_lng = body.lat, body.lng
    db.commit()
    return {"ok": True}


@router.post("/{case_id}/checklist")
def update_checklist(case_id: int, body: dict, user: User = Depends(require_roles("doctor", "hospital")),
                     db: Session = Depends(get_db)):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(404, "Emergency case not found")
    idx = body.get("index")
    items = list(c.checklist or [])
    if idx is None or not (0 <= idx < len(items)):
        raise HTTPException(400, "Invalid checklist index")
    items[idx] = {**items[idx], "done": bool(body.get("done", True))}
    c.checklist = items
    ops.log_event(db, case_id, "CHECKLIST_UPDATED", f"'{items[idx]['item']}' marked {'done' if items[idx]['done'] else 'pending'}", user.role)
    db.commit()
    return {"checklist": c.checklist}


@router.post("/{case_id}/complete")
def complete_case(case_id: int, user: User = Depends(require_roles("hospital", "doctor")), db: Session = Depends(get_db)):
    from datetime import datetime, timezone

    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(404, "Emergency case not found")
    c.status, c.completed_at = "COMPLETED", datetime.now(timezone.utc)
    if c.doctor:
        c.doctor.is_available = True
    ops.release_resources(db, c)
    ops.log_event(db, case_id, "COMPLETED", "Case closed", user.role)
    db.commit()
    return case_dict(c, user.role, detail=True)
