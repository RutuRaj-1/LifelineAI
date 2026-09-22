from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from ai.ocr import extract_text

from ..config import get_settings
from ..db import get_db
from ..models import MedicalReport, Patient, User
from ..schemas import PatientUpdate
from ..security import can_access_patient, current_user, require_roles
from ..services import storage
from ..services.serialize import patient_dict, report_dict

router = APIRouter(tags=["Patient & Reports"])
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}
MAX_BYTES = 10 * 1024 * 1024


def _own(db: Session, user: User) -> Patient:
    p = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Patient profile not found")
    return p


@router.get("/patient/me")
def my_profile(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    return patient_dict(_own(db, user))


@router.get("/patient/{patient_id}")
def get_patient(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not can_access_patient(db, user, patient_id):
        raise HTTPException(403, "No active emergency or consent for this patient")
    p = db.get(Patient, patient_id)
    if user.role == "family":
        return {"id": p.id, "full_name": p.user.full_name}
    return patient_dict(p)


@router.put("/patient/{patient_id}")
def update_patient(patient_id: int, body: PatientUpdate, user: User = Depends(require_roles("patient")),
                   db: Session = Depends(get_db)):
    p = _own(db, user)
    if p.id != patient_id:
        raise HTTPException(403, "You can only edit your own profile")
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"]:
        user.full_name = data.pop("full_name")
    if "phone" in data:
        user.phone = data.pop("phone")
    if "emergency_contacts" in data:
        p.emergency_contacts = [c if isinstance(c, dict) else c.model_dump() for c in data.pop("emergency_contacts") or []]
    for k, v in data.items():
        setattr(p, k, v)
    db.add(user)
    db.commit()
    return patient_dict(p)


@router.post("/report/upload", status_code=201)
def upload_report(file: UploadFile = File(...), title: str = Form(...), report_type: str = Form("other"),
                  report_date: str | None = Form(None), user: User = Depends(require_roles("patient")),
                  db: Session = Depends(get_db)):
    p = _own(db, user)
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED))}")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 10 MB)")
    path, ref = storage.save_report_file(p.id, file.filename or "report", data)
    text, status = extract_text(path)  # OCR / text extraction
    r = MedicalReport(patient_id=p.id, title=title.strip()[:200], report_type=report_type, original_filename=file.filename,
                      storage_url=ref, extracted_text=text, ocr_status=status, report_date=report_date)
    db.add(r)
    db.commit()
    return report_dict(r)


@router.get("/report/patient/{patient_id}")
def list_reports(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "family" or not can_access_patient(db, user, patient_id):
        raise HTTPException(403, "Not allowed to view these reports")
    rs = db.query(MedicalReport).filter(MedicalReport.patient_id == patient_id).order_by(MedicalReport.report_date.desc()).all()
    return [report_dict(r) for r in rs]


def _report_for(db: Session, user: User, report_id: int) -> MedicalReport:
    r = db.get(MedicalReport, report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    if user.role == "family" or not can_access_patient(db, user, r.patient_id):
        raise HTTPException(403, "Not allowed to view this report")
    return r


@router.get("/report/{report_id}")
def get_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return report_dict(_report_for(db, user, report_id), with_text=True)


@router.get("/report/{report_id}/file")
def download_report(report_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    r = _report_for(db, user, report_id)
    if (r.storage_url or "").startswith("gs://"):
        return RedirectResponse(storage.firebase_signed_url(r.storage_url))
    path = storage.local_path(r.storage_url or "")
    if not path or not path.exists():
        raise HTTPException(404, "Original file not stored (seeded record). Use the extracted text instead.")
    return FileResponse(path, filename=r.original_filename)
