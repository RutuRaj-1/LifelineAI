from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Doctor, EmergencyCase, User
from ..schemas import AssignIn
from ..security import current_user, doctor_of, require_roles
from ..services import ops
from ..services.serialize import case_dict, doctor_dict

router = APIRouter(tags=["Doctor"])


@router.get("/doctors")
def list_doctors(hospital_id: int | None = None, specialty: str | None = None,
                 user: User = Depends(require_roles("hospital", "doctor")), db: Session = Depends(get_db)):
    q = db.query(Doctor)
    q = q.filter(Doctor.hospital_id == (hospital_id or user.hospital_id)) if (hospital_id or user.hospital_id) else q
    if specialty:
        q = q.filter(Doctor.specialty == specialty)
    return [doctor_dict(d) for d in q.all()]


@router.post("/doctor/assign")
def assign_doctor(body: AssignIn, user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    case, doc = db.get(EmergencyCase, body.case_id), db.get(Doctor, body.doctor_id)
    if not case or not doc:
        raise HTTPException(404, "Case or doctor not found")
    if case.hospital_id != user.hospital_id or doc.hospital_id != user.hospital_id:
        raise HTTPException(403, "Case or doctor does not belong to your hospital")
    if not doc.is_available:
        raise HTTPException(409, "Doctor is not available")
    ops.set_doctor(db, case, doc, "hospital")
    db.commit()
    return case_dict(case, "hospital", detail=True)


@router.get("/doctor/cases")
def my_cases(user: User = Depends(require_roles("doctor")), db: Session = Depends(get_db)):
    d = doctor_of(db, user)
    cases = db.query(EmergencyCase).filter(EmergencyCase.doctor_id == d.id).order_by(EmergencyCase.created_at.desc()).all()
    return [case_dict(c, "doctor", detail=True) for c in cases]
