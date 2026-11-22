"""Post-Emergency Router (Prompt 10).

Manages Emergency Outcome Recording, Discharge Summaries, Medication Reconciliation,
and Longitudinal Follow-Up Plans.
"""
from datetime import datetime, timezone
import os
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ai.ocr import extract_text

from ..db import get_db
from ..models import (
    ActivityLog,
    DischargeSummary,
    EmergencyCase,
    EmergencyOutcome,
    FollowUpPlan,
    Hospital,
    MedicalReport,
    MedicationReconciliation,
    Patient,
    User,
)
from ..schemas import (
    DischargeSummaryApproveIn,
    DischargeSummaryGenerateIn,
    DischargeSummaryOut,
    DischargeSummaryRejectIn,
    EmergencyOutcomeAmend,
    EmergencyOutcomeCreate,
    EmergencyOutcomeOut,
    FollowUpPlanCreate,
    FollowUpPlanOut,
    FollowUpPlanUpdateIn,
    MedicationReconciliationCreate,
    MedicationReconciliationOut,
    MedicationReconciliationVerifyIn,
)
from ..security import current_user, require_roles
from ..services import post_emergency_service, storage

router = APIRouter(prefix="/emergency", tags=["Post-Emergency Continuity"])
ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}
MAX_FILE_BYTES = 10 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_outcome(o: EmergencyOutcome) -> dict:
    return {
        "id": o.id,
        "emergency_case_id": o.emergency_case_id,
        "patient_id": o.patient_id,
        "hospital_id": o.hospital_id,
        "hospital_name": o.hospital.name if o.hospital else None,
        "disposition": o.disposition,
        "disposition_notes": o.disposition_notes,
        "outcome_at": o.outcome_at,
        "verification_status": o.verification_status,
        "recorded_by_user_id": o.recorded_by_user_id,
        "recorded_by_name": o.recorded_by.full_name if o.recorded_by else None,
        "verified_by_user_id": o.verified_by_user_id,
        "verified_by_name": o.verified_by.full_name if o.verified_by else None,
        "verified_at": o.verified_at,
        "version": o.version,
        "parent_outcome_id": o.parent_outcome_id,
        "amendment_reason": o.amendment_reason,
        "created_at": o.created_at,
        "updated_at": o.updated_at,
    }


def _serialize_discharge_summary(s: DischargeSummary) -> dict:
    return {
        "id": s.id,
        "emergency_case_id": s.emergency_case_id,
        "patient_id": s.patient_id,
        "hospital_id": s.hospital_id,
        "hospital_name": s.hospital.name if s.hospital else None,
        "source_report_id": s.source_report_id,
        "version": s.version,
        "status": s.status,
        "admission_date": s.admission_date,
        "discharge_date": s.discharge_date,
        "primary_diagnosis": s.primary_diagnosis,
        "secondary_diagnoses": s.secondary_diagnoses or [],
        "procedures_performed": s.procedures_performed or [],
        "clinical_course": s.clinical_course,
        "discharge_condition": s.discharge_condition,
        "precautions": s.precautions or [],
        "summary_data": s.summary_data or {},
        "author_user_id": s.author_user_id,
        "author_name": s.author_user.full_name if s.author_user else None,
        "approved_by_user_id": s.approved_by_user_id,
        "approved_by_name": s.approved_by.full_name if s.approved_by else None,
        "approved_at": s.approved_at,
        "approval_notes": s.approval_notes,
        "rejection_reason": s.rejection_reason,
        "amendment_reason": s.amendment_reason,
        "is_current_approved": s.is_current_approved,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


def _serialize_med_rec(m: MedicationReconciliation) -> dict:
    return {
        "id": m.id,
        "emergency_case_id": m.emergency_case_id,
        "patient_id": m.patient_id,
        "hospital_id": m.hospital_id,
        "hospital_name": m.hospital.name if m.hospital else None,
        "discharge_summary_id": m.discharge_summary_id,
        "medication_name": m.medication_name,
        "dosage": m.dosage,
        "route": m.route,
        "frequency": m.frequency,
        "reconciliation_status": m.reconciliation_status,
        "source_type": m.source_type,
        "clinical_reason": m.clinical_reason,
        "verification_status": m.verification_status,
        "verified_by_user_id": m.verified_by_user_id,
        "verified_by_name": m.verified_by.full_name if m.verified_by else None,
        "verified_at": m.verified_at,
        "promoted_fact_id": m.promoted_fact_id,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


def _serialize_follow_up(f: FollowUpPlan) -> dict:
    return {
        "id": f.id,
        "emergency_case_id": f.emergency_case_id,
        "patient_id": f.patient_id,
        "hospital_id": f.hospital_id,
        "hospital_name": f.hospital.name if f.hospital else None,
        "department_id": f.department_id,
        "department_name": f.department.department_name if f.department else None,
        "specialty": f.specialty,
        "scheduled_date": f.scheduled_date,
        "instructions": f.instructions,
        "status": f.status,
        "created_by_user_id": f.created_by_user_id,
        "created_by_name": f.created_by.full_name if f.created_by else None,
        "verified_by_user_id": f.verified_by_user_id,
        "verified_by_name": f.verified_by.full_name if f.verified_by else None,
        "verified_at": f.verified_at,
        "completion_notes": f.completion_notes,
        "completed_at": f.completed_at,
        "created_at": f.created_at,
        "updated_at": f.updated_at,
    }


# ==============================================================================
# 1. Emergency Outcome Endpoints
# ==============================================================================

@router.post("/{case_id}/outcome", response_model=EmergencyOutcomeOut, status_code=201)
def record_outcome(
    case_id: int,
    data: EmergencyOutcomeCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Records the clinical and operational outcome/disposition of an emergency case."""
    outcome = post_emergency_service.record_outcome(db, case_id, user, data)
    return _serialize_outcome(outcome)


@router.patch("/{case_id}/outcome", response_model=EmergencyOutcomeOut)
def amend_outcome(
    case_id: int,
    data: EmergencyOutcomeAmend,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Amends an existing emergency outcome with an auditable justification."""
    outcome = post_emergency_service.amend_emergency_outcome(db, case_id, user, data)
    return _serialize_outcome(outcome)


@router.get("/{case_id}/outcome", response_model=EmergencyOutcomeOut | None)
def get_outcome(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Retrieves the active outcome disposition for an emergency case."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(404, "Emergency case not found.")

    # Isolation check
    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or patient.id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "family":
        if not user.linked_patient_id or user.linked_patient_id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(403, "Access denied: Hospital isolation.")

    outcome = post_emergency_service.get_emergency_outcome(db, case_id)
    if not outcome:
        return None
    return _serialize_outcome(outcome)


# ==============================================================================
# 2. Discharge Documentation & Summary Endpoints
# ==============================================================================

@router.post("/{case_id}/discharge-documents", status_code=201)
async def upload_discharge_document(
    case_id: int,
    file: UploadFile = File(...),
    title: str = Form("Hospital Discharge Document"),
    document_type: str = Form("Discharge Summary"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """
    Ingests an official discharge document, runs OCR, and links to the emergency case.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(404, "Emergency case not found.")

    if user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(403, "Access denied: Hospital mismatch.")
    if user.role not in ("hospital", "doctor", "admin"):
        raise HTTPException(403, "Access denied: Cannot upload clinical discharge records.")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"Unsupported file extension {ext}")

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File exceeds 10MB limit")

    saved_path, storage_url = storage.save_report_file(case.patient_id, file.filename or "discharge_doc.pdf", data)
    extracted_text, ocr_status = extract_text(saved_path)

    now = utc_now()
    report = MedicalReport(
        patient_id=case.patient_id,
        title=title.strip(),
        report_type=document_type.strip(),
        original_filename=file.filename,
        storage_url=storage_url,
        extracted_text=extracted_text,
        ocr_status=ocr_status,
        report_date=now.date().isoformat(),
        uploaded_at=now,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Automatically generate an evidence-grounded discharge summary draft
    gen_in = DischargeSummaryGenerateIn(
        primary_diagnosis=f"Post-Emergency Discharge: {case.emergency_type.title()}",
        clinical_course=f"Ingested from {title} ({file.filename}). OCR extraction status: {ocr_status}.",
    )
    summary = post_emergency_service.generate_discharge_summary_draft(
        db, case.id, user, gen_in, source_report_id=report.id
    )

    return {
        "report_id": report.id,
        "title": report.title,
        "ocr_status": report.ocr_status,
        "discharge_summary_id": summary.id,
        "version": summary.version,
        "status": summary.status,
    }


@router.get("/{case_id}/discharge-documents")
def list_discharge_documents(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Retrieves all uploaded medical reports linked to this emergency case's summaries."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(404, "Emergency case not found.")

    summaries = (
        db.query(DischargeSummary)
        .filter(DischargeSummary.emergency_case_id == case.id)
        .all()
    )
    report_ids = [s.source_report_id for s in summaries if s.source_report_id]
    reports = db.query(MedicalReport).filter(MedicalReport.id.in_(report_ids)).all() if report_ids else []

    return [
        {
            "id": r.id,
            "title": r.title,
            "report_type": r.report_type,
            "original_filename": r.original_filename,
            "ocr_status": r.ocr_status,
            "report_date": r.report_date,
            "uploaded_at": r.uploaded_at,
        }
        for r in reports
    ]


@router.post("/{case_id}/discharge-summary/generate", response_model=DischargeSummaryOut, status_code=201)
def generate_discharge_summary(
    case_id: int,
    data: DischargeSummaryGenerateIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Synthesizes an evidence-grounded discharge summary draft for physician review."""
    summary = post_emergency_service.generate_discharge_summary_draft(db, case_id, user, data)
    return _serialize_discharge_summary(summary)


@router.get("/{case_id}/discharge-summary", response_model=DischargeSummaryOut | None)
def get_discharge_summary(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Retrieves the current discharge summary for an emergency case."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(404, "Emergency case not found.")

    # Isolation check
    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or patient.id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "family":
        if not user.linked_patient_id or user.linked_patient_id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(403, "Access denied.")

    summary = post_emergency_service.get_latest_discharge_summary(db, case_id)
    if not summary:
        return None
    return _serialize_discharge_summary(summary)


@router.post("/{case_id}/discharge-summary/{summary_id}/approve", response_model=DischargeSummaryOut)
def approve_discharge_summary(
    case_id: int,
    summary_id: int,
    data: DischargeSummaryApproveIn,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Attending physician approval gate for discharge summary."""
    summary = post_emergency_service.approve_discharge_summary(db, case_id, summary_id, user, data)
    return _serialize_discharge_summary(summary)


@router.post("/{case_id}/discharge-summary/{summary_id}/reject", response_model=DischargeSummaryOut)
def reject_discharge_summary(
    case_id: int,
    summary_id: int,
    data: DischargeSummaryRejectIn,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Attending physician rejection gate for discharge summary."""
    summary = post_emergency_service.reject_discharge_summary(db, case_id, summary_id, user, data)
    return _serialize_discharge_summary(summary)


# ==============================================================================
# 3. Medication Reconciliation Endpoints
# ==============================================================================

@router.post("/{case_id}/medication-reconciliation", response_model=MedicationReconciliationOut, status_code=201)
def create_medication_reconciliation(
    case_id: int,
    data: MedicationReconciliationCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Records a medication reconciliation entry (CONTINUE, START, STOP, CHANGE)."""
    entry = post_emergency_service.create_medication_reconciliation_entry(db, case_id, user, data)
    return _serialize_med_rec(entry)


@router.get("/{case_id}/medication-reconciliation", response_model=list[MedicationReconciliationOut])
def list_medication_reconciliations(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Lists all medication reconciliation entries for an emergency case."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(404, "Emergency case not found.")

    # Isolation check
    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or patient.id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "family":
        if not user.linked_patient_id or user.linked_patient_id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(403, "Access denied.")

    items = post_emergency_service.list_medication_reconciliations(db, case_id)
    return [_serialize_med_rec(m) for m in items]


@router.post("/{case_id}/medication-reconciliation/{item_id}/verify", response_model=MedicationReconciliationOut)
def verify_medication_reconciliation(
    case_id: int,
    item_id: int,
    data: MedicationReconciliationVerifyIn,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Clinician verification gate for medication reconciliation entry."""
    entry = post_emergency_service.verify_medication_reconciliation_entry(db, case_id, item_id, user, data)
    return _serialize_med_rec(entry)


# ==============================================================================
# 4. Longitudinal Follow-Up Plan Endpoints
# ==============================================================================

@router.post("/{case_id}/follow-ups", response_model=FollowUpPlanOut, status_code=201)
def create_follow_up(
    case_id: int,
    data: FollowUpPlanCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Records an explicit documented follow-up plan for an emergency case."""
    plan = post_emergency_service.create_follow_up_plan(db, case_id, user, data)
    return _serialize_follow_up(plan)


@router.get("/{case_id}/follow-ups", response_model=list[FollowUpPlanOut])
def list_follow_ups(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Lists all follow-up plans associated with an emergency case."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(404, "Emergency case not found.")

    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or patient.id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "family":
        if not user.linked_patient_id or user.linked_patient_id != case.patient_id:
            raise HTTPException(403, "Access denied.")
    elif user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(403, "Access denied.")

    items = post_emergency_service.list_follow_up_plans(db, case_id)
    return [_serialize_follow_up(f) for f in items]


# Note: Global patch endpoint for updating follow up status directly
follow_up_router = APIRouter(prefix="/follow-ups", tags=["Post-Emergency Continuity"])


@follow_up_router.patch("/{follow_up_id}", response_model=FollowUpPlanOut)
def update_follow_up_status(
    follow_up_id: int,
    data: FollowUpPlanUpdateIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Updates the status of a follow-up plan (e.g. SCHEDULED, COMPLETED, CANCELLED)."""
    plan = post_emergency_service.update_follow_up_plan(db, follow_up_id, user, data)
    return _serialize_follow_up(plan)
