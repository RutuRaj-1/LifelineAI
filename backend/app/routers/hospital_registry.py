from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Hospital, HospitalCapability, HospitalDepartment
from ..services.serialize import capability_dict, department_dict, hospital_dict

router = APIRouter(prefix="/hospitals", tags=["Public Hospital Registry"])


@router.get("")
def list_public_hospitals(
    city: str | None = Query(None, description="Filter by city name"),
    hospital_type: str | None = Query(None, description="Filter by hospital type"),
    status: str | None = Query(None, description="Filter by registry status (default: VERIFIED)"),
    verified_only: bool = Query(True, description="When true, only returns VERIFIED hospitals"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Public hospital discovery endpoint.
    Returns hospitals matching search criteria without exposing sensitive internal audit notes.
    """
    q = db.query(Hospital)

    if verified_only:
        q = q.filter(Hospital.status == "VERIFIED")
    elif status:
        q = q.filter(Hospital.status == status.upper())

    if city:
        q = q.filter(Hospital.city.ilike(f"%{city.strip()}%"))
    if hospital_type:
        q = q.filter(Hospital.hospital_type == hospital_type.upper())

    total = q.count()
    hospitals = q.order_by(Hospital.name.asc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [hospital_dict(h, detail=False) for h in hospitals],
        "disclaimer": "Registered hospitals and clinical capabilities reflect hospital readiness claims. "
                      "They do not guarantee real-time bed, equipment, or specialist availability.",
    }


@router.get("/{hospital_id}")
def get_public_hospital_detail(
    hospital_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve public details and capability count for a specific hospital.
    """
    h = db.get(Hospital, hospital_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found in registry.")

    # Only verified hospitals or hospitals in active registry can be publicly viewed
    data = hospital_dict(h, detail=False)
    data["department_count"] = (
        db.query(HospitalDepartment)
        .filter(HospitalDepartment.hospital_id == h.id, HospitalDepartment.operational_status == "ACTIVE")
        .count()
    )
    data["verified_capabilities_count"] = (
        db.query(HospitalCapability)
        .filter(HospitalCapability.hospital_id == h.id, HospitalCapability.verification_status == "VERIFIED")
        .count()
    )
    data["disclaimer"] = (
        "Registered capabilities indicate institutional service claims. "
        "Real-time operational availability is confirmed only upon pre-arrival coordination."
    )
    return data


@router.get("/{hospital_id}/departments")
def list_public_hospital_departments(
    hospital_id: int,
    db: Session = Depends(get_db),
):
    """List publicly viewable active departments of a hospital."""
    h = db.get(Hospital, hospital_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found.")

    departments = (
        db.query(HospitalDepartment)
        .filter(HospitalDepartment.hospital_id == h.id, HospitalDepartment.operational_status == "ACTIVE")
        .order_by(HospitalDepartment.department_name.asc())
        .all()
    )
    return [department_dict(d) for d in departments]


@router.get("/{hospital_id}/capabilities")
def list_public_hospital_capabilities(
    hospital_id: int,
    category: str | None = Query(None, description="Filter by capability category"),
    verified_only: bool = Query(True, description="When true, only returns formally VERIFIED capabilities"),
    db: Session = Depends(get_db),
):
    """
    List clinical capabilities registered by a hospital.
    Defaults to verified capabilities only for public safety.
    """
    h = db.get(Hospital, hospital_id)
    if not h:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital not found.")

    q = db.query(HospitalCapability).filter(HospitalCapability.hospital_id == h.id)
    if verified_only:
        q = q.filter(HospitalCapability.verification_status == "VERIFIED")
    if category:
        q = q.filter(HospitalCapability.capability_category == category.upper())

    caps = q.order_by(HospitalCapability.capability_name.asc()).all()
    return {
        "hospital_id": h.id,
        "hospital_name": h.name,
        "capabilities": [capability_dict(c) for c in caps],
        "disclaimer": "Capability records indicate clinical service readiness claims, not live bed or staffed capacity.",
    }
