from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EmergencyCase, Hospital, HospitalResource, User
from ..schemas import ReserveIn
from ..security import require_roles
from ..services import ops
from ..services.serialize import case_dict

router = APIRouter(prefix="/hospital", tags=["Hospital"])


@router.get("/resources")
def get_resources(user: User = Depends(require_roles("hospital", "doctor")), db: Session = Depends(get_db)):
    rows = db.query(HospitalResource).filter(HospitalResource.hospital_id == user.hospital_id).all()
    return [{"resource_type": r.resource_type, "total": r.total, "available": r.available} for r in rows]


@router.post("/reserve")
def reserve(body: ReserveIn, user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    c = db.get(EmergencyCase, body.case_id)
    if not c or c.hospital_id != user.hospital_id:
        raise HTTPException(404, "Case not found at your hospital")
    if not ops.reserve_resource(db, c, body.resource_type):
        raise HTTPException(409, f"No {body.resource_type} available")
    ops.log_event(db, c.id, "MANUAL_RESERVATION", f"{body.resource_type} reserved by staff", "hospital")
    db.commit()
    return {"reserved_resources": c.reserved_resources}


@router.get("/queue")
def emergency_queue(user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    cases = (db.query(EmergencyCase).filter(EmergencyCase.hospital_id == user.hospital_id,
                                            EmergencyCase.status != "COMPLETED")
             .order_by(EmergencyCase.priority, EmergencyCase.created_at).all())
    return [case_dict(c, "hospital", detail=True) for c in cases]


@router.get("/cases/history")
def case_history(user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    cases = (db.query(EmergencyCase).filter(EmergencyCase.hospital_id == user.hospital_id, EmergencyCase.status == "COMPLETED")
             .order_by(EmergencyCase.completed_at.desc()).limit(50).all())
    return [case_dict(c, "hospital", detail=True) for c in cases]
