"""Evidence-Grounded Clinical Handover Engine (Prompt 08).

Prepares concise, structured, non-diagnostic clinical handovers grounded in:
1. Live incident reports (with source provenance, witness vs patient).
2. Historical patient context (verified clinical facts, OCR extracts).
3. Missing and uncertain information warnings (negative inference prevention).
4. Strict human review & approval gates (doctor/coordinator approval before hospital sharing).
5. Immutable versioning upon arrival of new incident data.

Strict AI Boundary:
- Organizes existing records; NEVER diagnoses, prescribes, or suggests treatment.
- Explicitly flags missing fields; does NOT infer absence of allergies or conditions.
"""
from datetime import datetime, timezone
import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..models import (
    ActivityLog,
    ClinicalHandover,
    ClinicalProvenance,
    EmergencyCase,
    EmergencyIncidentReport,
    MedicalReport,
    Patient,
    PatientClinicalFact,
    User,
)
from .emergency_service import broadcast_emergency_event

logger = logging.getLogger("lifeline.handover_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def age_of(dob: str | None) -> int | None:
    if not dob:
        return None
    try:
        from datetime import date
        d = date.fromisoformat(dob)
        t = date.today()
        return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    except Exception:
        return None


NON_DIAGNOSTIC_DISCLAIMER = (
    "EVIDENCE-GROUNDED INFORMATION HANDOVER ONLY. "
    "This clinical handover organizes documented historical records and incident reports for care coordination. "
    "It does NOT contain medical diagnoses, prescriptions, treatment advice, or autonomous triage decisions. "
    "All clinical decisions remain the responsibility of authorized treating physicians."
)


def generate_clinical_handover(
    db: Session,
    case_id: int,
    generating_user: User | None = None,
    notes: str | None = None,
) -> ClinicalHandover:
    """
    Constructs an evidence-grounded, non-diagnostic clinical handover draft:
    - Synthesizes live incident reports and historical clinical facts.
    - Explicitly identifies missing and uncertain information.
    - Increments version number preserving immutable prior versions.
    - Leaves status as PENDING_REVIEW awaiting authorized doctor approval.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    patient = case.patient
    now = utc_now()

    # 1. Gather Live Incident Reports
    reports = (
        db.query(EmergencyIncidentReport)
        .filter(EmergencyIncidentReport.emergency_case_id == case.id)
        .order_by(EmergencyIncidentReport.received_at.asc())
        .all()
    )

    incident_items = []
    witness_report_count = 0
    unverified_report_count = 0
    for r in reports:
        is_witness = r.reporter_type in ("WITNESS", "BYSTANDER", "FAMILY")
        if is_witness:
            witness_report_count += 1
        if r.verification_status == "UNVERIFIED":
            unverified_report_count += 1

        incident_items.append({
            "report_id": r.id,
            "reporter_type": r.reporter_type,
            "reporter_role": r.reporter_role,
            "report_type": r.report_type,
            "reported_text": r.reported_text,
            "observed_at": r.observed_at.isoformat() if r.observed_at else None,
            "received_at": r.received_at.isoformat(),
            "verification_status": r.verification_status,
            "is_witness_report": is_witness,
            "is_clinician_confirmed": r.verification_status == "CLINICIAN_CONFIRMED",
            "parent_report_id": r.parent_report_id,
            "transcription_status": r.transcription_status,
        })

    # 2. Gather Historical Clinical Facts (Prompt 04)
    facts = (
        db.query(PatientClinicalFact)
        .filter(PatientClinicalFact.patient_id == case.patient_id)
        .order_by(PatientClinicalFact.fact_type.asc(), PatientClinicalFact.created_at.desc())
        .all()
    )

    fact_items = []
    has_allergy_facts = False
    has_medication_facts = False
    for f in facts:
        ftype = (f.fact_type or "").upper()
        if ftype == "ALLERGY":
            has_allergy_facts = True
        elif ftype in ("MEDICATION", "PRESCRIPTION"):
            has_medication_facts = True

        provenance_records = []
        for p in f.provenance_records:
            provenance_records.append({
                "provenance_id": p.id,
                "source_type": p.source_type,
                "source_report_id": p.source_report_id,
                "source_reference": p.source_reference,
                "source_excerpt": p.source_excerpt,
                "verification_status": p.verification_status,
            })

        is_verified = any(p.verification_status == "VERIFIED" for p in f.provenance_records)

        fact_items.append({
            "fact_id": f.id,
            "type": f.fact_type,
            "value": f.fact_value,
            "clinical_status": f.clinical_status,
            "verification_status": "VERIFIED" if is_verified else "UNVERIFIED",
            "is_verified": is_verified,
            "sources": provenance_records,
        })

    # 3. Gather Medical Reports
    med_reports = (
        db.query(MedicalReport)
        .filter(MedicalReport.patient_id == case.patient_id)
        .order_by(MedicalReport.report_date.desc().nullslast())
        .all()
    )
    report_items = [
        {
            "report_id": rep.id,
            "title": rep.title,
            "report_type": rep.report_type,
            "report_date": rep.report_date,
            "ocr_status": rep.ocr_status,
        }
        for rep in med_reports
    ]

    # 4. Strict Missing & Uncertain Information Warnings
    missing_warnings = []
    if not has_allergy_facts:
        missing_warnings.append(
            "NO DOCUMENTED ALLERGY RECORDS: No allergy records were found in historical documentation. "
            "WARNING: Absence of documented allergy records does NOT indicate absence of clinical allergies. "
            "Direct clinical allergy inquiry must be performed upon patient arrival."
        )
    if not has_medication_facts:
        missing_warnings.append(
            "NO DOCUMENTED MEDICATIONS: No active medications documented in retrieved records. "
            "Medication reconciliation must be conducted with the patient or family."
        )
    if witness_report_count > 0:
        missing_warnings.append(
            f"UNVERIFIED WITNESS STATEMENTS: {witness_report_count} incident statement(s) are bystander/family reported. "
            "Observations reflect lay reports and must not be treated as confirmed clinical diagnostic events."
        )
    if case.location_accuracy_meters and case.location_accuracy_meters > 100:
        missing_warnings.append(
            f"UNCERTAIN LOCATION ACCURACY: Current incident GPS accuracy radius is ±{case.location_accuracy_meters:.0f}m."
        )

    # 5. Build Complete Handover Payload
    handover_data = {
        "emergency_identification": {
            "case_id": case.id,
            "patient_id": case.patient_id,
            "patient_name": patient.user.full_name if patient and patient.user else "Emergency Patient",
            "age": age_of(patient.dob) if patient else None,
            "gender": patient.gender if patient else None,
            "blood_group": patient.blood_group if patient else None,
            "emergency_type": case.emergency_type,
            "specialty": case.specialty,
            "incident_initiated_at": case.created_at.isoformat(),
            "location": {
                "latitude": case.current_lat or case.lat,
                "longitude": case.current_lng or case.lng,
                "source": case.location_source,
                "accuracy_meters": case.location_accuracy_meters,
            },
            "status": case.status,
            "generation_notes": notes,
        },
        "current_incident": {
            "initial_symptoms": case.symptoms,
            "reports_count": len(incident_items),
            "reports": incident_items,
        },
        "historical_medical_context": {
            "clinical_facts_count": len(fact_items),
            "clinical_facts": fact_items,
            "uploaded_medical_reports": report_items,
        },
        "missing_and_uncertain_information": missing_warnings,
        "provenance_summary": {
            "total_incident_reports": len(incident_items),
            "witness_reports": witness_report_count,
            "unverified_incident_reports": unverified_report_count,
            "historical_facts": len(fact_items),
            "clinician_verified_facts": sum(1 for f in fact_items if f["is_verified"]),
        },
        "non_diagnostic_disclaimer": NON_DIAGNOSTIC_DISCLAIMER,
    }

    # 6. Version Calculation
    max_version = (
        db.query(func.coalesce(func.max(ClinicalHandover.version), 0))
        .filter(ClinicalHandover.emergency_case_id == case.id)
        .scalar()
    )
    new_version = max_version + 1

    handover = ClinicalHandover(
        emergency_case_id=case.id,
        version=new_version,
        status="PENDING_REVIEW",
        handover_data=handover_data,
        is_current_approved=False,
        created_at=now,
    )
    db.add(handover)

    # Activity log
    log = ActivityLog(
        case_id=case.id,
        event="HANDOVER_GENERATED",
        detail=f"Clinical handover v{new_version} generated with {len(incident_items)} incident reports and {len(fact_items)} clinical facts.",
        actor=generating_user.full_name if generating_user else "LifeLine AI Pipeline",
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(handover)

    broadcast_emergency_event(
        "HANDOVER_GENERATED",
        case,
        extra={"handover_id": handover.id, "handover_version": new_version},
    )
    return handover


def approve_clinical_handover(
    db: Session,
    handover_id: int,
    doctor_user: User,
    approval_notes: str | None = None,
) -> ClinicalHandover:
    """
    Authorized Doctor / Coordinator approval gate:
    - Validates handover is in PENDING_REVIEW or DRAFT status.
    - Transitions status to APPROVED.
    - Supersedes previous approved versions for this emergency case.
    - Links emergency_case.current_handover_id to this approved handover.
    """
    handover = db.get(ClinicalHandover, handover_id)
    if not handover:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clinical handover not found.")

    if doctor_user.role != "doctor":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied: Clinical authority required. Only qualified physicians can approve clinical handovers.",
        )

    if handover.status not in ("PENDING_REVIEW", "DRAFT"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot approve handover in status: {handover.status}.",
        )

    now = utc_now()

    # 1. Mark previous approved handovers as SUPERSEDED
    prev_approved = (
        db.query(ClinicalHandover)
        .filter(
            ClinicalHandover.emergency_case_id == handover.emergency_case_id,
            ClinicalHandover.is_current_approved.is_(True),
            ClinicalHandover.id != handover.id,
        )
        .all()
    )
    for p in prev_approved:
        p.is_current_approved = False
        p.status = "SUPERSEDED"

    # 2. Approve this handover
    handover.status = "APPROVED"
    handover.is_current_approved = True
    handover.approved_by_user_id = doctor_user.id
    handover.approved_at = now
    handover.approval_notes = approval_notes

    # 3. Link to EmergencyCase
    case = handover.emergency_case
    case.current_handover_id = handover.id
    case.updated_at = now

    log = ActivityLog(
        case_id=case.id,
        event="HANDOVER_APPROVED",
        detail=f"Clinical handover v{handover.version} approved by Dr. {doctor_user.full_name}. {approval_notes or ''}".strip(),
        actor=doctor_user.full_name or doctor_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(handover)

    broadcast_emergency_event(
        "HANDOVER_APPROVED",
        case,
        extra={"handover_id": handover.id, "handover_version": handover.version},
    )
    return handover


def reject_clinical_handover(
    db: Session,
    handover_id: int,
    doctor_user: User,
    rejection_reason: str,
) -> ClinicalHandover:
    """Explicitly rejects a handover draft with clinical rationale."""
    handover = db.get(ClinicalHandover, handover_id)
    if not handover:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clinical handover not found.")

    if doctor_user.role not in ("doctor", "admin"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied: Only authorized physicians or coordinators can reject handovers.",
        )

    now = utc_now()
    handover.status = "REJECTED"
    handover.rejection_reason = rejection_reason
    handover.is_current_approved = False

    case = handover.emergency_case
    log = ActivityLog(
        case_id=case.id,
        event="HANDOVER_REJECTED",
        detail=f"Clinical handover v{handover.version} rejected by Dr. {doctor_user.full_name}: {rejection_reason}",
        actor=doctor_user.full_name or doctor_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(handover)

    broadcast_emergency_event(
        "HANDOVER_REJECTED",
        case,
        extra={"handover_id": handover.id, "handover_version": handover.version},
    )
    return handover
