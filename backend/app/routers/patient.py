from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from ai.ocr import extract_text

from ..config import get_settings
from ..db import get_db
from ..models import (
    ClinicalProvenance,
    DischargeSummary,
    EmergencyCase,
    EmergencyOutcome,
    FollowUpPlan,
    MedicalReport,
    MedicationReconciliation,
    Patient,
    PatientClinicalFact,
    User,
)
from ..schemas import PatientClinicalFactUpdate, PatientSelfFactCreate, PatientUpdate
from ..security import can_access_patient, current_user, require_roles
from ..services import storage
from ..services.serialize import fact_dict, patient_dict, report_dict

router = APIRouter(tags=["Patient & Reports"])
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt"}
MAX_BYTES = 10 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _own(db: Session, user: User) -> Patient:
    p = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Patient profile not found")
    return p


# --- Patient Profile Endpoints ---

@router.get("/patient/me")
def my_profile(user: User = Depends(require_roles("patient")), db: Session = Depends(get_db)):
    return patient_dict(_own(db, user))


# --- Prompt 04: Health Vault Overview ---

@router.get("/patient/health-vault")
def get_health_vault(
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Aggregate overview of the authenticated patient's health vault and clinical facts."""
    p = _own(db, user)

    reports = (
        db.query(MedicalReport)
        .filter(MedicalReport.patient_id == p.id)
        .order_by(MedicalReport.report_date.desc(), MedicalReport.uploaded_at.desc())
        .all()
    )
    facts = (
        db.query(PatientClinicalFact)
        .filter(PatientClinicalFact.patient_id == p.id)
        .order_by(PatientClinicalFact.created_at.desc())
        .all()
    )

    conditions = [f for f in facts if f.fact_type == "CONDITION" and f.clinical_status == "ACTIVE"]
    allergies = [f for f in facts if f.fact_type == "ALLERGY" and f.clinical_status == "ACTIVE"]
    medications = [f for f in facts if f.fact_type == "MEDICATION" and f.clinical_status == "ACTIVE"]
    surgeries = [f for f in facts if f.fact_type == "SURGERY"]

    latest_report_date = reports[0].report_date if reports else None

    # Verification summary from provenance
    verification_summary = {"VERIFIED": 0, "REVIEWED": 0, "UNVERIFIED": 0}
    for f in facts:
        for pr in f.provenance_records or []:
            st = pr.verification_status or "UNVERIFIED"
            if st in verification_summary:
                verification_summary[st] += 1
            else:
                verification_summary[st] = 1

    health_summary = {
        "recorded_conditions": [f.fact_value for f in conditions],
        "recorded_allergies": [f.fact_value for f in allergies],
        "recorded_medications": [f.fact_value for f in medications],
        "recorded_surgeries": [f.fact_value for f in surgeries],
        "total_source_documents": len(reports),
        "disclaimer": (
            "Health summary is an organizational aid compiled strictly from uploaded records and self-declared facts. "
            "It is not a clinical diagnosis or medical evaluation. All medical decisions require physician evaluation."
        ),
    }

    return {
        "patient": patient_dict(p),
        "total_reports": len(reports),
        "total_facts": len(facts),
        "conditions_count": len(conditions),
        "allergies_count": len(allergies),
        "medications_count": len(medications),
        "surgeries_count": len(surgeries),
        "latest_report_date": latest_report_date,
        "latest_timeline_event": reports[0].title if reports else (facts[0].fact_value if facts else None),
        "verification_summary": verification_summary,
        "recent_reports": [report_dict(r) for r in reports[:5]],
        "recent_facts": [fact_dict(f) for f in facts[:8]],
        "health_summary": health_summary,
    }


# --- Prompt 04: Structured Clinical Facts & Provenance ---

@router.get("/patient/clinical-facts")
def list_clinical_facts(
    fact_type: str | None = Query(None, description="Filter by fact_type (e.g. CONDITION, ALLERGY, MEDICATION)"),
    clinical_status: str | None = Query(None, description="Filter by status (e.g. ACTIVE, INACTIVE)"),
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieve structured clinical facts for the authenticated patient with full provenance."""
    p = _own(db, user)
    q = db.query(PatientClinicalFact).filter(PatientClinicalFact.patient_id == p.id)
    if fact_type:
        q = q.filter(PatientClinicalFact.fact_type == fact_type.upper())
    if clinical_status:
        q = q.filter(PatientClinicalFact.clinical_status == clinical_status.upper())
    facts = q.order_by(PatientClinicalFact.fact_type.asc(), PatientClinicalFact.created_at.desc()).all()
    return [fact_dict(f) for f in facts]


@router.get("/patient/clinical-facts/{fact_id}")
def get_clinical_fact(
    fact_id: int,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieve an individual clinical fact with all supporting provenance records."""
    p = _own(db, user)
    f = db.get(PatientClinicalFact, fact_id)
    if not f or f.patient_id != p.id:
        raise HTTPException(404, "Clinical fact not found")
    return fact_dict(f)


@router.post("/patient/clinical-facts", status_code=201)
def create_clinical_fact(
    body: PatientSelfFactCreate,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Allow a patient to enter a new personal medical fact with automated provenance tracking."""
    p = _own(db, user)
    fact = PatientClinicalFact(
        patient_id=p.id,
        fact_type=body.fact_type,
        fact_code=body.fact_code,
        fact_value=body.fact_value.strip(),
        normalized_value=body.normalized_value or body.fact_value.strip(),
        clinical_status=body.clinical_status,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
    )
    db.add(fact)
    db.flush()

    # Automate provenance for self-entered facts
    provenance = ClinicalProvenance(
        clinical_fact_id=fact.id,
        source_type="PATIENT_ENTERED",
        source_user_id=user.id,
        source_reference="Patient Self-Report (Health Vault)",
        source_excerpt=body.notes or f"Self-reported {body.fact_type.lower()}: {body.fact_value}",
        verification_status="UNVERIFIED",
        verification_notes="Self-reported by patient; requires clinician review.",
    )
    db.add(provenance)
    db.commit()
    db.refresh(fact)
    return fact_dict(fact)


@router.patch("/patient/clinical-facts/{fact_id}")
def update_clinical_fact(
    fact_id: int,
    body: PatientClinicalFactUpdate,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Update or correct a patient clinical fact, appending a verifiable provenance entry."""
    p = _own(db, user)
    fact = db.get(PatientClinicalFact, fact_id)
    if not fact or fact.patient_id != p.id:
        raise HTTPException(404, "Clinical fact not found")

    if body.fact_value is not None:
        fact.fact_value = body.fact_value.strip()
    if body.normalized_value is not None:
        fact.normalized_value = body.normalized_value.strip()
    if body.clinical_status is not None:
        fact.clinical_status = body.clinical_status
    if body.effective_from is not None:
        fact.effective_from = body.effective_from
    if body.effective_to is not None:
        fact.effective_to = body.effective_to

    # Append provenance update without erasing historical provenance
    prov = ClinicalProvenance(
        clinical_fact_id=fact.id,
        source_type="PATIENT_ENTERED",
        source_user_id=user.id,
        source_reference="Patient Self-Correction",
        source_excerpt=body.update_notes or f"Updated value to: {fact.fact_value} (status: {fact.clinical_status})",
        verification_status="UNVERIFIED",
        verification_notes="Updated by patient in health vault.",
    )
    db.add(prov)
    db.commit()
    db.refresh(fact)
    return fact_dict(fact)


@router.delete("/patient/clinical-facts/{fact_id}")
def deactivate_clinical_fact(
    fact_id: int,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Deactivate/archive a clinical fact while preserving provenance audit history."""
    p = _own(db, user)
    fact = db.get(PatientClinicalFact, fact_id)
    if not fact or fact.patient_id != p.id:
        raise HTTPException(404, "Clinical fact not found")

    fact.clinical_status = "INACTIVE"
    prov = ClinicalProvenance(
        clinical_fact_id=fact.id,
        source_type="PATIENT_ENTERED",
        source_user_id=user.id,
        source_reference="Patient Self-Deactivation",
        source_excerpt="Marked inactive/archived by patient",
        verification_status="UNVERIFIED",
        verification_notes="Deactivated by patient.",
    )
    db.add(prov)
    db.commit()
    return {"status": "deactivated", "id": fact_id}


# --- Prompt 04: Longitudinal Health Timeline ---

@router.get("/patient/health-timeline")
def get_health_timeline(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Chronological longitudinal health timeline merging reports, structured facts, and emergency events."""
    p = _own(db, user)
    events = []

    # 1. Medical Report Uploads
    reports = db.query(MedicalReport).filter(MedicalReport.patient_id == p.id).all()
    for r in reports:
        report_dt_str = r.report_date or (r.uploaded_at.date().isoformat() if r.uploaded_at else "Unknown Date")
        events.append({
            "id": f"report-{r.id}",
            "event_type": "REPORT_UPLOADED",
            "title": r.title,
            "description": f"Uploaded {r.report_type} ({r.original_filename or 'document'}). OCR status: {r.ocr_status}.",
            "event_date": report_dt_str,
            "recorded_at": r.uploaded_at.isoformat() if r.uploaded_at else report_dt_str,
            "source_reference": f"Medical Report #{r.id}",
            "provenance_source": "OCR_EXTRACTED",
            "verification_status": "REVIEWED" if r.ocr_status == "ok" else "UNVERIFIED",
            "has_supporting_document": True,
            "report_id": r.id,
            "metadata": {"report_type": r.report_type, "ocr_status": r.ocr_status},
        })

    # 2. Structured Clinical Facts
    facts = db.query(PatientClinicalFact).filter(PatientClinicalFact.patient_id == p.id).all()
    for f in facts:
        primary_prov = f.provenance_records[0] if f.provenance_records else None
        fact_date = f.effective_from or (f.created_at.date().isoformat() if f.created_at else None)
        events.append({
            "id": f"fact-{f.id}",
            "event_type": "CLINICAL_FACT",
            "title": f"{f.fact_type.replace('_', ' ').title()}: {f.fact_value}",
            "description": f"Status: {f.clinical_status}. Source: {primary_prov.source_type if primary_prov else 'PATIENT_ENTERED'}.",
            "event_date": fact_date,
            "recorded_at": f.created_at.isoformat() if f.created_at else "",
            "source_reference": primary_prov.source_reference if primary_prov else "Self-declared",
            "provenance_source": primary_prov.source_type if primary_prov else "PATIENT_ENTERED",
            "verification_status": primary_prov.verification_status if primary_prov else "UNVERIFIED",
            "has_supporting_document": primary_prov.source_report_id is not None if primary_prov else False,
            "report_id": primary_prov.source_report_id if primary_prov else None,
            "metadata": {"fact_type": f.fact_type, "clinical_status": f.clinical_status},
        })

    # 3. Emergency Events
    emergencies = db.query(EmergencyCase).filter(EmergencyCase.patient_id == p.id).all()
    for ec in emergencies:
        hosp_name = ec.hospital.name if ec.hospital else "Emergency Coordination Centre"
        case_date = ec.created_at.date().isoformat() if ec.created_at else None
        events.append({
            "id": f"emergency-{ec.id}",
            "event_type": "EMERGENCY_VISIT",
            "title": f"Emergency Incident: {ec.emergency_type.upper()}",
            "description": f"Emergency case #{ec.id} routed to {hosp_name}. Status: {ec.status}.",
            "event_date": case_date,
            "recorded_at": ec.created_at.isoformat() if ec.created_at else "",
            "source_reference": f"Emergency Case #{ec.id}",
            "provenance_source": "HOSPITAL_IMPORTED",
            "verification_status": "VERIFIED" if ec.status == "COMPLETED" else "REVIEWED",
            "has_supporting_document": False,
            "report_id": None,
            "metadata": {"case_id": ec.id, "emergency_type": ec.emergency_type, "status": ec.status},
        })

    # 4. Approved Discharge Summaries (Prompt 10)
    summaries = (
        db.query(DischargeSummary)
        .filter(DischargeSummary.patient_id == p.id, DischargeSummary.is_current_approved == True)
        .all()
    )
    for ds in summaries:
        hosp_name = ds.hospital.name if ds.hospital else "Hospital"
        events.append({
            "id": f"discharge-{ds.id}",
            "event_type": "DISCHARGE_SUMMARY",
            "title": f"Hospital Discharge: {ds.primary_diagnosis or 'Summary'}",
            "description": f"Discharged from {hosp_name}. Condition: {ds.discharge_condition or 'Stable'}.",
            "event_date": ds.discharge_date or (ds.approved_at.date().isoformat() if ds.approved_at else None),
            "recorded_at": ds.approved_at.isoformat() if ds.approved_at else (ds.created_at.isoformat() if ds.created_at else ""),
            "source_reference": f"Discharge Summary v{ds.version} (Case #{ds.emergency_case_id})",
            "provenance_source": "DOCTOR_VERIFIED",
            "verification_status": "VERIFIED",
            "has_supporting_document": ds.source_report_id is not None,
            "report_id": ds.source_report_id,
            "metadata": {
                "summary_id": ds.id,
                "case_id": ds.emergency_case_id,
                "primary_diagnosis": ds.primary_diagnosis,
                "discharge_condition": ds.discharge_condition,
            },
        })

    # 5. Clinician-Verified Medication Reconciliation (Prompt 10)
    med_recs = (
        db.query(MedicationReconciliation)
        .filter(
            MedicationReconciliation.patient_id == p.id,
            MedicationReconciliation.verification_status.in_(["VERIFIED", "CLINICIAN_VERIFIED"]),
        )
        .all()
    )
    for mr in med_recs:
        rec_date = mr.verified_at.date().isoformat() if mr.verified_at else mr.created_at.date().isoformat()
        events.append({
            "id": f"medrec-{mr.id}",
            "event_type": "MEDICATION_RECONCILED",
            "title": f"Medication {mr.reconciliation_status}: {mr.medication_name}",
            "description": f"Dosage: {mr.dosage or 'standard'}, Frequency: {mr.frequency or 'daily'}. Reason: {mr.clinical_reason or 'Emergency discharge reconciliation'}.",
            "event_date": rec_date,
            "recorded_at": mr.verified_at.isoformat() if mr.verified_at else mr.created_at.isoformat(),
            "source_reference": f"Medication Reconciliation (Case #{mr.emergency_case_id})",
            "provenance_source": "DOCTOR_VERIFIED",
            "verification_status": "VERIFIED",
            "has_supporting_document": False,
            "report_id": None,
            "metadata": {
                "medication_name": mr.medication_name,
                "dosage": mr.dosage,
                "status": mr.reconciliation_status,
            },
        })

    # 6. Longitudinal Follow-Up Plans (Prompt 10)
    follow_ups = (
        db.query(FollowUpPlan)
        .filter(FollowUpPlan.patient_id == p.id)
        .all()
    )
    for fu in follow_ups:
        events.append({
            "id": f"followup-{fu.id}",
            "event_type": "FOLLOW_UP_PLAN",
            "title": f"Follow-Up: {fu.specialty} ({fu.status})",
            "description": f"Instructions: {fu.instructions}. Scheduled: {fu.scheduled_date or 'To be scheduled'}.",
            "event_date": fu.scheduled_date or (fu.created_at.date().isoformat() if fu.created_at else None),
            "recorded_at": fu.created_at.isoformat() if fu.created_at else "",
            "source_reference": f"Follow-Up Plan #{fu.id} (Case #{fu.emergency_case_id})",
            "provenance_source": "HOSPITAL_IMPORTED",
            "verification_status": "REVIEWED" if fu.verified_by_user_id else "UNVERIFIED",
            "has_supporting_document": False,
            "report_id": None,
            "metadata": {"specialty": fu.specialty, "status": fu.status, "scheduled_date": fu.scheduled_date},
        })

    # Sort newest date first safely
    def sort_key(ev):
        return ev.get("event_date") or ev.get("recorded_at") or ""

    events.sort(key=sort_key, reverse=True)
    total = len(events)
    paginated = events[offset : offset + limit]

    return {
        "events": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# --- Prompt 10: Patient Post-Emergency History & Continuity APIs ---

@router.get("/patient/emergency-history")
def get_emergency_history(
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieves full longitudinal emergency encounter history for the authenticated patient."""
    p = _own(db, user)
    cases = (
        db.query(EmergencyCase)
        .filter(EmergencyCase.patient_id == p.id)
        .order_by(EmergencyCase.created_at.desc())
        .all()
    )

    items = []
    for c in cases:
        # Latest active outcome
        outcome = (
            db.query(EmergencyOutcome)
            .filter(EmergencyOutcome.emergency_case_id == c.id)
            .order_by(EmergencyOutcome.version.desc())
            .first()
        )
        # Approved discharge summary
        ds = (
            db.query(DischargeSummary)
            .filter(DischargeSummary.emergency_case_id == c.id, DischargeSummary.is_current_approved == True)
            .first()
        )
        if not ds:
            ds = (
                db.query(DischargeSummary)
                .filter(DischargeSummary.emergency_case_id == c.id)
                .order_by(DischargeSummary.version.desc())
                .first()
            )

        fu_count = db.query(FollowUpPlan).filter(FollowUpPlan.emergency_case_id == c.id).count()
        med_count = db.query(MedicationReconciliation).filter(MedicationReconciliation.emergency_case_id == c.id).count()

        items.append({
            "case_id": c.id,
            "emergency_type": c.emergency_type,
            "status": c.status,
            "priority": c.priority,
            "created_at": c.created_at,
            "completed_at": c.completed_at,
            "hospital_id": c.hospital_id,
            "hospital_name": c.hospital.name if c.hospital else None,
            "hospital_address": c.hospital.address if c.hospital else None,
            "outcome": {
                "id": outcome.id,
                "disposition": outcome.disposition,
                "disposition_notes": outcome.disposition_notes,
                "outcome_at": outcome.outcome_at,
                "verification_status": outcome.verification_status,
                "version": outcome.version,
            } if outcome else None,
            "discharge_summary": {
                "id": ds.id,
                "version": ds.version,
                "status": ds.status,
                "primary_diagnosis": ds.primary_diagnosis,
                "discharge_condition": ds.discharge_condition,
                "discharge_date": ds.discharge_date,
                "precautions": ds.precautions or [],
                "is_current_approved": ds.is_current_approved,
            } if ds else None,
            "follow_up_count": fu_count,
            "medication_count": med_count,
        })
    return items


@router.get("/patient/discharge-summaries")
def get_patient_discharge_summaries(
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieves all approved discharge summaries for the authenticated patient."""
    p = _own(db, user)
    summaries = (
        db.query(DischargeSummary)
        .filter(DischargeSummary.patient_id == p.id, DischargeSummary.is_current_approved == True)
        .order_by(DischargeSummary.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "emergency_case_id": s.emergency_case_id,
            "hospital_id": s.hospital_id,
            "hospital_name": s.hospital.name if s.hospital else None,
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
            "summary_data": s.summary_data,
            "approved_at": s.approved_at,
            "approval_notes": s.approval_notes,
        }
        for s in summaries
    ]


@router.get("/patient/medication-reconciliation")
def get_patient_medications(
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieves all verified medication reconciliation records for the authenticated patient."""
    p = _own(db, user)
    meds = (
        db.query(MedicationReconciliation)
        .filter(MedicationReconciliation.patient_id == p.id, MedicationReconciliation.verification_status == "CLINICIAN_VERIFIED")
        .order_by(MedicationReconciliation.created_at.desc())
        .all()
    )
    return [
        {
            "id": m.id,
            "emergency_case_id": m.emergency_case_id,
            "hospital_name": m.hospital.name if m.hospital else None,
            "medication_name": m.medication_name,
            "dosage": m.dosage,
            "route": m.route,
            "frequency": m.frequency,
            "reconciliation_status": m.reconciliation_status,
            "clinical_reason": m.clinical_reason,
            "verification_status": m.verification_status,
            "verified_at": m.verified_at,
        }
        for m in meds
    ]


@router.get("/patient/follow-ups")
def get_patient_follow_ups(
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieves all documented follow-up instructions and plans for the authenticated patient."""
    p = _own(db, user)
    plans = (
        db.query(FollowUpPlan)
        .filter(FollowUpPlan.patient_id == p.id)
        .order_by(FollowUpPlan.scheduled_date.asc(), FollowUpPlan.created_at.desc())
        .all()
    )
    return [
        {
            "id": f.id,
            "emergency_case_id": f.emergency_case_id,
            "hospital_name": f.hospital.name if f.hospital else None,
            "department_name": f.department.department_name if f.department else None,
            "specialty": f.specialty,
            "scheduled_date": f.scheduled_date,
            "instructions": f.instructions,
            "status": f.status,
            "completion_notes": f.completion_notes,
            "completed_at": f.completed_at,
        }
        for f in plans
    ]


# --- Medical Report APIs ---

@router.get("/patient/medical-reports")
def list_my_reports(
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieve all uploaded medical reports for the authenticated patient."""
    p = _own(db, user)
    reports = (
        db.query(MedicalReport)
        .filter(MedicalReport.patient_id == p.id)
        .order_by(MedicalReport.report_date.desc(), MedicalReport.uploaded_at.desc())
        .all()
    )
    return [report_dict(r) for r in reports]


@router.get("/patient/medical-reports/{report_id}")
def get_my_report_detail(
    report_id: int,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    """Retrieve detailed metadata and extracted OCR text for an individual report."""
    p = _own(db, user)
    r = db.get(MedicalReport, report_id)
    if not r or r.patient_id != p.id:
        raise HTTPException(404, "Report not found")
    return report_dict(r, with_text=True)


@router.get("/patient/{patient_id}")
def get_patient(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not can_access_patient(db, user, patient_id):
        raise HTTPException(403, "No active emergency or consent for this patient")
    p = db.get(Patient, patient_id)
    if not p:
        raise HTTPException(404, "Patient not found")
    if user.role == "family":
        return {"id": p.id, "full_name": p.user.full_name}
    return patient_dict(p)


@router.put("/patient/{patient_id}")
def update_patient(
    patient_id: int,
    body: PatientUpdate,
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    p = _own(db, user)
    if p.id != patient_id:
        raise HTTPException(403, "You can only edit your own profile")
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"]:
        user.full_name = data.pop("full_name")
    if "phone" in data:
        user.phone = data.pop("phone")
    if "emergency_contacts" in data:
        p.emergency_contacts = [
            c if isinstance(c, dict) else c.model_dump() for c in data.pop("emergency_contacts") or []
        ]
    for k, v in data.items():
        setattr(p, k, v)
    db.add(user)
    db.commit()
    return patient_dict(p)


@router.post("/report/upload", status_code=201)
def upload_report(
    file: UploadFile = File(...),
    title: str = Form(...),
    report_type: str = Form("other"),
    report_date: str | None = Form(None),
    user: User = Depends(require_roles("patient")),
    db: Session = Depends(get_db),
):
    p = _own(db, user)
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED:
        raise HTTPException(415, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED))}")
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "File too large (max 10 MB)")
    path, ref = storage.save_report_file(p.id, file.filename or "report", data)
    text, status = extract_text(path)  # OCR / text extraction
    r = MedicalReport(
        patient_id=p.id,
        title=title.strip()[:200],
        report_type=report_type,
        original_filename=file.filename,
        storage_url=ref,
        extracted_text=text,
        ocr_status=status,
        report_date=report_date,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return report_dict(r)


@router.get("/report/patient/{patient_id}")
def list_reports(patient_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "family" or not can_access_patient(db, user, patient_id):
        raise HTTPException(403, "Not allowed to view these reports")
    rs = (
        db.query(MedicalReport)
        .filter(MedicalReport.patient_id == patient_id)
        .order_by(MedicalReport.report_date.desc())
        .all()
    )
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
