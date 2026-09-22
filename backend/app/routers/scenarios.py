"""Demo helper: lets a judge fire one of the 5 seeded emergency scenarios without using the patient app."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Patient, User
from ..scenarios import SCENARIOS
from ..security import require_roles
from ..services import ops
from ..services.runner import start_case
from ..services.serialize import case_dict

router = APIRouter(prefix="/demo", tags=["Demo"])


@router.get("/scenarios")
def list_scenarios(_: User = Depends(require_roles("hospital"))):
    return [{"key": s["key"], "title": s["title"], "emergency_type": s["emergency_type"]} for s in SCENARIOS]


@router.post("/scenarios/{key}/trigger")
def trigger_scenario(key: str, user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    s = next((s for s in SCENARIOS if s["key"] == key), None)
    if not s:
        raise HTTPException(404, "Unknown scenario")
    patient = (db.query(Patient).join(User, User.id == Patient.user_id)
              .filter(User.email == s["patient_email"]).first())
    if not patient:
        raise HTTPException(404, "Demo patient not seeded. Run database/seed.py first.")
    if ops.active_case(db, patient.id):
        raise HTTPException(409, "This demo patient already has an active emergency")
    case = ops.create_case(db, patient.id, s["lat"], s["lng"], s["emergency_type"], s["symptoms"], actor="demo")
    db.commit()
    start_case(case.id)
    return case_dict(case, "hospital", detail=True)
