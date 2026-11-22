"""Centralized Operational Resource Availability & Reservation Service (Prompt 06).

Core Principle: A vacant resource is not automatically a usable resource.
Calculates usable capacity based on:
1. Physical capacity (total)
2. Staffed capacity (staffed_capacity)
3. Occupied units (occupied_count)
4. Maintenance units (maintenance_count)
5. Active reservation holds (HELD / CONFIRMED)
6. Operational status (FUNCTIONAL, LIMITED, MAINTENANCE, etc.)
7. Freshness window & attestation audit trail.
"""
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from ..events import hub
from ..models import HospitalResource, ResourceReservation, ResourceStatusHistory
from . import runner

logger = logging.getLogger("lifeline.resource_service")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def validate_resource_counts(
    total: int,
    staffed: int | None,
    occupied: int,
    maintenance: int,
) -> None:
    """Enforces non-negative constraints and operational feasibility rules."""
    if total < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Physical capacity (total) cannot be negative.")
    if occupied < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Occupied count cannot be negative.")
    if maintenance < 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Maintenance count cannot be negative.")
    if staffed is not None:
        if staffed < 0:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Staffed capacity cannot be negative.")
        if staffed > total:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Staffed capacity ({staffed}) cannot exceed physical capacity ({total}).",
            )
        effective_limit = staffed
    else:
        effective_limit = total

    if occupied + maintenance > effective_limit:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Occupied ({occupied}) + Maintenance ({maintenance}) exceeds effective capacity ({effective_limit}).",
        )


def calculate_freshness(resource: HospitalResource, now: datetime | None = None) -> str:
    """Classifies resource freshness: FRESH, STALE, UNKNOWN, or SUSPENDED."""
    if resource.operational_status in ("SUSPENDED", "CLOSED", "NON_OPERATIONAL"):
        return "SUSPENDED"
    if not resource.last_verified_at:
        return "UNKNOWN"

    current = now or utc_now()
    # Normalize timestamp if naive
    last_verified = resource.last_verified_at
    if last_verified.tzinfo is None:
        last_verified = last_verified.replace(tzinfo=timezone.utc)

    window_minutes = resource.freshness_window_minutes or 60
    age_seconds = (current - last_verified).total_seconds()
    if age_seconds <= window_minutes * 60:
        return "FRESH"
    return "STALE"


def expire_stale_reservations(db: Session, resource_id: int | None = None) -> int:
    """
    Finds and expires active HELD reservations whose expiry window has elapsed.
    Idempotent and safe to run on demand or before capacity calculation.
    """
    now = utc_now()
    q = db.query(ResourceReservation).filter(
        ResourceReservation.reservation_status == "HELD",
        ResourceReservation.expires_at.isnot(None),
        ResourceReservation.expires_at < now,
    )
    if resource_id:
        q = q.filter(ResourceReservation.hospital_resource_id == resource_id)

    stale_holds = q.all()
    count = 0
    for hold in stale_holds:
        hold.reservation_status = "EXPIRED"
        hold.updated_at = now
        count += 1

    if count > 0:
        db.flush()
    return count


def get_active_reserved_holds(db: Session, resource_id: int) -> int:
    """
    Calculates active held units consuming capacity.
    Active holds include 'HELD' (not expired) and 'CONFIRMED' (awaiting consumption).
    'RELEASED', 'EXPIRED', and 'CONSUMED' do not consume reservation holds.
    """
    # Clean up stale holds first
    expire_stale_reservations(db, resource_id)

    holds_sum = (
        db.query(func.coalesce(func.sum(ResourceReservation.quantity), 0))
        .filter(
            ResourceReservation.hospital_resource_id == resource_id,
            ResourceReservation.reservation_status.in_(["HELD", "CONFIRMED"]),
        )
        .scalar()
    )
    return int(holds_sum or 0)


def calculate_usable_capacity(resource: HospitalResource, active_holds: int = 0) -> int:
    """
    Central operational availability formula:
    usable_capacity = max(0, staffed_capacity - occupied_count - maintenance_count - active_reserved_holds)
    If operational status is non-operational or maintenance, usable capacity is 0.
    """
    if resource.operational_status in ("MAINTENANCE", "NON_OPERATIONAL", "UNSTAFFED", "CLOSED", "SUSPENDED"):
        return 0

    staffed = resource.staffed_capacity if resource.staffed_capacity is not None else resource.total
    occupied = resource.occupied_count or 0
    maintenance = resource.maintenance_count or 0

    usable = staffed - occupied - maintenance - active_holds
    return max(0, usable)


def sync_legacy_available(db: Session, resource: HospitalResource, active_holds: int | None = None) -> int:
    """
    Synchronizes the legacy 'available' column as a projection of derived usable capacity.
    Ensures backwards-compatibility for existing routing algorithms and client views.
    """
    if active_holds is None:
        active_holds = get_active_reserved_holds(db, resource.id)
    usable = calculate_usable_capacity(resource, active_holds)
    resource.available = usable
    return usable


def broadcast_resource_update(resource: HospitalResource, usable: int, freshness: str) -> None:
    """Publishes a RESOURCE_STATUS_UPDATED event over the WebSocket hub after commit."""
    try:
        info = {
            "hospital_id": resource.hospital_id,
            "patient_id": None,
        }
        data = {
            "resource_id": resource.id,
            "resource_type": resource.resource_type,
            "usable_capacity": usable,
            "operational_status": resource.operational_status,
            "freshness_status": freshness,
            "last_verified_at": resource.last_verified_at.isoformat() if resource.last_verified_at else None,
        }
        runner.spawn(hub.emit("RESOURCE_STATUS_UPDATED", info, **data))
    except Exception as exc:
        logger.warning(f"Could not broadcast resource update event: {exc}")


def attest_resource(
    db: Session,
    resource: HospitalResource,
    user_id: int,
    staffed_capacity: int | None,
    occupied_count: int,
    maintenance_count: int,
    operational_status: str,
    status_source: str = "MANUAL",
    remarks: str | None = None,
    freshness_window_minutes: int | None = None,
) -> HospitalResource:
    """
    Hospital staff attestation workflow.
    Validates counts, creates append-only audit history, recalculates availability,
    and updates the resource record transactionally.
    """
    validate_resource_counts(
        total=resource.total,
        staffed=staffed_capacity,
        occupied=occupied_count,
        maintenance=maintenance_count,
    )

    now = utc_now()
    active_holds = get_active_reserved_holds(db, resource.id)
    prev_usable = calculate_usable_capacity(resource, active_holds)
    prev_status = resource.operational_status

    # Apply proposed updates
    resource.staffed_capacity = staffed_capacity
    resource.occupied_count = occupied_count
    resource.maintenance_count = maintenance_count
    resource.operational_status = operational_status
    resource.status_source = status_source or "MANUAL"
    resource.last_verified_at = now
    resource.verified_by_user_id = user_id
    resource.updated_at = now
    if freshness_window_minutes:
        resource.freshness_window_minutes = freshness_window_minutes

    new_usable = calculate_usable_capacity(resource, active_holds)
    resource.available = new_usable

    # Append to immutable ResourceStatusHistory
    history_entry = ResourceStatusHistory(
        hospital_resource_id=resource.id,
        previous_status=prev_status,
        new_status=operational_status,
        previous_available_count=prev_usable,
        new_available_count=new_usable,
        verification_source=status_source or "MANUAL",
        verified_by_user_id=user_id,
        verified_at=now,
        remarks=remarks,
        created_at=now,
    )
    db.add(history_entry)
    db.commit()
    db.refresh(resource)

    freshness = calculate_freshness(resource, now)
    broadcast_resource_update(resource, new_usable, freshness)

    return resource


# --- Centralized Reservation Lifecycle Operations ---

def create_reservation_hold(
    db: Session,
    hospital_resource_id: int,
    quantity: int,
    idempotency_key: str,
    referral_request_id: int | None = None,
    expires_in_minutes: int = 15,
) -> tuple[ResourceReservation, bool]:
    """
    Atomically allocates an active hold on a hospital resource.
    Returns (reservation, is_new).
    - Enforces idempotency: repeated request with same key returns existing reservation.
    - Validates operational status and freshness.
    - Prevents over-reservation.
    """
    if quantity <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Reservation quantity must be greater than zero.")

    # 1. Idempotency Check
    existing = (
        db.query(ResourceReservation)
        .filter(ResourceReservation.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        return existing, False

    # 2. Acquire resource
    resource = db.get(HospitalResource, hospital_resource_id)
    if not resource:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Hospital resource not found.")

    freshness = calculate_freshness(resource)
    if freshness == "SUSPENDED" or resource.operational_status in ("MAINTENANCE", "CLOSED", "SUSPENDED"):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot reserve: resource {resource.resource_type} is currently {resource.operational_status}.",
        )

    # 3. Capacity calculation
    active_holds = get_active_reserved_holds(db, resource.id)
    usable = calculate_usable_capacity(resource, active_holds)

    if usable < quantity:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Insufficient operational capacity for {resource.resource_type}. Usable: {usable}, Requested: {quantity}.",
        )

    now = utc_now()
    expires_at = now + timedelta(minutes=expires_in_minutes)

    reservation = ResourceReservation(
        referral_request_id=referral_request_id,
        hospital_resource_id=resource.id,
        quantity=quantity,
        reservation_status="HELD",
        held_at=now,
        expires_at=expires_at,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    db.add(reservation)
    db.flush()

    # Synchronize legacy available
    resource.available = max(0, usable - quantity)
    db.commit()
    db.refresh(reservation)

    broadcast_resource_update(resource, resource.available, freshness)
    return reservation, True


def confirm_reservation(db: Session, reservation_id: int, user_id: int | None = None) -> ResourceReservation:
    """Confirms a held reservation, continuing to hold capacity until arrival."""
    res = db.get(ResourceReservation, reservation_id)
    if not res:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    if res.reservation_status not in ("HELD", "CONFIRMED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot confirm reservation in status: {res.reservation_status}",
        )

    res.reservation_status = "CONFIRMED"
    res.confirmed_at = utc_now()
    res.confirmed_by_user_id = user_id
    res.updated_at = utc_now()
    db.commit()
    db.refresh(res)
    return res


def release_reservation(db: Session, reservation_id: int, reason: str = "CANCELLED") -> ResourceReservation:
    """Releases an active hold, immediately returning capacity to usable pool."""
    res = db.get(ResourceReservation, reservation_id)
    if not res:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    if res.reservation_status in ("RELEASED", "EXPIRED"):
        return res

    was_active = res.reservation_status in ("HELD", "CONFIRMED")
    res.reservation_status = "RELEASED"
    res.released_at = utc_now()
    res.release_reason = reason
    res.updated_at = utc_now()
    db.flush()

    if was_active and res.hospital_resource:
        sync_legacy_available(db, res.hospital_resource)

    db.commit()
    db.refresh(res)
    return res


def consume_reservation(db: Session, reservation_id: int, user_id: int | None = None) -> ResourceReservation:
    """
    Transfers a reservation upon patient arrival:
    - Reservation status transitions to 'CONSUMED' (no longer counted as an active hold).
    - Resource 'occupied_count' increments by reservation quantity.
    - Net change to usable capacity is 0 (prevents double-counting).
    """
    res = db.get(ResourceReservation, reservation_id)
    if not res:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found.")
    if res.reservation_status == "CONSUMED":
        return res
    if res.reservation_status not in ("HELD", "CONFIRMED"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot consume reservation with status: {res.reservation_status}",
        )

    res.reservation_status = "CONSUMED"
    res.updated_at = utc_now()
    db.flush()

    # Shift from reservation hold to active occupancy
    if res.hospital_resource:
        res.hospital_resource.occupied_count = (res.hospital_resource.occupied_count or 0) + res.quantity
        res.hospital_resource.updated_at = utc_now()
        sync_legacy_available(db, res.hospital_resource)

    db.commit()
    db.refresh(res)
    return res
