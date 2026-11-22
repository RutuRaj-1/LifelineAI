from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Hospital, HospitalCapability, HospitalDepartment, User
from ..schemas import VerificationActionIn
from ..security import require_roles
from ..services.serialize import capability_dict, hospital_dict

router = APIRouter(prefix="/admin", tags=["Administration & Review"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/hospital-reviews")
def list_pending_reviews(
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """
    List hospitals and capability submissions currently pending administrative review.
    Protected strictly for admin / reviewer role.
    """
    pending_hospitals = (
        db.query(Hospital)
        .filter(Hospital.status.in_(["SUBMITTED", "UNDER_REVIEW"]))
        .order_by(Hospital.updated_at.desc())
        .all()
    )
    pending_capabilities = (
        db.query(HospitalCapability)
        .filter(HospitalCapability.verification_status.in_(["PENDING_REVIEW", "UNVERIFIED"]))
        .order_by(HospitalCapability.updated_at.desc())
        .all()
    )

    return {
        "pending_hospitals": [hospital_dict(h, detail=True) for h in pending_hospitals],
        "pending_capabilities": [capability_dict(c) for c in pending_capabilities],
        "pending_hospital_count": len(pending_hospitals),
        "pending_capability_count": len(pending_capabilities),
    }


@router.post("/hospital-capabilities/{capability_id}/verify")
def verify_capability(
    capability_id: int,
    body: VerificationActionIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Approve and formally verify a clinical capability claim."""
    cap = db.get(HospitalCapability, capability_id)
    if not cap:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capability not found.")

    cap.verification_status = "VERIFIED"
    cap.verified_by_user_id = user.id
    cap.verified_at = utc_now()
    cap.verification_notes = body.notes or "Capability verified by administrative review."
    cap.verification_source = body.verification_source or "ADMINISTRATIVE_AUDIT"
    cap.updated_at = utc_now()

    db.commit()
    db.refresh(cap)
    return capability_dict(cap)


@router.post("/hospital-capabilities/{capability_id}/reject")
def reject_capability(
    capability_id: int,
    body: VerificationActionIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Reject a capability submission with required audit rationale."""
    cap = db.get(HospitalCapability, capability_id)
    if not cap:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capability not found.")

    cap.verification_status = "REJECTED"
    cap.verified_by_user_id = user.id
    cap.verified_at = utc_now()
    cap.verification_notes = body.notes or "Capability claim rejected during administrative review."
    cap.updated_at = utc_now()

    db.commit()
    db.refresh(cap)
    return capability_dict(cap)


@router.post("/hospitals/{hospital_id}/verify")
def verify_hospital_profile(
    hospital_id: int,
    body: VerificationActionIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Verify a hospital registry profile."""
    h = db.get(Hospital, hospital_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found.")

    h.status = "VERIFIED"
    h.verified_by_user_id = user.id
    h.verified_at = utc_now()
    h.verification_notes = body.notes or "Hospital registry profile verified."
    h.updated_at = utc_now()

    db.commit()
    db.refresh(h)
    return hospital_dict(h, detail=True)


@router.post("/hospitals/{hospital_id}/reject")
def reject_hospital_profile(
    hospital_id: int,
    body: VerificationActionIn,
    user: User = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    """Reject a hospital registry profile submission with rationale."""
    h = db.get(Hospital, hospital_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found.")

    h.status = "REJECTED"
    h.verified_by_user_id = user.id
    h.verified_at = utc_now()
    h.verification_notes = body.notes or "Hospital profile rejected during administrative review."
    h.updated_at = utc_now()

    db.commit()
    db.refresh(h)
    return hospital_dict(h, detail=True)
