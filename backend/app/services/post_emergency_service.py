"""Post-Emergency Continuity, Outcomes, Discharges & Longitudinal Follow-Up Service (Prompt 10).

Core Healthcare Principle:
- Move Information Before the Patient, Not After.
- Clinical Safety: AI never diagnoses, prescribes, or independently changes medications.
- All discharge summaries, medication reconciliations, and follow-up plans require explicit,
  auditable clinician verification.
- Distinguishes emergency closure, inpatient admission, facility transfer, and outpatient discharge.
"""
from datetime import datetime, timezone
import logging
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..events import hub
from ..models import (
    ActivityLog,
    ClinicalProvenance,
    DischargeSummary,
    EmergencyCase,
    EmergencyIncidentReport,
    EmergencyOutcome,
    FollowUpPlan,
    Hospital,
    HospitalDepartment,
    MedicalReport,
    MedicationReconciliation,
    Patient,
    PatientClinicalFact,
    User,
)
from ..schemas import (
    DischargeSummaryApproveIn,
    DischargeSummaryGenerateIn,
    DischargeSummaryRejectIn,
    EmergencyOutcomeAmend,
    EmergencyOutcomeCreate,
    FollowUpPlanCreate,
    FollowUpPlanUpdateIn,
    MedicationReconciliationCreate,
    MedicationReconciliationVerifyIn,
)
from . import runner

logger = logging.getLogger("lifeline.post_emergency_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def broadcast_post_emergency_event(event_type: str, case: EmergencyCase, extra: dict | None = None) -> None:
    """Broadcast scoped post-emergency lifecycle events across the WebSocket event hub."""
    try:
        info = {
            "case_id": case.id,
            "patient_id": case.patient_id,
            "hospital_id": case.hospital_id,
            "doctor_id": case.doctor_id,
            "status": case.status,
        }
        runner.spawn(hub.emit(event_type, info, **(extra or {})))
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to broadcast WebSocket event %s: %s", event_type, exc)


NON_DIAGNOSTIC_DISCHARGE_DISCLAIMER = (
    "EVIDENCE-GROUNDED POST-EMERGENCY CLINICAL CONTINUITY RECORD. "
    "This summary synthesizes authorized treating hospital records, field reports, and documented physician instructions. "
    "It does NOT contain autonomous AI diagnoses, automated prescription changes, or unverified claims. "
    "All medical instructions and medication changes remain the explicit responsibility of the authorized treating physician."
)


# ==============================================================================
# 1. Emergency Outcome Recording & Amendment
# ==============================================================================

def record_emergency_outcome(
    db: Session,
    case_id: int,
    user: User,
    data: EmergencyOutcomeCreate,
) -> EmergencyOutcome:
    """
    Records the clinical and operational disposition of an emergency episode.
    Distinguishes:
    - DISCHARGED: Outpatient release from emergency/hospital care.
    - ADMITTED: Continued inpatient care at the receiving facility.
    - TRANSFERRED: Transferred to another specialized institution.
    - OTHER: Explicitly documented disposition.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    # Authorization Check: Receiving hospital staff or treating doctor
    if user.role == "hospital":
        if not user.hospital_id or case.hospital_id != user.hospital_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Access denied: Only staff of the assigned receiving hospital can record outcomes.",
            )
    elif user.role == "doctor":
        # Treating doctor check
        if user.hospital_id and case.hospital_id and user.hospital_id != case.hospital_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Doctor not affiliated with receiving hospital.")
    elif user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Insufficient privileges to record emergency outcome.")

    # Enforce that existing approved outcome requires formal amendment
    existing = (
        db.query(EmergencyOutcome)
        .filter(
            EmergencyOutcome.emergency_case_id == case.id,
            EmergencyOutcome.verification_status.in_(["CLINICIAN_VERIFIED", "REVIEWED"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"An active verified outcome already exists (version {existing.version}). Use the outcome amendment workflow to update.",
        )

    now = utc_now()
    outcome_dt = data.outcome_at or now

    # Determine verification status
    is_clinician = user.role in ("doctor", "admin")
    verification_status = "CLINICIAN_VERIFIED" if is_clinician else "REVIEWED"

    outcome = EmergencyOutcome(
        emergency_case_id=case.id,
        patient_id=case.patient_id,
        hospital_id=case.hospital_id or user.hospital_id or 1,
        disposition=data.disposition,
        disposition_notes=data.disposition_notes,
        outcome_at=outcome_dt,
        verification_status=verification_status,
        recorded_by_user_id=user.id,
        verified_by_user_id=user.id if is_clinician else None,
        verified_at=now if is_clinician else None,
        version=1,
    )
    db.add(outcome)

    # Lifecycle state transition
    if data.disposition == "DISCHARGED":
        case.status = "COMPLETED"
        case.completed_at = now
    elif data.disposition == "ADMITTED":
        # Patient is admitted into continuing inpatient care; case is closed from emergency perspective
        case.status = "COMPLETED"
        case.completed_at = now
    elif data.disposition == "TRANSFERRED":
        case.status = "COMPLETED"
        case.completed_at = now

    case.updated_at = now

    log = ActivityLog(
        case_id=case.id,
        event="EMERGENCY_OUTCOME_RECORDED",
        detail=f"Outcome disposition '{data.disposition}' recorded by {user.full_name}. Notes: {data.disposition_notes or 'None'}",
        actor=user.full_name or user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(outcome)

    broadcast_post_emergency_event(
        "EMERGENCY_OUTCOME_RECORDED",
        case,
        extra={"disposition": outcome.disposition, "outcome_id": outcome.id},
    )
    return outcome


def amend_emergency_outcome(
    db: Session,
    case_id: int,
    user: User,
    data: EmergencyOutcomeAmend,
) -> EmergencyOutcome:
    """
    Creates an auditable amended outcome version, preserving the prior record.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    # Authorization Check
    if user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Unauthorized hospital.")
    if user.role not in ("hospital", "doctor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Cannot amend outcomes.")

    latest = (
        db.query(EmergencyOutcome)
        .filter(EmergencyOutcome.emergency_case_id == case.id)
        .order_by(EmergencyOutcome.version.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No prior outcome record found to amend.")

    now = utc_now()
    is_clinician = user.role in ("doctor", "admin")

    # Mark prior outcome as SUPERSEDED or AMENDED
    latest.verification_status = "SUPERSEDED"
    latest.updated_at = now

    new_outcome = EmergencyOutcome(
        emergency_case_id=case.id,
        patient_id=case.patient_id,
        hospital_id=case.hospital_id or user.hospital_id or 1,
        disposition=data.disposition,
        disposition_notes=data.disposition_notes,
        outcome_at=now,
        verification_status="CLINICIAN_VERIFIED" if is_clinician else "REVIEWED",
        recorded_by_user_id=user.id,
        verified_by_user_id=user.id if is_clinician else None,
        verified_at=now if is_clinician else None,
        version=latest.version + 1,
        parent_outcome_id=latest.id,
        amendment_reason=data.amendment_reason,
    )
    db.add(new_outcome)

    log = ActivityLog(
        case_id=case.id,
        event="EMERGENCY_OUTCOME_AMENDED",
        detail=f"Outcome amended to '{data.disposition}' (v{new_outcome.version}) by {user.full_name}. Reason: {data.amendment_reason}",
        actor=user.full_name or user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(new_outcome)

    broadcast_post_emergency_event(
        "EMERGENCY_OUTCOME_AMENDED",
        case,
        extra={"disposition": new_outcome.disposition, "version": new_outcome.version},
    )
    return new_outcome


def get_emergency_outcome(db: Session, case_id: int) -> EmergencyOutcome | None:
    """Returns the latest active outcome for an emergency case."""
    return (
        db.query(EmergencyOutcome)
        .filter(EmergencyOutcome.emergency_case_id == case_id)
        .order_by(EmergencyOutcome.version.desc())
        .first()
    )


# ==============================================================================
# 2. Discharge Documentation & Summary Synthesis
# ==============================================================================

def generate_discharge_summary_draft(
    db: Session,
    case_id: int,
    user: User,
    data: DischargeSummaryGenerateIn,
    source_report_id: int | None = None,
) -> DischargeSummary:
    """
    Synthesizes a structured, evidence-grounded discharge summary draft:
    - Incorporates documented primary diagnosis, clinical course, procedures, and precautions.
    - Explicitly surfaces missing data warnings.
    - Marks status as DRAFT / PENDING_REVIEW awaiting physician approval.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if user.role == "hospital" and user.hospital_id != case.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Unauthorized hospital.")
    if user.role not in ("hospital", "doctor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Insufficient privileges.")

    # Gather historical facts and incident data
    facts = (
        db.query(PatientClinicalFact)
        .filter(PatientClinicalFact.patient_id == case.patient_id)
        .all()
    )
    allergies = [f.fact_value for f in facts if f.fact_type == "ALLERGY" and f.clinical_status == "ACTIVE"]
    conditions = [f.fact_value for f in facts if f.fact_type == "CONDITION" and f.clinical_status == "ACTIVE"]
    medications = [f.fact_value for f in facts if f.fact_type == "MEDICATION" and f.clinical_status == "ACTIVE"]

    # Incompleteness / Missing data warnings
    missing_warnings = []
    if not allergies:
        missing_warnings.append("No drug allergies documented on record (does NOT confirm absence of allergies).")
    if not conditions:
        missing_warnings.append("No chronic conditions documented on baseline profile.")
    if not medications:
        missing_warnings.append("Medication reconciliation pending; no active baseline prescriptions on record.")

    # Determine latest version
    latest = (
        db.query(DischargeSummary)
        .filter(DischargeSummary.emergency_case_id == case.id)
        .order_by(DischargeSummary.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    now = utc_now()
    summary_data = {
        "encounter_type": case.emergency_type,
        "arrived_at": case.arrived_at.isoformat() if case.arrived_at else None,
        "completed_at": case.completed_at.isoformat() if case.completed_at else now.isoformat(),
        "baseline_allergies": allergies,
        "baseline_conditions": conditions,
        "baseline_medications": medications,
        "missing_data_warnings": missing_warnings,
        "disclaimer": NON_DIAGNOSTIC_DISCHARGE_DISCLAIMER,
        "notes": data.notes,
    }

    admission_dt = case.arrived_at.date().isoformat() if case.arrived_at else case.created_at.date().isoformat()
    discharge_dt = now.date().isoformat()

    summary = DischargeSummary(
        emergency_case_id=case.id,
        patient_id=case.patient_id,
        hospital_id=case.hospital_id or user.hospital_id or 1,
        source_report_id=source_report_id,
        version=next_version,
        status="PENDING_REVIEW",
        admission_date=admission_dt,
        discharge_date=discharge_dt,
        primary_diagnosis=data.primary_diagnosis or f"Managed acute {case.emergency_type} episode",
        secondary_diagnoses=data.secondary_diagnoses or [],
        procedures_performed=data.procedures_performed or [],
        clinical_course=data.clinical_course or "Evaluated and treated in emergency department.",
        discharge_condition=data.discharge_condition,
        precautions=data.precautions or [],
        summary_data=summary_data,
        author_user_id=user.id,
        parent_summary_id=latest.id if latest else None,
        is_current_approved=False,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)

    broadcast_post_emergency_event(
        "DISCHARGE_SUMMARY_GENERATED",
        case,
        extra={"summary_id": summary.id, "version": summary.version},
    )
    return summary


def approve_discharge_summary(
    db: Session,
    case_id: int,
    summary_id: int,
    doctor_user: User,
    data: DischargeSummaryApproveIn,
) -> DischargeSummary:
    """
    Authoritative clinician approval of a discharge summary.
    Enforces physician review gate and promotes documented diagnoses to PatientClinicalFact.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if doctor_user.role not in ("doctor", "admin"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied: Only licensed physicians may clinically approve discharge summaries.",
        )

    summary = db.get(DischargeSummary, summary_id)
    if not summary or summary.emergency_case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discharge summary not found for this case.")

    if summary.status == "APPROVED":
        return summary  # Idempotent return

    now = utc_now()

    # Supersede any prior approved summary for this case
    prior_approved = (
        db.query(DischargeSummary)
        .filter(
            DischargeSummary.emergency_case_id == case.id,
            DischargeSummary.is_current_approved == True,
            DischargeSummary.id != summary.id,
        )
        .all()
    )
    for p in prior_approved:
        p.is_current_approved = False
        p.status = "SUPERSEDED"

    summary.status = "APPROVED"
    summary.is_current_approved = True
    summary.approved_by_user_id = doctor_user.id
    summary.approved_at = now
    summary.approval_notes = data.approval_notes
    summary.updated_at = now

    # Promote approved primary diagnosis to longitudinal PatientClinicalFact
    if summary.primary_diagnosis:
        # Check if already present to avoid duplicates
        existing_fact = (
            db.query(PatientClinicalFact)
            .filter(
                PatientClinicalFact.patient_id == case.patient_id,
                PatientClinicalFact.fact_type == "CONDITION",
                PatientClinicalFact.fact_value == summary.primary_diagnosis,
            )
            .first()
        )
        if not existing_fact:
            fact = PatientClinicalFact(
                patient_id=case.patient_id,
                fact_type="CONDITION",
                fact_value=summary.primary_diagnosis,
                clinical_status="ACTIVE",
                effective_from=summary.discharge_date or now.date().isoformat(),
            )
            db.add(fact)
            db.flush()

            prov = ClinicalProvenance(
                clinical_fact_id=fact.id,
                source_type="HOSPITAL_IMPORTED",
                source_report_id=summary.source_report_id,
                source_user_id=doctor_user.id,
                source_reference=f"Discharge Summary #{summary.id} (Case #{case.id})",
                source_excerpt=f"Primary Diagnosis on discharge: {summary.primary_diagnosis}",
                verification_status="VERIFIED",
                verified_by_user_id=doctor_user.id,
                verified_at=now,
                verification_notes=f"Approved by Dr. {doctor_user.full_name}",
            )
            db.add(prov)

    log = ActivityLog(
        case_id=case.id,
        event="DISCHARGE_SUMMARY_APPROVED",
        detail=f"Discharge summary v{summary.version} approved by Dr. {doctor_user.full_name}. {data.approval_notes or ''}".strip(),
        actor=doctor_user.full_name or doctor_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(summary)

    broadcast_post_emergency_event(
        "DISCHARGE_SUMMARY_APPROVED",
        case,
        extra={"summary_id": summary.id, "version": summary.version},
    )
    return summary


def reject_discharge_summary(
    db: Session,
    case_id: int,
    summary_id: int,
    doctor_user: User,
    data: DischargeSummaryRejectIn,
) -> DischargeSummary:
    """Rejects a discharge summary with clinical justification."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if doctor_user.role not in ("doctor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Only physicians may reject discharge summaries.")

    summary = db.get(DischargeSummary, summary_id)
    if not summary or summary.emergency_case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Discharge summary not found for this case.")

    now = utc_now()
    summary.status = "REJECTED"
    summary.rejection_reason = data.rejection_reason
    summary.is_current_approved = False
    summary.updated_at = now

    log = ActivityLog(
        case_id=case.id,
        event="DISCHARGE_SUMMARY_REJECTED",
        detail=f"Discharge summary v{summary.version} rejected by Dr. {doctor_user.full_name}. Reason: {data.rejection_reason}",
        actor=doctor_user.full_name or doctor_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(summary)
    return summary


def get_latest_discharge_summary(db: Session, case_id: int) -> DischargeSummary | None:
    """Returns the current approved discharge summary or latest version."""
    approved = (
        db.query(DischargeSummary)
        .filter(DischargeSummary.emergency_case_id == case_id, DischargeSummary.is_current_approved == True)
        .first()
    )
    if approved:
        return approved
    return (
        db.query(DischargeSummary)
        .filter(DischargeSummary.emergency_case_id == case_id)
        .order_by(DischargeSummary.version.desc())
        .first()
    )


# ==============================================================================
# 3. Medication Reconciliation
# ==============================================================================

def create_medication_reconciliation_entry(
    db: Session,
    case_id: int,
    user: User,
    data: MedicationReconciliationCreate,
) -> MedicationReconciliation:
    """
    Records a structured medication reconciliation entry.
    Statuses: CONTINUE, START, STOP, CHANGE, NOT_RECONCILED.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if user.role not in ("hospital", "doctor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Insufficient privileges.")

    # Find latest approved or draft discharge summary if available
    summary = get_latest_discharge_summary(db, case.id)

    is_clinician = user.role in ("doctor", "admin")
    now = utc_now()

    entry = MedicationReconciliation(
        emergency_case_id=case.id,
        patient_id=case.patient_id,
        hospital_id=case.hospital_id or user.hospital_id or 1,
        discharge_summary_id=summary.id if summary else None,
        medication_name=data.medication_name.strip(),
        dosage=data.dosage.strip() if data.dosage else None,
        route=data.route,
        frequency=data.frequency,
        reconciliation_status=data.reconciliation_status,
        source_type=data.source_type,
        clinical_reason=data.clinical_reason,
        verification_status="CLINICIAN_VERIFIED" if is_clinician else "UNVERIFIED",
        verified_by_user_id=user.id if is_clinician else None,
        verified_at=now if is_clinician else None,
    )
    db.add(entry)
    db.flush()

    # If verified by clinician directly on entry, execute clinical fact promotion
    if is_clinician:
        _promote_reconciled_medication(db, entry, user, now)

    db.commit()
    db.refresh(entry)

    broadcast_post_emergency_event(
        "MEDICATION_RECONCILIATION_UPDATED",
        case,
        extra={"entry_id": entry.id, "medication": entry.medication_name, "status": entry.reconciliation_status},
    )
    return entry


def verify_medication_reconciliation_entry(
    db: Session,
    case_id: int,
    entry_id: int,
    doctor_user: User,
    data: MedicationReconciliationVerifyIn,
) -> MedicationReconciliation:
    """
    Clinician verification gate for medication reconciliation entries.
    Promotes START/CONTINUE to PatientClinicalFact and deactivates STOP medications.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if doctor_user.role not in ("doctor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Only clinicians can verify medication reconciliation.")

    entry = db.get(MedicationReconciliation, entry_id)
    if not entry or entry.emergency_case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medication reconciliation record not found.")

    now = utc_now()
    entry.verification_status = data.verification_status
    entry.verified_by_user_id = doctor_user.id
    entry.verified_at = now
    if data.clinical_reason:
        entry.clinical_reason = data.clinical_reason
    entry.updated_at = now

    if data.verification_status == "VERIFIED":
        _promote_reconciled_medication(db, entry, doctor_user, now)

    db.commit()
    db.refresh(entry)

    broadcast_post_emergency_event(
        "MEDICATION_RECONCILIATION_UPDATED",
        case,
        extra={"entry_id": entry.id, "verified": True},
    )
    return entry


def _promote_reconciled_medication(
    db: Session,
    entry: MedicationReconciliation,
    user: User,
    now: datetime,
) -> None:
    """Helper promoting or resolving longitudinal PatientClinicalFact based on reconciliation."""
    med_display = f"{entry.medication_name} {entry.dosage or ''}".strip()

    if entry.reconciliation_status in ("START", "CONTINUE", "CHANGE"):
        existing = (
            db.query(PatientClinicalFact)
            .filter(
                PatientClinicalFact.patient_id == entry.patient_id,
                PatientClinicalFact.fact_type == "MEDICATION",
                PatientClinicalFact.fact_value.ilike(f"%{entry.medication_name}%"),
            )
            .first()
        )
        if existing:
            existing.fact_value = med_display
            existing.clinical_status = "ACTIVE"
            existing.updated_at = now
            entry.promoted_fact_id = existing.id
        else:
            fact = PatientClinicalFact(
                patient_id=entry.patient_id,
                fact_type="MEDICATION",
                fact_value=med_display,
                clinical_status="ACTIVE",
                effective_from=now.date().isoformat(),
            )
            db.add(fact)
            db.flush()
            entry.promoted_fact_id = fact.id

            prov = ClinicalProvenance(
                clinical_fact_id=fact.id,
                source_type="DOCTOR_VERIFIED",
                source_user_id=user.id,
                source_reference=f"Emergency Medication Reconciliation (Case #{entry.emergency_case_id})",
                source_excerpt=f"{entry.reconciliation_status}: {med_display} ({entry.frequency or 'daily'})",
                verification_status="VERIFIED",
                verified_by_user_id=user.id,
                verified_at=now,
                verification_notes=entry.clinical_reason or f"Clinician reconciled: {entry.reconciliation_status}",
            )
            db.add(prov)

    elif entry.reconciliation_status == "STOP":
        # Deactivate previous active medication fact
        prior_facts = (
            db.query(PatientClinicalFact)
            .filter(
                PatientClinicalFact.patient_id == entry.patient_id,
                PatientClinicalFact.fact_type == "MEDICATION",
                PatientClinicalFact.clinical_status == "ACTIVE",
                PatientClinicalFact.fact_value.ilike(f"%{entry.medication_name}%"),
            )
            .all()
        )
        for pf in prior_facts:
            pf.clinical_status = "RESOLVED"
            pf.updated_at = now
            prov = ClinicalProvenance(
                clinical_fact_id=pf.id,
                source_type="DOCTOR_VERIFIED",
                source_user_id=user.id,
                source_reference=f"Discharge Medication Discontinuation (Case #{entry.emergency_case_id})",
                source_excerpt=f"Discontinued: {entry.medication_name}. Reason: {entry.clinical_reason or 'Clinician stopped'}",
                verification_status="VERIFIED",
                verified_by_user_id=user.id,
                verified_at=now,
                verification_notes=entry.clinical_reason or "Stopped on emergency discharge.",
            )
            db.add(prov)


def list_medication_reconciliations(db: Session, case_id: int) -> list[MedicationReconciliation]:
    """Returns all medication reconciliation items for an emergency case."""
    return (
        db.query(MedicationReconciliation)
        .filter(MedicationReconciliation.emergency_case_id == case_id)
        .order_by(MedicationReconciliation.created_at.asc())
        .all()
    )


# ==============================================================================
# 4. Longitudinal Follow-Up Plans
# ==============================================================================

def create_follow_up_plan(
    db: Session,
    case_id: int,
    user: User,
    data: FollowUpPlanCreate,
) -> FollowUpPlan:
    """
    Creates an explicit documented follow-up instruction.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if user.role not in ("hospital", "doctor", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Insufficient privileges.")

    summary = get_latest_discharge_summary(db, case.id)
    is_clinician = user.role in ("doctor", "admin")
    now = utc_now()

    plan = FollowUpPlan(
        emergency_case_id=case.id,
        patient_id=case.patient_id,
        hospital_id=case.hospital_id or user.hospital_id or 1,
        discharge_summary_id=summary.id if summary else None,
        department_id=data.department_id,
        specialty=data.specialty.strip(),
        scheduled_date=data.scheduled_date,
        instructions=data.instructions.strip(),
        status="PLANNED",
        created_by_user_id=user.id,
        verified_by_user_id=user.id if is_clinician else None,
        verified_at=now if is_clinician else None,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    broadcast_post_emergency_event(
        "FOLLOW_UP_PLAN_CREATED",
        case,
        extra={"plan_id": plan.id, "specialty": plan.specialty},
    )
    return plan


def update_follow_up_plan(
    db: Session,
    plan_id: int,
    user: User,
    data: FollowUpPlanUpdateIn,
) -> FollowUpPlan:
    """
    Updates the lifecycle status of a follow-up plan (e.g. SCHEDULED, COMPLETED, CANCELLED).
    """
    plan = db.get(FollowUpPlan, plan_id)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Follow-up plan not found.")

    # Authorization: Patient can mark scheduled or view; Clinician / Hospital can complete/cancel
    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or patient.id != plan.patient_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Not your follow-up record.")
    elif user.role == "hospital" and user.hospital_id != plan.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Hospital mismatch.")

    now = utc_now()
    plan.status = data.status
    if data.completion_notes:
        plan.completion_notes = data.completion_notes
    if data.scheduled_date:
        plan.scheduled_date = data.scheduled_date
    if data.status == "COMPLETED":
        plan.completed_at = now
    plan.updated_at = now

    db.commit()
    db.refresh(plan)
    return plan


# Exported aliases for router convenience
record_outcome = record_emergency_outcome
amend_outcome = amend_emergency_outcome


def list_follow_up_plans(db: Session, case_id: int) -> list[FollowUpPlan]:
    """Returns all follow-up plans for an emergency case."""
    return (
        db.query(FollowUpPlan)
        .filter(FollowUpPlan.emergency_case_id == case_id)
        .order_by(FollowUpPlan.created_at.asc())
        .all()
    )
