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
    ReserveIn,
)
from ..security import require_roles
from ..services import ops
from ..services.serialize import capability_dict, case_dict, department_dict, hospital_dict

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


# --- 4. Operational Resource & Emergency Queue Endpoints (Preserved) ---

@router.get("/resources")
def get_resources(user: User = Depends(require_roles("hospital", "doctor")), db: Session = Depends(get_db)):
    rows = db.query(HospitalResource).filter(HospitalResource.hospital_id == user.hospital_id).all()
    return [{"resource_type": r.resource_type, "total": r.total, "available": r.available} for r in rows]


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
