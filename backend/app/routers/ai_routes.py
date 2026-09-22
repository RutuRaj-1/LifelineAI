"""Direct AI endpoints (also usable outside the emergency pipeline, e.g. hospital pre-review)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.agents import DoctorAgent
from ai.summarizer import build_brief

from ..config import get_settings
from ..db import get_db
from ..models import EmergencyCase, MedicalReport, User
from ..security import can_access_patient, current_user
from ..services.runner import get_rag

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post("/summary")
def generate_summary(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    patient_id = body.get("patient_id")
    if not patient_id or not can_access_patient(db, user, patient_id) or user.role == "family":
        raise HTTPException(403, "Not allowed to summarise this patient's records")
    rs = db.query(MedicalReport).filter(MedicalReport.patient_id == patient_id, MedicalReport.extracted_text.isnot(None)).all()
    docs = [{"id": r.id, "title": r.title, "date": r.report_date, "text": r.extracted_text} for r in rs if r.extracted_text.strip()]
    s = get_settings()
    brief = build_brief(docs, get_rag(), body.get("reported", {}), api_key=s.openai_api_key, model=s.openai_model)
    return brief


@router.post("/recommend")
def recommend_specialist(body: dict, user: User = Depends(current_user), db: Session = Depends(get_db)):
    case = db.get(EmergencyCase, body.get("case_id")) if body.get("case_id") else None
    etype = case.emergency_type if case else body.get("emergency_type")
    if not etype:
        raise HTTPException(400, "Provide case_id or emergency_type")
    if case and not can_access_patient(db, user, case.patient_id):
        raise HTTPException(403, "Not allowed")
    return DoctorAgent.recommend(etype, case.ai_summary if case else None)
