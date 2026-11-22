from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    ActivityLog,
    ClinicalHandover,
    EmergencyCase,
    EmergencyIncidentReport,
    HandoverAcknowledgement,
    Patient,
    User,
)
from ..schemas import (
    ClinicalHandoverApproveIn,
    ClinicalHandoverGenerateIn,
    ClinicalHandoverOut,
    ClinicalHandoverRejectIn,
    EmergencyArrivalIn,
    EmergencyIncidentReportIn,
    EmergencyIncidentReportOut,
    EmergencyIn,
    EmergencyLocationUpdateIn,
    EmergencyStatusUpdateIn,
    HandoverAcknowledgeIn,
    HandoverAcknowledgementOut,
    LocationIn,
    SOSInitiateIn,
)
from ..security import can_access_patient, current_user, require_roles
from ..services import emergency_service, handover_service, ops
from ..services.runner import start_case
from ..services.serialize import (
    case_dict,
    clinical_handover_dict,
    handover_acknowledgement_dict,
    incident_report_dict,
)

router = APIRouter(prefix="/emergency", tags=["Emergency"])


def _own_patient(db: Session, user: User) -> Patient:
    p = db.query(Patient).filter(Patient.user_id == user.id).first()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient profile not found")
    return p


# ==============================================================================
# 1. SOS Initiation
# ==============================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
def create_emergency(
    body: SOSInitiateIn | EmergencyIn,
    user: User = Depends(require_roles("patient", "family", "doctor", "admin")),
    db: Session = Depends(get_db),
):
    """
    Standard emergency initiation endpoint.
    Supports patient SOS, family-assisted SOS, or doctor/coordinator initiation.
    """
    # Normalize input
    if isinstance(body, EmergencyIn):
        sos_in = SOSInitiateIn(
            emergency_type=body.emergency_type,
            symptoms=body.symptoms,
            lat=body.lat,
            lng=body.lng,
            origin_type="PATIENT_SOS",
        )
    else:
        sos_in = body

    case, _ = emergency_service.initiate_sos(db, user, sos_in)
    return case_dict(case, user.role, detail=True)


@router.post("/sos", status_code=status.HTTP_201_CREATED)
def trigger_sos(
    body: SOSInitiateIn,
    user: User = Depends(require_roles("patient", "family", "doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Explicit SOS trigger with idempotency key and location context."""
    case, _ = emergency_service.initiate_sos(db, user, body)
    return case_dict(case, user.role, detail=True)


@router.get("/active")
def my_active_emergency(
    user: User = Depends(require_roles("patient", "family")),
    db: Session = Depends(get_db),
):
    patient_id = _own_patient(db, user).id if user.role == "patient" else user.linked_patient_id
    if not patient_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No linked patient")
    c = ops.active_case(db, patient_id)
    return case_dict(c, user.role, detail=True) if c else None


@router.get("/{case_id}")
def get_emergency(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found")
    if not can_access_patient(db, user, c.patient_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this emergency")
    return case_dict(c, user.role, detail=True)


@router.get("/{case_id}/timeline")
def get_timeline(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found")
    if not can_access_patient(db, user, c.patient_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view this emergency")
    rows = db.query(ActivityLog).filter(ActivityLog.case_id == case_id).order_by(ActivityLog.created_at).all()
    hide_clinical = user.role == "family"
    return [
        {
            "event": r.event,
            "detail": "Status update" if hide_clinical and ("SUMMARY" in r.event or "FACT" in r.event) else r.detail,
            "actor": r.actor,
            "at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.patch("/{case_id}/location")
@router.put("/{case_id}/location")
def update_location(
    case_id: int,
    body: EmergencyLocationUpdateIn | LocationIn,
    user: User = Depends(require_roles("patient", "doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Update live location ping."""
    source = getattr(body, "location_source", "DEVICE_GPS")
    accuracy = getattr(body, "location_accuracy_meters", None)
    c = emergency_service.update_emergency_location(
        db, case_id, user, body.lat, body.lng, location_source=source, accuracy_meters=accuracy
    )
    return {"ok": True, "lat": c.current_lat, "lng": c.current_lng, "source": c.location_source}


@router.post("/{case_id}/status")
def update_emergency_status(
    case_id: int,
    body: EmergencyStatusUpdateIn,
    user: User = Depends(require_roles("doctor", "hospital", "admin")),
    db: Session = Depends(get_db),
):
    """Formal emergency status lifecycle transition."""
    c = emergency_service.transition_status(db, case_id, user, body.status, reason=body.reason)
    return case_dict(c, user.role, detail=True)


# ==============================================================================
# 2. Live Incident Intake
# ==============================================================================

@router.post("/{case_id}/incidents", status_code=status.HTTP_201_CREATED)
def submit_incident(
    case_id: int,
    body: EmergencyIncidentReportIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Submits an evidence-preserved incident report."""
    rep, _ = emergency_service.submit_incident_report(db, case_id, user, body)
    return incident_report_dict(rep)


@router.get("/{case_id}/incidents")
def list_incidents(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Lists all incident reports filed for this emergency case."""
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found")
    if not can_access_patient(db, user, c.patient_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view incident reports")

    reps = (
        db.query(EmergencyIncidentReport)
        .filter(EmergencyIncidentReport.emergency_case_id == case_id)
        .order_by(EmergencyIncidentReport.received_at.asc())
        .all()
    )
    return [incident_report_dict(r) for r in reps]


@router.get("/{case_id}/incidents/{incident_id}")
def get_incident(
    case_id: int,
    incident_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Retrieves an individual incident report."""
    rep = db.get(EmergencyIncidentReport, incident_id)
    if not rep or rep.emergency_case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident report not found")
    return incident_report_dict(rep)


@router.post("/{case_id}/incidents/{incident_id}/corrections", status_code=status.HTTP_201_CREATED)
def submit_incident_correction(
    case_id: int,
    incident_id: int,
    body: EmergencyIncidentReportIn,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Submits a correction/amendment linked to an earlier report without overwriting original history."""
    body.parent_report_id = incident_id
    rep, _ = emergency_service.submit_incident_report(db, case_id, user, body)
    return incident_report_dict(rep)


# ==============================================================================
# 3. Clinical Handover Engine
# ==============================================================================

@router.post("/{case_id}/handover/generate", status_code=status.HTTP_201_CREATED)
def generate_handover(
    case_id: int,
    body: ClinicalHandoverGenerateIn | None = None,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Generates an evidence-grounded clinical handover draft (PENDING_REVIEW)."""
    notes = body.notes if body else None
    handover = handover_service.generate_clinical_handover(db, case_id, generating_user=user, notes=notes)
    return clinical_handover_dict(handover, role=user.role)


@router.get("/{case_id}/handover")
def get_current_handover(
    case_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Retrieves current approved handover, or latest draft for doctors."""
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found")
    if not can_access_patient(db, user, c.patient_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to view clinical handover")

    # If case has current_handover_id, return it
    if c.current_handover_id:
        h = db.get(ClinicalHandover, c.current_handover_id)
        if h:
            return clinical_handover_dict(h, role=user.role)

    # Otherwise return latest handover for doctor/admin
    latest = (
        db.query(ClinicalHandover)
        .filter(ClinicalHandover.emergency_case_id == case_id)
        .order_by(ClinicalHandover.version.desc())
        .first()
    )
    if not latest:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No clinical handover found for this emergency case.")
    return clinical_handover_dict(latest, role=user.role)


@router.get("/{case_id}/handover/{handover_id}")
def get_handover_version(
    case_id: int,
    handover_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Retrieves a specific handover version."""
    h = db.get(ClinicalHandover, handover_id)
    if not h or h.emergency_case_id != case_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Clinical handover not found")
    return clinical_handover_dict(h, role=user.role)


@router.post("/{case_id}/handover/{handover_id}/approve")
def approve_handover(
    case_id: int,
    handover_id: int,
    body: ClinicalHandoverApproveIn | None = None,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Authorized doctor approval gate for clinical handover."""
    notes = body.approval_notes if body else None
    h = handover_service.approve_clinical_handover(db, handover_id, doctor_user=user, approval_notes=notes)
    return clinical_handover_dict(h, role=user.role)


@router.post("/{case_id}/handover/{handover_id}/reject")
def reject_handover(
    case_id: int,
    handover_id: int,
    body: ClinicalHandoverRejectIn,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Authorized doctor rejection with clinical rationale."""
    h = handover_service.reject_clinical_handover(db, handover_id, doctor_user=user, rejection_reason=body.rejection_reason)
    return clinical_handover_dict(h, role=user.role)


# ==============================================================================
# 4. Receiving-Hospital Arrival & Handover Acknowledgement
# ==============================================================================

@router.post("/{case_id}/arrival")
def record_arrival(
    case_id: int,
    body: EmergencyArrivalIn | None = None,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Receiving hospital explicitly records physical patient arrival.
    Consumes confirmed ResourceReservation exactly once.
    """
    remarks = body.remarks if body else None
    c = emergency_service.record_patient_arrival(db, case_id, hospital_user=user, remarks=remarks)
    return case_dict(c, user.role, detail=True)


@router.post("/{case_id}/handover/acknowledge", status_code=status.HTTP_201_CREATED)
def acknowledge_handover_endpoint(
    case_id: int,
    body: HandoverAcknowledgeIn,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Receiving hospital explicitly acknowledges handover receipt."""
    ack = emergency_service.acknowledge_handover(
        db, case_id, hospital_user=user, handover_id=body.handover_id, operational_remarks=body.operational_remarks
    )
    return handover_acknowledgement_dict(ack)


# ==============================================================================
# 5. Checklist & Completion (Backwards Compatible)
# ==============================================================================

@router.post("/{case_id}/checklist")
def update_checklist(
    case_id: int,
    body: dict,
    user: User = Depends(require_roles("doctor", "hospital")),
    db: Session = Depends(get_db),
):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found")
    idx = body.get("index")
    items = list(c.checklist or [])
    if idx is None or not (0 <= idx < len(items)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid checklist index")
    items[idx] = {**items[idx], "done": bool(body.get("done", True))}
    c.checklist = items
    ops.log_event(
        db,
        case_id,
        "CHECKLIST_UPDATED",
        f"'{items[idx]['item']}' marked {'done' if items[idx]['done'] else 'pending'}",
        user.role,
    )
    db.commit()
    return {"checklist": c.checklist}


@router.post("/{case_id}/complete")
def complete_case(
    case_id: int,
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    c = db.get(EmergencyCase, case_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found")
    c.status = "COMPLETED"
    c.completed_at = datetime.now(timezone.utc)
    c.case_closed_at = datetime.now(timezone.utc)
    if c.doctor:
        c.doctor.is_available = True
    ops.release_resources(db, c)
    ops.log_event(db, case_id, "COMPLETED", "Case closed", user.role)
    db.commit()
    return case_dict(c, user.role, detail=True)
