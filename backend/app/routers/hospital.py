from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (
    EmergencyCase,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    ReferralRequest,
    ReferralResponse,
    ResourceStatusHistory,
    User,
)
from ..schemas import (
    HospitalCapabilityOut,
    HospitalCapabilityUpdate,
    HospitalCapabilityUserCreate,
    HospitalDepartmentOut,
    HospitalDepartmentUpdate,
    HospitalDepartmentUserCreate,
    HospitalOut,
    HospitalProfileUpdate,
    OperationalResourceOut,
    ReferralAcceptIn,
    ReferralClarificationIn,
    ReferralDeclineIn,
    ReserveIn,
    ResourceAttestationIn,
    ResourceConfigUpdate,
)
from ..security import require_roles
from ..services import ops, referral_service, resource_service
from ..services.serialize import (
    capability_dict,
    case_dict,
    department_dict,
    hospital_dict,
    referral_request_dict,
    resource_dict,
    resource_history_dict,
)

router = APIRouter(prefix="/hospital", tags=["Hospital"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _get_user_hospital(db: Session, user: User) -> Hospital:
    if not user.hospital_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Authenticated user is not associated with any hospital.")
    h = db.get(Hospital, user.hospital_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found.")
    return h


# --- 1. Hospital Profile Management ---

@router.get("/profile")
def get_hospital_profile(
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Retrieve the authenticated hospital user's own hospital profile."""
    h = _get_user_hospital(db, user)
    return hospital_dict(h, detail=True)


@router.patch("/profile")
def update_hospital_profile(
    body: HospitalProfileUpdate,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Update profile information for the authenticated hospital."""
    h = _get_user_hospital(db, user)
    data = body.model_dump(exclude_unset=True)
    for field, val in data.items():
        if val is not None:
            setattr(h, field, val)
    h.updated_at = utc_now()
    db.commit()
    db.refresh(h)
    return hospital_dict(h, detail=True)


@router.post("/profile/submit")
def submit_hospital_profile(
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Submit hospital profile for administrative verification review."""
    h = _get_user_hospital(db, user)
    if h.status not in ("DRAFT", "REJECTED", "VERIFIED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot submit hospital profile with current status: {h.status}",
        )
    h.status = "UNDER_REVIEW"
    h.updated_at = utc_now()
    db.commit()
    db.refresh(h)
    return {"status": h.status, "message": "Hospital profile submitted for administrative verification."}


# --- 2. Hospital Department Management ---

@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(
    body: HospitalDepartmentUserCreate,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Create a new department within the authenticated hospital."""
    h = _get_user_hospital(db, user)
    dept_code = body.department_code.strip().upper()

    # Enforce uniqueness within hospital: UNIQUE(hospital_id, department_code)
    existing = (
        db.query(HospitalDepartment)
        .filter(HospitalDepartment.hospital_id == h.id, HospitalDepartment.department_code == dept_code)
        .first()
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Department code '{dept_code}' already exists for this hospital.",
        )

    dept = HospitalDepartment(
        hospital_id=h.id,
        department_name=body.department_name.strip(),
        department_code=dept_code,
        description=body.description,
        operational_status=body.operational_status,
        contact_information=body.contact_information,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return department_dict(dept)


@router.get("/departments")
def list_departments(
    operational_status: str | None = Query(None, description="Filter by operational status (ACTIVE/INACTIVE/LIMITED)"),
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """List all departments for the authenticated hospital."""
    h = _get_user_hospital(db, user)
    q = db.query(HospitalDepartment).filter(HospitalDepartment.hospital_id == h.id)
    if operational_status:
        q = q.filter(HospitalDepartment.operational_status == operational_status.upper())
    departments = q.order_by(HospitalDepartment.department_name.asc()).all()
    return [department_dict(d) for d in departments]


@router.get("/departments/{department_id}")
def get_department(
    department_id: int,
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """Retrieve an individual department with ownership validation."""
    h = _get_user_hospital(db, user)
    dept = db.get(HospitalDepartment, department_id)
    if not dept or dept.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found at your hospital.")
    return department_dict(dept)


@router.patch("/departments/{department_id}")
def update_department(
    department_id: int,
    body: HospitalDepartmentUpdate,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Update department information."""
    h = _get_user_hospital(db, user)
    dept = db.get(HospitalDepartment, department_id)
    if not dept or dept.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found at your hospital.")

    data = body.model_dump(exclude_unset=True)
    for field, val in data.items():
        if val is not None:
            setattr(dept, field, val)
    dept.updated_at = utc_now()
    db.commit()
    db.refresh(dept)
    return department_dict(dept)


@router.delete("/departments/{department_id}")
def deactivate_department(
    department_id: int,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Soft-deactivate a department to preserve historical resource allocations and audit trails."""
    h = _get_user_hospital(db, user)
    dept = db.get(HospitalDepartment, department_id)
    if not dept or dept.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Department not found at your hospital.")

    dept.operational_status = "INACTIVE"
    dept.updated_at = utc_now()
    db.commit()
    return {"status": "deactivated", "id": department_id, "operational_status": "INACTIVE"}


# --- 3. Hospital Clinical Capability Management ---

@router.post("/capabilities", status_code=status.HTTP_201_CREATED)
def create_capability(
    body: HospitalCapabilityUserCreate,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Register a new clinical capability claim for the authenticated hospital."""
    h = _get_user_hospital(db, user)
    cap_code = body.capability_code.strip().upper()

    # Enforce uniqueness within hospital: UNIQUE(hospital_id, capability_code)
    existing = (
        db.query(HospitalCapability)
        .filter(HospitalCapability.hospital_id == h.id, HospitalCapability.capability_code == cap_code)
        .first()
    )
    if existing:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Capability '{cap_code}' already registered for this hospital.",
        )

    # Validate department ownership if provided
    if body.department_id:
        dept = db.get(HospitalDepartment, body.department_id)
        if not dept or dept.hospital_id != h.id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Specified department does not exist or does not belong to your hospital.",
            )

    cap = HospitalCapability(
        hospital_id=h.id,
        department_id=body.department_id,
        capability_code=cap_code,
        capability_name=body.capability_name.strip(),
        capability_category=body.capability_category.strip().upper(),
        description=body.description,
        availability_mode=body.availability_mode,
        verification_status="UNVERIFIED",
    )
    db.add(cap)
    db.commit()
    db.refresh(cap)
    return capability_dict(cap)


@router.get("/capabilities")
def list_capabilities(
    verification_status: str | None = Query(None, description="Filter by verification status (UNVERIFIED/PENDING_REVIEW/VERIFIED/REJECTED)"),
    category: str | None = Query(None, description="Filter by category (DIAGNOSTIC/SURGICAL/CRITICAL_CARE/STABILIZATION)"),
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """List registered clinical capabilities for the authenticated hospital."""
    h = _get_user_hospital(db, user)
    q = db.query(HospitalCapability).filter(HospitalCapability.hospital_id == h.id)
    if verification_status:
        q = q.filter(HospitalCapability.verification_status == verification_status.upper())
    if category:
        q = q.filter(HospitalCapability.capability_category == category.upper())
    caps = q.order_by(HospitalCapability.capability_name.asc()).all()
    return [capability_dict(c) for c in caps]


@router.get("/capabilities/{capability_id}")
def get_capability(
    capability_id: int,
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """Retrieve an individual capability with hospital ownership verification."""
    h = _get_user_hospital(db, user)
    cap = db.get(HospitalCapability, capability_id)
    if not cap or cap.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capability not found at your hospital.")
    return capability_dict(cap)


@router.patch("/capabilities/{capability_id}")
def update_capability(
    capability_id: int,
    body: HospitalCapabilityUpdate,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Update capability details. Verification status cannot be altered directly via patch."""
    h = _get_user_hospital(db, user)
    cap = db.get(HospitalCapability, capability_id)
    if not cap or cap.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capability not found at your hospital.")

    data = body.model_dump(exclude_unset=True)
    if "department_id" in data and data["department_id"] is not None:
        dept = db.get(HospitalDepartment, data["department_id"])
        if not dept or dept.hospital_id != h.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not belong to your hospital.")

    for field, val in data.items():
        if val is not None:
            setattr(cap, field, val)
    cap.updated_at = utc_now()
    db.commit()
    db.refresh(cap)
    return capability_dict(cap)


@router.post("/capabilities/{capability_id}/submit-review")
def submit_capability_review(
    capability_id: int,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """Submit a capability claim for formal administrative verification."""
    h = _get_user_hospital(db, user)
    cap = db.get(HospitalCapability, capability_id)
    if not cap or cap.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Capability not found at your hospital.")

    cap.verification_status = "PENDING_REVIEW"
    cap.updated_at = utc_now()
    db.commit()
    db.refresh(cap)
    return capability_dict(cap)


# --- 4. Operational Resource Management (Prompt 06) ---

@router.get("/resources")
def get_resources(
    department_id: int | None = Query(None, description="Filter by department"),
    resource_type: str | None = Query(None, description="Filter by resource type"),
    operational_status: str | None = Query(None, description="Filter by operational status"),
    freshness_status: str | None = Query(None, description="Filter by freshness status (FRESH/STALE/UNKNOWN/SUSPENDED)"),
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """
    Retrieve operational resources for the authenticated hospital staff.
    Computes derived usable capacity, active holds, physical/staffed counts,
    and freshness classification dynamically.
    """
    h = _get_user_hospital(db, user)
    q = db.query(HospitalResource).filter(HospitalResource.hospital_id == h.id)
    if department_id:
        q = q.filter(HospitalResource.department_id == department_id)
    if resource_type:
        q = q.filter(HospitalResource.resource_type == resource_type.upper())
    if operational_status:
        q = q.filter(HospitalResource.operational_status == operational_status.upper())

    rows = q.order_by(HospitalResource.resource_type.asc()).all()
    results = []
    for r in rows:
        active_holds = resource_service.get_active_reserved_holds(db, r.id)
        resource_service.sync_legacy_available(db, r, active_holds)
        d = resource_dict(r, active_holds=active_holds, detail=True)
        if freshness_status and d["freshness_status"] != freshness_status.upper():
            continue
        results.append(d)
    return results


@router.get("/resources/{resource_id}")
def get_resource_detail(
    resource_id: int,
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """Retrieve operational capacity and attestation details for a specific resource."""
    h = _get_user_hospital(db, user)
    r = db.get(HospitalResource, resource_id)
    if not r or r.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found at your hospital.")

    active_holds = resource_service.get_active_reserved_holds(db, r.id)
    resource_service.sync_legacy_available(db, r, active_holds)
    return resource_dict(r, active_holds=active_holds, detail=True)


@router.post("/resources/{resource_id}/attest")
def attest_resource_capacity(
    resource_id: int,
    body: ResourceAttestationIn,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Hospital staff operational attestation.
    Validates capacity metrics, records append-only history, updates freshness,
    and recalculates usable capacity transactionally.
    """
    h = _get_user_hospital(db, user)
    r = db.get(HospitalResource, resource_id)
    if not r or r.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found at your hospital.")

    updated_resource = resource_service.attest_resource(
        db=db,
        resource=r,
        user_id=user.id,
        staffed_capacity=body.staffed_capacity,
        occupied_count=body.occupied_count,
        maintenance_count=body.maintenance_count,
        operational_status=body.operational_status,
        status_source=body.status_source or "MANUAL",
        remarks=body.remarks or body.notes,
        freshness_window_minutes=body.freshness_window_minutes,
    )
    active_holds = resource_service.get_active_reserved_holds(db, r.id)
    return resource_dict(updated_resource, active_holds=active_holds, detail=True)


@router.patch("/resources/{resource_id}")
def update_resource_configuration(
    resource_id: int,
    body: ResourceConfigUpdate,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Update resource structural configuration (e.g. department link, physical total, freshness window).
    Operational capacity metrics must be updated via the /attest endpoint.
    """
    h = _get_user_hospital(db, user)
    r = db.get(HospitalResource, resource_id)
    if not r or r.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found at your hospital.")

    data = body.model_dump(exclude_unset=True)
    if "department_id" in data and data["department_id"] is not None:
        dept = db.get(HospitalDepartment, data["department_id"])
        if not dept or dept.hospital_id != h.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Department does not belong to your hospital.")
        r.department_id = data["department_id"]

    if "total" in data and data["total"] is not None:
        if data["total"] < 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Physical total cannot be negative.")
        r.total = data["total"]
        if r.staffed_capacity is not None and r.staffed_capacity > r.total:
            r.staffed_capacity = r.total

    if "freshness_window_minutes" in data and data["freshness_window_minutes"] is not None:
        r.freshness_window_minutes = data["freshness_window_minutes"]

    r.updated_at = utc_now()
    active_holds = resource_service.get_active_reserved_holds(db, r.id)
    resource_service.sync_legacy_available(db, r, active_holds)
    db.commit()
    db.refresh(r)
    return resource_dict(r, active_holds=active_holds, detail=True)


@router.get("/resources/{resource_id}/history")
def get_resource_history(
    resource_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_roles("hospital", "doctor")),
    db: Session = Depends(get_db),
):
    """Retrieve paginated append-only operational status history for a resource."""
    h = _get_user_hospital(db, user)
    r = db.get(HospitalResource, resource_id)
    if not r or r.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resource not found at your hospital.")

    q = (
        db.query(ResourceStatusHistory)
        .filter(ResourceStatusHistory.hospital_resource_id == r.id)
        .order_by(ResourceStatusHistory.created_at.desc())
    )
    total = q.count()
    rows = q.offset(offset).limit(limit).all()
    return {
        "resource_id": r.id,
        "resource_type": r.resource_type,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [resource_history_dict(h) for h in rows],
    }


# --- 5. Emergency Queue & Manual Reservation Endpoints (Preserved) ---


@router.post("/reserve")
def reserve(body: ReserveIn, user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    c = db.get(EmergencyCase, body.case_id)
    if not c or c.hospital_id != user.hospital_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found at your hospital")
    if not ops.reserve_resource(db, c, body.resource_type):
        raise HTTPException(status.HTTP_409_CONFLICT, f"No {body.resource_type} available")
    ops.log_event(db, c.id, "MANUAL_RESERVATION", f"{body.resource_type} reserved by staff", "hospital")
    db.commit()
    return {"reserved_resources": c.reserved_resources}


@router.get("/queue")
def emergency_queue(user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    cases = (
        db.query(EmergencyCase)
        .filter(EmergencyCase.hospital_id == user.hospital_id, EmergencyCase.status != "COMPLETED")
        .order_by(EmergencyCase.priority, EmergencyCase.created_at)
        .all()
    )
    return [case_dict(c, "hospital", detail=True) for c in cases]


@router.get("/cases/history")
def case_history(user: User = Depends(require_roles("hospital")), db: Session = Depends(get_db)):
    cases = (
        db.query(EmergencyCase)
        .filter(EmergencyCase.hospital_id == user.hospital_id, EmergencyCase.status == "COMPLETED")
        .order_by(EmergencyCase.completed_at.desc())
        .limit(50)
        .all()
    )
    return [case_dict(c, "hospital", detail=True) for c in cases]


# --- 6. Incoming Referral Coordination & Decision Workflows (Prompt 07) ---


@router.get("/referrals/incoming")
def list_incoming_referrals(
    status_filter: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Authenticated Hospital Inbox:
    Retrieves incoming emergency referral requests directed to this hospital.
    Strictly isolated: Hospital A can never access Hospital B's referrals.
    """
    h = _get_user_hospital(db, user)

    # Automatically check for expired referrals
    referral_service.expire_stale_referrals(db)

    q = (
        db.query(ReferralRequest)
        .filter(ReferralRequest.hospital_id == h.id)
    )

    if status_filter:
        s = status_filter.strip().upper()
        if s == "PENDING":
            q = q.filter(ReferralRequest.status.in_(["SENT", "REVIEWING"]))
        elif s == "ACTIVE":
            q = q.filter(ReferralRequest.status.in_(["SENT", "REVIEWING", "CLARIFICATION_REQUIRED", "ACCEPTED"]))
        else:
            q = q.filter(ReferralRequest.status == s)

    total = q.count()
    rows = (
        q.order_by(
            ReferralRequest.priority.asc(),
            ReferralRequest.requested_at.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "hospital_id": h.id,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [referral_request_dict(r, role="hospital", detail=False) for r in rows],
    }


@router.get("/referrals/{referral_id}")
def get_incoming_referral_detail(
    referral_id: int,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Detailed clinical handover view for an incoming referral request.
    Data minimized: provides vital emergency context, allergies, verified facts, and requested resource.
    """
    h = _get_user_hospital(db, user)
    referral = db.get(ReferralRequest, referral_id)
    if not referral or referral.hospital_id != h.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Referral request not found at your hospital.")

    # Automatically transition SENT -> REVIEWING on first opening
    if referral.status == "SENT":
        referral.status = "REVIEWING"
        referral.updated_at = utc_now()
        db.commit()
        db.refresh(referral)

    return referral_request_dict(referral, role="hospital", detail=True)


@router.post("/referrals/{referral_id}/accept")
def accept_incoming_referral(
    referral_id: int,
    body: ReferralAcceptIn,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Explicit, authenticated hospital acceptance:
    - Revalidates resource operational status, freshness window, and usable capacity.
    - Atomically creates and confirms ResourceReservation.
    - Enforces Single Active Acceptance Invariant: at most one hospital accepts an emergency.
    - Transitions referral status to 'ACCEPTED'.
    """
    accepted = referral_service.accept_referral(
        db=db,
        referral_id=referral_id,
        responding_user=user,
        notes=body.notes,
    )
    return referral_request_dict(accepted, role="hospital", detail=True)


@router.post("/referrals/{referral_id}/decline")
def decline_incoming_referral(
    referral_id: int,
    body: ReferralDeclineIn,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Explicit hospital decline with structured reason code:
    (NO_BEDS, NO_SPECIALIST, DIVERT, RESOURCE_UNAVAILABLE, CLINICAL_REVIEW_DECLINED, OTHER).
    """
    declined = referral_service.decline_referral(
        db=db,
        referral_id=referral_id,
        responding_user=user,
        reason_code=body.reason_code,
        notes=body.notes,
    )
    return referral_request_dict(declined, role="hospital", detail=True)


@router.post("/referrals/{referral_id}/clarification")
def request_referral_clarification(
    referral_id: int,
    body: ReferralClarificationIn,
    user: User = Depends(require_roles("hospital")),
    db: Session = Depends(get_db),
):
    """
    Hospital requests clinical or operational clarification from the originating emergency coordinator/doctor.
    """
    clarified = referral_service.request_clarification(
        db=db,
        referral_id=referral_id,
        responding_user=user,
        question=body.question,
    )
    return referral_request_dict(clarified, role="hospital", detail=True)
