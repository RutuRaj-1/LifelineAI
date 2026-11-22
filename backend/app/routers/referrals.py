"""Referral Coordination Router for Emergency Doctors & Coordinators (Prompt 07).

Enables authorized clinicians to:
1. Discover eligible receiving hospitals based on verified capabilities and live operational resource readiness.
2. Broadcast individual, independent referral requests to selected hospitals.
3. Track referral responses, clarifications, and explicit hospital acceptance.
4. Answer clarification requests and safely cancel referrals.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import EmergencyCase, ReferralRequest, User
from ..schemas import (
    ReferralBroadcastIn,
    ReferralCancelIn,
    ReferralClarificationAnswerIn,
)
from ..security import require_roles
from ..services import referral_service
from ..services.serialize import referral_request_dict

router = APIRouter(tags=["Referrals"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==============================================================================
# 1. Hospital Eligibility Discovery for Emergency Cases
# ==============================================================================

@router.get("/emergency/{emergency_id}/referral-eligibility")
@router.get("/emergencies/{emergency_id}/referral-eligibility")
def check_referral_eligibility(
    emergency_id: int,
    requested_resource_type: str = Query("ICU_BED"),
    user: User = Depends(require_roles("doctor", "admin", "hospital")),
    db: Session = Depends(get_db),
):
    """
    Evaluates verified receiving hospitals for clinical capability and live operational resource readiness.
    Distinguishes verified capabilities, resource operational status, freshness, and usable capacity.
    """
    case = db.get(EmergencyCase, emergency_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    eligible_list = referral_service.get_eligible_hospitals(
        db=db,
        emergency_case=case,
        requested_resource_type=requested_resource_type,
    )

    return {
        "emergency_case_id": case.id,
        "emergency_type": case.emergency_type,
        "specialty": case.specialty,
        "requested_resource_type": requested_resource_type,
        "referral_round": case.referral_round,
        "total_hospitals_evaluated": len(eligible_list),
        "eligible_hospitals": eligible_list,
    }


# ==============================================================================
# 2. Multi-Hospital Referral Broadcasting
# ==============================================================================

@router.post("/emergency/{emergency_id}/referrals", status_code=status.HTTP_201_CREATED)
@router.post("/emergencies/{emergency_id}/referrals", status_code=status.HTTP_201_CREATED)
def broadcast_case_referrals(
    emergency_id: int,
    body: ReferralBroadcastIn,
    user: User = Depends(require_roles("doctor", "admin", "hospital")),
    db: Session = Depends(get_db),
):
    """
    Fans out individual, independent referral requests to specified receiving hospitals.
    Enforces idempotency and isolation.
    """
    created_requests = referral_service.broadcast_referrals(
        db=db,
        emergency_case_id=emergency_id,
        hospital_ids=body.hospital_ids,
        requested_resource_type=body.requested_resource_type,
        requested_by_user=user,
        response_timeout_minutes=body.response_timeout_minutes,
        priority=body.priority,
        notes=body.notes,
        idempotency_key=body.idempotency_key,
    )

    return {
        "emergency_case_id": emergency_id,
        "dispatched_count": len(created_requests),
        "referrals": [referral_request_dict(r, role=user.role, detail=True) for r in created_requests],
    }


# ==============================================================================
# 3. Emergency Referrals List & Timeline
# ==============================================================================

@router.get("/emergency/{emergency_id}/referrals")
@router.get("/emergencies/{emergency_id}/referrals")
def list_case_referrals(
    emergency_id: int,
    user: User = Depends(require_roles("doctor", "admin", "hospital", "patient")),
    db: Session = Depends(get_db),
):
    """
    Lists all referral requests and response decisions across rounds for a specific emergency case.
    Role-aware: Patients see status without internal hospital capacity notes.
    """
    case = db.get(EmergencyCase, emergency_id)
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Emergency case not found.")

    # Automatically check expired
    referral_service.expire_stale_referrals(db, case.id)

    referrals = (
        db.query(ReferralRequest)
        .filter(ReferralRequest.emergency_case_id == emergency_id)
        .order_by(ReferralRequest.request_round.desc(), ReferralRequest.created_at.desc())
        .all()
    )

    return {
        "emergency_case_id": case.id,
        "referral_round": case.referral_round,
        "total": len(referrals),
        "referrals": [referral_request_dict(r, role=user.role, detail=(user.role != "patient")) for r in referrals],
    }


# ==============================================================================
# 4. Referral Detail & Response Actions
# ==============================================================================

@router.get("/referrals/{referral_id}")
def get_referral_detail(
    referral_id: int,
    user: User = Depends(require_roles("doctor", "admin", "hospital")),
    db: Session = Depends(get_db),
):
    """Detailed view of a referral request with complete response audit history."""
    referral = db.get(ReferralRequest, referral_id)
    if not referral:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found.")

    # Hospital role isolation check
    if user.role == "hospital" and user.hospital_id != referral.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied to other hospital's referral.")

    return referral_request_dict(referral, role=user.role, detail=True)


@router.post("/referrals/{referral_id}/clarifications/respond")
def respond_to_clarification(
    referral_id: int,
    body: ReferralClarificationAnswerIn,
    user: User = Depends(require_roles("doctor", "admin", "hospital")),
    db: Session = Depends(get_db),
):
    """Doctor or Coordinator responds to a hospital's clarification request."""
    updated = referral_service.provide_clarification(
        db=db,
        referral_id=referral_id,
        responding_user=user,
        answer=body.answer,
    )
    return referral_request_dict(updated, role=user.role, detail=True)


@router.post("/referrals/{referral_id}/cancel")
def cancel_case_referral(
    referral_id: int,
    body: ReferralCancelIn | None = None,
    user: User = Depends(require_roles("doctor", "admin")),
    db: Session = Depends(get_db),
):
    """Authorized clinician/coordinator cancels an active referral request and safely releases any held reservation."""
    reason = body.reason if body else None
    cancelled = referral_service.cancel_referral(
        db=db,
        referral_id=referral_id,
        cancelling_user=user,
        reason=reason,
    )
    return referral_request_dict(cancelled, role=user.role, detail=True)
