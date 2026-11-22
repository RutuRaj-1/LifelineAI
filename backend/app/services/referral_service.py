"""Multi-Hospital Referral Engine & Acceptance Coordination Service (Prompt 07).

Core Principles:
1. "A hospital appearing in a recommendation list does NOT mean it has accepted a patient."
2. "A resource appearing available does NOT mean the hospital has committed that resource."
3. "A referral is accepted ONLY when an authorized receiving-hospital user explicitly accepts it
   AND the corresponding reservation is successfully secured."
4. Single Active Acceptance Invariant: At most one referral may be ACCEPTED for an emergency case.
"""
from datetime import datetime, timedelta, timezone
import logging
import uuid
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..events import hub
from ..models import (
    ActivityLog,
    EmergencyCase,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    ReferralRequest,
    ReferralResponse,
    ResourceReservation,
    User,
)
from . import resource_service, runner

logger = logging.getLogger("lifeline.referral_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. Eligible Hospital Discovery Engine
# ==============================================================================

def get_eligible_hospitals(
    db: Session,
    emergency_case: EmergencyCase,
    requested_resource_type: str = "ICU_BED",
) -> list[dict]:
    """
    Evaluates verified hospitals for referral eligibility based on:
    1. Hospital active and verified status (Prompt 05).
    2. Verified clinical capabilities matching case specialty or emergency type.
    3. Operational resource status, freshness window, and usable capacity (Prompt 06).
    4. Whether a referral has already been dispatched in the current round.
    """
    # Expire stale referrals before calculation
    expire_stale_referrals(db, emergency_case.id)

    # Fetch all active/verified hospitals
    hospitals = (
        db.query(Hospital)
        .filter(Hospital.status.in_(["VERIFIED", "ACTIVE"]))
        .order_by(Hospital.name.asc())
        .all()
    )

    # Existing referrals for current round
    existing_referrals = {
        r.hospital_id: r
        for r in db.query(ReferralRequest)
        .filter(
            ReferralRequest.emergency_case_id == emergency_case.id,
            ReferralRequest.request_round == emergency_case.referral_round,
        )
        .all()
    }

    results = []
    case_type = (emergency_case.emergency_type or "").upper()
    specialty = (emergency_case.specialty or "").upper()

    for h in hospitals:
        reasons = []
        is_eligible = True
        status_label = "ELIGIBLE"

        # Check Hospital Operating Status
        if getattr(h, "status", None) in ("SUSPENDED", "INACTIVE", "CLOSED", "REJECTED"):
            reasons.append(f"Hospital operational status is {h.status}.")
            status_label = "HOSPITAL_SUSPENDED"
            is_eligible = False

        # Check Clinical Capabilities
        caps = (
            db.query(HospitalCapability)
            .filter(HospitalCapability.hospital_id == h.id)
            .all()
        )
        verified_caps = [c.capability_code for c in caps if c.verification_status == "VERIFIED"]

        # Check Department
        departments = (
            db.query(HospitalDepartment)
            .filter(HospitalDepartment.hospital_id == h.id, HospitalDepartment.operational_status == "ACTIVE")
            .all()
        )
        if not departments:
            reasons.append("No active clinical departments registered.")
            if is_eligible:
                status_label = "DEPARTMENT_UNAVAILABLE"
                is_eligible = False

        # Check Requested Resource Operational Status & Capacity
        res = (
            db.query(HospitalResource)
            .filter(
                HospitalResource.hospital_id == h.id,
                HospitalResource.resource_type == requested_resource_type,
            )
            .first()
        )

        res_summary = None
        if not res:
            reasons.append(f"Resource type '{requested_resource_type}' not provisioned at hospital.")
            if is_eligible:
                status_label = "RESOURCE_UNAVAILABLE"
                is_eligible = False
        else:
            freshness = resource_service.calculate_freshness(res)
            active_holds = resource_service.get_active_reserved_holds(db, res.id)
            usable_capacity = resource_service.calculate_usable_capacity(res, active_holds)

            res_summary = {
                "resource_type": res.resource_type,
                "usable_capacity": usable_capacity,
                "staffed_capacity": res.staffed_capacity or res.total,
                "operational_status": res.operational_status,
                "freshness_status": freshness,
                "is_confirmed_fresh": (freshness == "FRESH"),
            }

            if freshness == "SUSPENDED" or res.operational_status in ("MAINTENANCE", "CLOSED", "SUSPENDED", "NON_OPERATIONAL"):
                reasons.append(f"Resource {res.resource_type} is {res.operational_status}.")
                if is_eligible:
                    status_label = "RESOURCE_NON_OPERATIONAL"
                    is_eligible = False
            elif freshness == "STALE":
                reasons.append(f"Resource attestation is STALE (exceeds {res.freshness_window_minutes}m window).")
                if is_eligible:
                    status_label = "RESOURCE_STALE"
                    is_eligible = False
            elif freshness == "UNKNOWN":
                reasons.append("Resource has no recorded attestation timestamp.")
                if is_eligible:
                    status_label = "RESOURCE_UNKNOWN"
                    is_eligible = False
            elif usable_capacity <= 0:
                reasons.append(f"No usable capacity available ({usable_capacity} usable, {active_holds} active holds).")
                if is_eligible:
                    status_label = "INSUFFICIENT_CAPACITY"
                    is_eligible = False

        # Dispatch status check
        existing_ref = existing_referrals.get(h.id)
        is_dispatched = existing_ref is not None
        ref_id = existing_ref.id if existing_ref else None
        current_status = existing_ref.status if existing_ref else None

        if is_eligible:
            reasons.append("Verified capabilities and fresh operational resources confirmed.")

        results.append({
            "hospital_id": h.id,
            "hospital_name": h.name,
            "city": h.city,
            "address": h.address,
            "phone": h.phone,
            "eligibility_status": status_label,
            "is_eligible": is_eligible,
            "reasons": reasons,
            "verified_capabilities": verified_caps,
            "resource_summary": res_summary,
            "is_dispatched": is_dispatched,
            "referral_request_id": ref_id,
            "current_referral_status": current_status,
        })

    # Sort: Eligible first, then descending by usable capacity
    results.sort(
        key=lambda item: (
            1 if item["is_eligible"] else 0,
            item["resource_summary"]["usable_capacity"] if item["resource_summary"] else 0,
        ),
        reverse=True,
    )
    return results


# ==============================================================================
# 2. Referral Broadcasting Engine
# ==============================================================================

def broadcast_referrals(
    db: Session,
    emergency_case_id: int,
    hospital_ids: list[int],
    requested_resource_type: str,
    requested_by_user: User,
    response_timeout_minutes: int = 15,
    priority: int | None = None,
    notes: str | None = None,
    idempotency_key: str | None = None,
) -> list[ReferralRequest]:
    """
    Fans out individual, independent referral requests to specified receiving hospitals.
    - Preserves isolation: Hospital A cannot see Hospital B's referral request or responses.
    - Enforces idempotency via idempotency_key.
    - Prevents duplicate requests within the same round.
    """
    case = db.get(EmergencyCase, emergency_case_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    if case.status in ("COMPLETED", "CANCELLED", "CLOSED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot initiate referral for emergency in state: {case.status}.",
        )

    # Check if this case already has an active accepted referral
    accepted_ref = (
        db.query(ReferralRequest)
        .filter(ReferralRequest.emergency_case_id == case.id, ReferralRequest.status == "ACCEPTED")
        .first()
    )
    if accepted_ref:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Emergency already accepted by hospital ID {accepted_ref.hospital_id}. Cannot broadcast new referrals.",
        )

    now = utc_now()
    deadline = now + timedelta(minutes=response_timeout_minutes)
    created_requests = []

    # Clean hospital IDs (unique)
    target_hospital_ids = list(dict.fromkeys(hospital_ids))

    for hosp_id in target_hospital_ids:
        # Check Hospital existence
        hosp = db.get(Hospital, hosp_id)
        if not hosp:
            logger.warning(f"Skipping non-existent hospital id {hosp_id}")
            continue

        hosp_idemp_key = f"{idempotency_key}-{hosp_id}" if idempotency_key else None

        # 1. Idempotency Check
        if hosp_idemp_key:
            existing = (
                db.query(ReferralRequest)
                .filter(ReferralRequest.idempotency_key == hosp_idemp_key)
                .first()
            )
            if existing:
                created_requests.append(existing)
                continue

        # 2. Check for duplicate within the same round
        dup = (
            db.query(ReferralRequest)
            .filter(
                ReferralRequest.emergency_case_id == case.id,
                ReferralRequest.hospital_id == hosp_id,
                ReferralRequest.request_round == case.referral_round,
            )
            .first()
        )
        if dup:
            # Already dispatched in this round, include in response without duplicating
            created_requests.append(dup)
            continue

        # 3. Create independent ReferralRequest
        ref_code = f"REF-{case.id}-{hosp_id}-R{case.referral_round}-{uuid.uuid4().hex[:6].upper()}"
        req = ReferralRequest(
            emergency_case_id=case.id,
            hospital_id=hosp_id,
            request_reference=ref_code,
            request_round=case.referral_round,
            status="SENT",
            requested_resource_type=requested_resource_type,
            priority=priority or case.priority,
            notes=notes,
            requested_by_user_id=requested_by_user.id,
            requested_at=now,
            response_deadline=deadline,
            idempotency_key=hosp_idemp_key,
            created_at=now,
            updated_at=now,
        )
        db.add(req)
        db.flush()

        # Append initial DISPATCHED event in response history
        disp_event = ReferralResponse(
            referral_request_id=req.id,
            responding_user_id=requested_by_user.id,
            response_type="DISPATCHED",
            response_notes=f"Referral dispatched for {requested_resource_type} with deadline {deadline.strftime('%H:%M:%S')}.",
            responded_at=now,
            created_at=now,
        )
        db.add(disp_event)
        created_requests.append(req)

    # Activity log
    log = ActivityLog(
        case_id=case.id,
        event="REFERRAL_DISPATCHED",
        detail=f"Dispatched {len(created_requests)} referral requests for round {case.referral_round}.",
        actor=requested_by_user.full_name or requested_by_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()

    # WebSocket events broadcast
    for req in created_requests:
        db.refresh(req)
        broadcast_referral_event("REFERRAL_DISPATCHED", req)

    return created_requests


# ==============================================================================
# 3. Hospital Response Engine (Accept, Decline, Clarify)
# ==============================================================================

def accept_referral(
    db: Session,
    referral_id: int,
    responding_user: User,
    notes: str | None = None,
) -> ReferralRequest:
    """
    Explicit, authenticated hospital acceptance workflow:
    1. Authorization verification (user belongs to receiving hospital).
    2. Validates referral eligibility (SENT, REVIEWING, CLARIFICATION_REQUIRED; not EXPIRED).
    3. Emergency-Level Acceptance Invariant: checks if another hospital already accepted.
    4. Revalidates resource operational status, freshness window, and usable capacity.
    5. Atomically creates and confirms ResourceReservation via Prompt 06 resource engine.
    6. Updates referral status to 'ACCEPTED' and links emergency case to this hospital.
    7. Appends immutable ReferralResponse audit event.
    8. Protected by database conditional unique index uq_case_single_active_accepted.
    """
    referral = db.get(ReferralRequest, referral_id)
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found.")

    # 1. Authorization: Hospital user isolation
    if responding_user.hospital_id != referral.hospital_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Access denied: You can only accept referrals sent to your own hospital.",
        )

    # 2. State eligibility
    if referral.status == "ACCEPTED":
        return referral  # Idempotent return

    if referral.status in ("DECLINED", "CANCELLED", "EXPIRED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot accept referral in terminal status: {referral.status}.",
        )

    now = utc_now()

    # 3. Deadline verification
    deadline = referral.response_deadline
    if deadline:
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if deadline < now:
            referral.status = "EXPIRED"
            referral.updated_at = now
            db.commit()
            raise HTTPException(
                status.HTTP_410_GONE,
                "Referral response deadline has passed. Referral marked EXPIRED.",
            )

    # 4. Emergency Single Acceptance Invariant (Python-level check before commit)
    other_accepted = (
        db.query(ReferralRequest)
        .filter(
            ReferralRequest.emergency_case_id == referral.emergency_case_id,
            ReferralRequest.status == "ACCEPTED",
            ReferralRequest.id != referral.id,
        )
        .first()
    )
    if other_accepted:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Another hospital has already accepted this emergency case.",
        )

    # 5. Resource Verification & Atomic Reservation
    resource_type = referral.requested_resource_type or "ICU_BED"
    resource = (
        db.query(HospitalResource)
        .filter(
            HospitalResource.hospital_id == referral.hospital_id,
            HospitalResource.resource_type == resource_type,
        )
        .first()
    )
    if not resource:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Required resource '{resource_type}' is not configured at this hospital.",
        )

    freshness = resource_service.calculate_freshness(resource)
    if freshness == "SUSPENDED" or resource.operational_status in ("MAINTENANCE", "CLOSED", "SUSPENDED", "NON_OPERATIONAL"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot accept referral: {resource.resource_type} is {resource.operational_status}.",
        )

    if freshness in ("STALE", "UNKNOWN"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Resource attestation is {freshness} (exceeds freshness window). Staff must attest live counts before accepting.",
        )

    active_holds = resource_service.get_active_reserved_holds(db, resource.id)
    usable_capacity = resource_service.calculate_usable_capacity(resource, active_holds)
    if usable_capacity < 1:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Insufficient usable capacity for {resource.resource_type}. Usable: {usable_capacity}, Required: 1.",
        )

    # 6. Create Reservation Hold & Confirm atomically via resource_service
    reservation_key = f"res-accept-ref-{referral.id}"
    reservation, _ = resource_service.create_reservation_hold(
        db=db,
        hospital_resource_id=resource.id,
        quantity=1,
        referral_request_id=referral.id,
        idempotency_key=reservation_key,
        expires_in_minutes=120,
    )
    resource_service.confirm_reservation(db, reservation.id, user_id=responding_user.id)

    # 7. Update Referral Request & Emergency Case
    referral.status = "ACCEPTED"
    referral.is_active_acceptance = True
    referral.accepted_by_user_id = responding_user.id
    referral.responded_at = now
    referral.updated_at = now

    case = referral.emergency_case
    case.hospital_id = referral.hospital_id
    case.status = "ACCEPTED"
    case.updated_at = now

    # Append response event
    resp_event = ReferralResponse(
        referral_request_id=referral.id,
        responding_user_id=responding_user.id,
        response_type="ACCEPT",
        response_notes=notes or "Referral accepted. Bed/resource reserved.",
        responded_at=now,
        created_at=now,
    )
    db.add(resp_event)

    log = ActivityLog(
        case_id=case.id,
        event="REFERRAL_ACCEPTED",
        detail=f"Accepted by {responding_user.full_name} for {referral.hospital.name if referral.hospital else 'Hospital'}. Resource reserved.",
        actor=responding_user.full_name or responding_user.email,
        created_at=now,
    )
    db.add(log)

    # Commit — Enforced by DB constraint uq_case_single_active_accepted
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Conflict: another hospital accepted this emergency referral concurrently.",
        ) from exc

    db.refresh(referral)

    broadcast_referral_event("REFERRAL_ACCEPTED", referral)
    return referral


def decline_referral(
    db: Session,
    referral_id: int,
    responding_user: User,
    reason_code: str,
    notes: str | None = None,
) -> ReferralRequest:
    """Explicitly declines an incoming referral with a structured reason code."""
    referral = db.get(ReferralRequest, referral_id)
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found.")

    if responding_user.hospital_id != referral.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied: Cannot decline another hospital's referral.")

    if referral.status in ("ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot decline referral in status: {referral.status}.",
        )

    now = utc_now()
    referral.status = "DECLINED"
    referral.decline_reason_code = reason_code
    referral.responded_at = now
    referral.updated_at = now

    resp_event = ReferralResponse(
        referral_request_id=referral.id,
        responding_user_id=responding_user.id,
        response_type="DECLINE",
        reason_code=reason_code,
        response_notes=notes or f"Declined: {reason_code}",
        responded_at=now,
        created_at=now,
    )
    db.add(resp_event)

    log = ActivityLog(
        case_id=referral.emergency_case_id,
        event="REFERRAL_DECLINED",
        detail=f"Hospital {referral.hospital.name if referral.hospital else referral.hospital_id} declined. Reason: {reason_code}.",
        actor=responding_user.full_name or responding_user.email,
        created_at=now,
    )
    db.add(log)
    db.commit()
    db.refresh(referral)

    broadcast_referral_event("REFERRAL_DECLINED", referral)
    return referral


def request_clarification(
    db: Session,
    referral_id: int,
    responding_user: User,
    question: str,
) -> ReferralRequest:
    """Hospital requests clinical or operational clarification before deciding on admission."""
    referral = db.get(ReferralRequest, referral_id)
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found.")

    if responding_user.hospital_id != referral.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied.")

    if referral.status in ("ACCEPTED", "DECLINED", "CANCELLED", "EXPIRED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot request clarification in status: {referral.status}.",
        )

    now = utc_now()
    referral.status = "CLARIFICATION_REQUIRED"
    referral.clarification_notes = question
    referral.updated_at = now

    resp_event = ReferralResponse(
        referral_request_id=referral.id,
        responding_user_id=responding_user.id,
        response_type="REQUEST_CLARIFICATION",
        response_notes=question,
        responded_at=now,
        created_at=now,
    )
    db.add(resp_event)
    db.commit()
    db.refresh(referral)

    broadcast_referral_event("REFERRAL_CLARIFICATION_REQUESTED", referral)
    return referral


def provide_clarification(
    db: Session,
    referral_id: int,
    responding_user: User,
    answer: str,
) -> ReferralRequest:
    """Coordinator or Doctor answers hospital's clarification question."""
    referral = db.get(ReferralRequest, referral_id)
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found.")

    if referral.status != "CLARIFICATION_REQUIRED":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Referral is not awaiting clarification (current status: {referral.status}).",
        )

    now = utc_now()
    referral.status = "REVIEWING"
    referral.clarification_notes = f"{referral.clarification_notes or ''}\n\n[Answer]: {answer}"
    referral.updated_at = now

    resp_event = ReferralResponse(
        referral_request_id=referral.id,
        responding_user_id=responding_user.id,
        response_type="CLARIFICATION_PROVIDED",
        response_notes=answer,
        responded_at=now,
        created_at=now,
    )
    db.add(resp_event)
    db.commit()
    db.refresh(referral)

    broadcast_referral_event("REFERRAL_CLARIFICATION_RESPONDED", referral)
    return referral


def cancel_referral(
    db: Session,
    referral_id: int,
    cancelling_user: User,
    reason: str | None = None,
) -> ReferralRequest:
    """Authorized coordinator cancels a pending or accepted referral and safely releases reservations."""
    referral = db.get(ReferralRequest, referral_id)
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found.")

    if referral.status in ("CANCELLED", "DECLINED", "EXPIRED"):
        return referral

    now = utc_now()

    # If referral was accepted or had active reservations, release them safely
    reservations = (
        db.query(ResourceReservation)
        .filter(
            ResourceReservation.referral_request_id == referral.id,
            ResourceReservation.reservation_status.in_(["HELD", "CONFIRMED"]),
        )
        .all()
    )
    for res in reservations:
        resource_service.release_reservation(db, res.id, reason=f"Referral cancelled: {reason or 'No reason provided'}")

    was_accepted = (referral.status == "ACCEPTED")
    referral.status = "CANCELLED"
    referral.is_active_acceptance = False
    referral.updated_at = now

    if was_accepted and referral.emergency_case and referral.emergency_case.hospital_id == referral.hospital_id:
        referral.emergency_case.hospital_id = None
        referral.emergency_case.status = "IN_TRANSIT"
        referral.emergency_case.updated_at = now

    resp_event = ReferralResponse(
        referral_request_id=referral.id,
        responding_user_id=cancelling_user.id,
        response_type="CANCEL",
        response_notes=reason or "Referral cancelled by coordinator.",
        responded_at=now,
        created_at=now,
    )
    db.add(resp_event)
    db.commit()
    db.refresh(referral)

    broadcast_referral_event("REFERRAL_CANCELLED", referral)
    return referral


def expire_stale_referrals(db: Session, emergency_case_id: int | None = None) -> int:
    """Idempotently finds and marks expired referrals whose response deadline has elapsed."""
    now = utc_now()
    q = db.query(ReferralRequest).filter(
        ReferralRequest.status.in_(["SENT", "REVIEWING", "CLARIFICATION_REQUIRED"]),
        ReferralRequest.response_deadline.isnot(None),
        ReferralRequest.response_deadline < now,
    )
    if emergency_case_id:
        q = q.filter(ReferralRequest.emergency_case_id == emergency_case_id)

    stale_list = q.all()
    count = 0
    for req in stale_list:
        req.status = "EXPIRED"
        req.updated_at = now
        count += 1
        db.add(
            ReferralResponse(
                referral_request_id=req.id,
                response_type="EXPIRED",
                response_notes="Referral expired: response deadline elapsed without hospital decision.",
                responded_at=now,
                created_at=now,
            )
        )

    if count > 0:
        db.commit()
    return count


# ==============================================================================
# 4. WebSocket Event Notification Helper
# ==============================================================================

def broadcast_referral_event(event_type: str, referral: ReferralRequest) -> None:
    """Publishes scoped referral lifecycle events over the in-process WebSocket hub."""
    try:
        info = {
            "hospital_id": referral.hospital_id,
            "patient_id": referral.emergency_case.patient_id if referral.emergency_case else None,
        }
        data = {
            "referral_id": referral.id,
            "emergency_case_id": referral.emergency_case_id,
            "hospital_id": referral.hospital_id,
            "status": referral.status,
            "request_reference": referral.request_reference,
            "request_round": referral.request_round,
            "requested_resource_type": referral.requested_resource_type,
            "timestamp": referral.updated_at.isoformat() if referral.updated_at else None,
        }
        runner.spawn(hub.emit(event_type, info, **data))
    except Exception as exc:
        logger.warning(f"Could not broadcast referral event {event_type}: {exc}")
