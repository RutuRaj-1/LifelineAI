"""Emergency Orchestration Service (Prompt 08).

Manages the active emergency lifecycle, live incident intake, location updates,
arrival coordination, and reservation consumption.

Core Principle: "Move Information Before the Patient, Not After."
"""
from datetime import datetime, timezone
import logging
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..events import hub
from ..models import (
    ActivityLog,
    EmergencyCase,
    EmergencyIncidentReport,
    HandoverAcknowledgement,
    ClinicalHandover,
    Hospital,
    HospitalResource,
    Patient,
    ReferralRequest,
    ResourceReservation,
    User,
)
from ..schemas import EmergencyIncidentReportIn, SOSInitiateIn
from . import resource_service, runner

logger = logging.getLogger("lifeline.emergency_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def broadcast_emergency_event(event_type: str, case: EmergencyCase, extra: dict | None = None) -> None:
    """Broadcast scoped emergency lifecycle events across the WebSocket event hub."""
    try:
        info = {
            "case_id": case.id,
            "patient_id": case.patient_id,
            "hospital_id": case.hospital_id,
            "doctor_id": case.doctor_id,
            "status": case.status,
            "eta_minutes": case.eta_minutes,
        }
        runner.spawn(hub.emit(event_type, info, **(extra or {})))
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to broadcast WebSocket event %s: %s", event_type, exc)


# ==============================================================================
# 1. SOS Initiation Engine
# ==============================================================================

def initiate_sos(
    db: Session,
    user: User,
    data: SOSInitiateIn,
) -> tuple[EmergencyCase, bool]:
    """
    Initiates an emergency case with strict idempotency and authorization.
    Returns: (EmergencyCase, is_created: bool)
    """
    now = utc_now()

    # 1. Idempotency Check
    if data.idempotency_key:
        existing = (
            db.query(EmergencyCase)
            .filter(EmergencyCase.idempotency_key == data.idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    # 2. Determine Patient ID
    patient_id: int | None = None
    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient profile not found for this user.")
        patient_id = patient.id
    elif user.role == "family":
        if not user.linked_patient_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Family user is not linked to any patient profile.")
        if data.patient_id and data.patient_id != user.linked_patient_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Family user can only initiate SOS for their linked patient.")
        patient_id = user.linked_patient_id
    elif user.role in ("doctor", "admin"):
        if not data.patient_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Doctor/Coordinator must specify target patient_id.")
        patient = db.get(Patient, data.patient_id)
        if not patient:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Target patient not found.")
        patient_id = patient.id
    else:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Role not authorized to initiate emergency.")

    # 3. Prevent duplicate simultaneous active emergencies for same patient
    active_case = (
        db.query(EmergencyCase)
        .filter(
            EmergencyCase.patient_id == patient_id,
            EmergencyCase.status.notin_(["COMPLETED", "CLOSED", "CANCELLED"]),
        )
        .first()
    )
    if active_case:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"An active emergency (Case #{active_case.id}) is already in progress for this patient.",
        )

    # 4. Create EmergencyCase
    case = EmergencyCase(
        patient_id=patient_id,
        emergency_type=data.emergency_type,
        symptoms=data.symptoms,
        lat=data.lat,
        lng=data.lng,
        current_lat=data.lat,
        current_lng=data.lng,
        status="CREATED",
        origin_type=data.origin_type,
        location_source=data.location_source or "DEVICE_GPS",
        location_accuracy_meters=data.location_accuracy_meters,
        idempotency_key=data.idempotency_key,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.flush()

    # 5. Log activity
    log = ActivityLog(
        case_id=case.id,
        event="EMERGENCY_INITIATED",
        detail=f"Emergency SOS initiated for {data.emergency_type} via {data.origin_type}.",
        actor=user.full_name or user.email,
        created_at=now,
    )
    db.add(log)

    # 6. If initial symptoms or text provided, create initial incident report
    if data.symptoms:
        rep = EmergencyIncidentReport(
            emergency_case_id=case.id,
            reporter_user_id=user.id,
            reporter_type=user.role.upper(),
            reporter_role=user.role,
            report_type="TEXT",
            reported_text=data.symptoms,
            observed_at=now,
            received_at=now,
            location_latitude=data.lat,
            location_longitude=data.lng,
            location_accuracy_meters=data.location_accuracy_meters,
            verification_status="UNVERIFIED",
            created_at=now,
        )
        db.add(rep)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if data.idempotency_key:
            existing = (
                db.query(EmergencyCase)
                .filter(EmergencyCase.idempotency_key == data.idempotency_key)
                .first()
            )
            if existing:
                return existing, False
        raise HTTPException(status.HTTP_409_CONFLICT, "Conflict creating emergency case.") from exc

    db.refresh(case)

    # Trigger background pipeline runner
    runner.start_case(case.id)

    broadcast_emergency_event("EMERGENCY_INITIATED", case)
    return case, True


# ==============================================================================
# 2. Live Incident Intake Engine
# ==============================================================================

def submit_incident_report(
    db: Session,
    case_id: int,
    user: User,
    data: EmergencyIncidentReportIn,
) -> tuple[EmergencyIncidentReport, bool]:
    """
    Submits an evidence-preserved incident report (patient, witness, family, doctor).
    Returns: (EmergencyIncidentReport, is_created: bool)
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if case.status in ("COMPLETED", "CLOSED", "CANCELLED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot submit incident reports for emergency in terminal state: {case.status}.",
        )

    # 1. Idempotency Check
    if data.idempotency_key:
        existing = (
            db.query(EmergencyIncidentReport)
            .filter(EmergencyIncidentReport.idempotency_key == data.idempotency_key)
            .first()
        )
        if existing:
            return existing, False

    # 2. Parent report validation for corrections/amendments
    if data.parent_report_id:
        parent = db.get(EmergencyIncidentReport, data.parent_report_id)
        if not parent or parent.emergency_case_id != case.id:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Parent incident report not found for correction.",
            )

    now = utc_now()
    # Clinician confirmations are recorded only when doctor/admin submits
    verification_status = "CLINICIAN_CONFIRMED" if user.role in ("doctor", "admin") else "UNVERIFIED"

    rep = EmergencyIncidentReport(
        emergency_case_id=case.id,
        reporter_user_id=user.id,
        reporter_type=data.reporter_type.upper(),
        reporter_role=user.role,
        report_type=data.report_type.upper(),
        reported_text=data.reported_text.strip(),
        observed_at=data.observed_at or now,
        received_at=now,
        location_latitude=data.location_latitude,
        location_longitude=data.location_longitude,
        location_accuracy_meters=data.location_accuracy_meters,
        audio_storage_url=data.audio_storage_url,
        transcription_status=data.transcription_status or "NONE",
        verification_status=verification_status,
        parent_report_id=data.parent_report_id,
        idempotency_key=data.idempotency_key,
        created_at=now,
    )
    db.add(rep)

    # Activity log
    log = ActivityLog(
        case_id=case.id,
        event="INCIDENT_REPORT_RECEIVED",
        detail=f"{data.reporter_type} reported {data.report_type}: '{data.reported_text[:60]}...'",
        actor=user.full_name or user.email,
        created_at=now,
    )
    db.add(log)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if data.idempotency_key:
            existing = (
                db.query(EmergencyIncidentReport)
                .filter(EmergencyIncidentReport.idempotency_key == data.idempotency_key)
                .first()
            )
            if existing:
                return existing, False
        raise HTTPException(status.HTTP_409_CONFLICT, "Conflict saving incident report.") from exc

    db.refresh(rep)

    broadcast_emergency_event(
        "INCIDENT_REPORT_RECEIVED",
        case,
        extra={"incident_report_id": rep.id, "reporter_type": rep.reporter_type},
    )
    return rep, True


# ==============================================================================
# 3. Location & Status Updates
# ==============================================================================

def update_emergency_location(
    db: Session,
    case_id: int,
    user: User,
    lat: float,
    lng: float,
    location_source: str = "DEVICE_GPS",
    accuracy_meters: float | None = None,
) -> EmergencyCase:
    """Updates live emergency location coordinates."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    now = utc_now()
    case.current_lat = lat
    case.current_lng = lng
    case.location_source = location_source
    case.location_accuracy_meters = accuracy_meters
    case.updated_at = now

    log = ActivityLog(
        case_id=case.id,
        event="INCIDENT_LOCATION_UPDATED",
        detail=f"Location updated to ({lat:.5f}, {lng:.5f}) via {location_source}.",
        actor=user.full_name or user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(case)

    broadcast_emergency_event("INCIDENT_LOCATION_UPDATED", case)
    return case


def transition_status(
    db: Session,
    case_id: int,
    user: User,
    new_status: str,
    reason: str | None = None,
) -> EmergencyCase:
    """Enforces valid status transitions on the EmergencyCase."""
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    now = utc_now()
    old_status = case.status
    case.status = new_status
    case.updated_at = now

    if new_status in ("COMPLETED", "CLOSED"):
        case.completed_at = now
        case.case_closed_at = now
    elif new_status == "ARRIVED":
        case.arrived_at = now
        case.handover_status = "ARRIVED"

    log = ActivityLog(
        case_id=case.id,
        event="EMERGENCY_STATUS_UPDATED",
        detail=f"Status transitioned from {old_status} to {new_status}. {reason or ''}".strip(),
        actor=user.full_name or user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(case)

    broadcast_emergency_event("EMERGENCY_STATUS_UPDATED", case, extra={"previous_status": old_status})
    return case


# ==============================================================================
# 4. Receiving-Hospital Arrival & Reservation Consumption
# ==============================================================================

def record_patient_arrival(
    db: Session,
    case_id: int,
    hospital_user: User,
    remarks: str | None = None,
) -> EmergencyCase:
    """
    Explicit, authorized receiving-hospital patient arrival:
    - Enforces hospital authorization (user belongs to accepting hospital).
    - Consumes the confirmed ResourceReservation exactly once via resource_service.
    - Idempotent: repeated calls do not double-increment occupancy or double-consume hold.
    - Transitions case status to ARRIVED.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if not hospital_user.hospital_id or case.hospital_id != hospital_user.hospital_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied: Only staff of the accepted receiving hospital can confirm patient arrival.",
        )

    # Idempotent return if already arrived
    if case.status == "ARRIVED" and case.arrived_at is not None:
        return case

    # Find the accepted referral request for this hospital
    accepted_ref = (
        db.query(ReferralRequest)
        .filter(
            ReferralRequest.emergency_case_id == case.id,
            ReferralRequest.hospital_id == hospital_user.hospital_id,
            ReferralRequest.status == "ACCEPTED",
        )
        .first()
    )
    if not accepted_ref:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot confirm arrival: No active accepted referral request found for this hospital.",
        )

    # Locate and consume reservation hold
    reservation = (
        db.query(ResourceReservation)
        .filter(
            ResourceReservation.referral_request_id == accepted_ref.id,
            ResourceReservation.reservation_status.in_(["HELD", "CONFIRMED"]),
        )
        .first()
    )
    if reservation:
        resource_service.consume_reservation(db, reservation.id, user_id=hospital_user.id)

    now = utc_now()
    case.status = "ARRIVED"
    case.arrived_at = now
    case.handover_status = "ARRIVED"
    case.updated_at = now

    log = ActivityLog(
        case_id=case.id,
        event="PATIENT_ARRIVED",
        detail=f"Patient physically arrived at {hospital_user.hospital_id}. Resource reservation consumed. {remarks or ''}".strip(),
        actor=hospital_user.full_name or hospital_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(case)

    broadcast_emergency_event("PATIENT_ARRIVED", case)
    return case


# ==============================================================================
# 5. Receiving-Hospital Handover Acknowledgement
# ==============================================================================

def acknowledge_handover(
    db: Session,
    case_id: int,
    hospital_user: User,
    handover_id: int,
    operational_remarks: str | None = None,
) -> HandoverAcknowledgement:
    """
    Authoritative receiving-hospital acknowledgement of an approved clinical handover.
    Distinguishes prepared -> approved -> shared -> acknowledged.
    """
    case = db.get(EmergencyCase, case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if not hospital_user.hospital_id or case.hospital_id != hospital_user.hospital_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied: Only staff of the accepted receiving hospital can acknowledge handovers.",
        )

    handover = db.get(ClinicalHandover, handover_id)
    if not handover or handover.emergency_case_id != case.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clinical handover not found for this emergency case.")

    if handover.status != "APPROVED":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot acknowledge handover in non-approved status: {handover.status}.",
        )

    now = utc_now()
    ack = HandoverAcknowledgement(
        emergency_case_id=case.id,
        hospital_id=hospital_user.hospital_id,
        handover_id=handover.id,
        acknowledged_by_user_id=hospital_user.id,
        acknowledged_at=now,
        status="ACKNOWLEDGED",
        operational_remarks=operational_remarks,
    )
    db.add(ack)

    case.handover_status = "HANDOVER_COMPLETE"
    case.handover_signed_by = hospital_user.full_name or hospital_user.email
    case.updated_at = now

    log = ActivityLog(
        case_id=case.id,
        event="HANDOVER_ACKNOWLEDGED",
        detail=f"Clinical handover v{handover.version} acknowledged by {hospital_user.full_name}. {operational_remarks or ''}".strip(),
        actor=hospital_user.full_name or hospital_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(ack)

    broadcast_emergency_event(
        "HANDOVER_ACKNOWLEDGED",
        case,
        extra={"handover_id": handover.id, "handover_version": handover.version},
    )
    return ack
