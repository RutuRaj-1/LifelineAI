"""Unit and integration tests for Live Resource Availability, Attestation, and Reservation Safety (Prompt 06)."""
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from app.db import SessionLocal
from app.models import (
    EmergencyCase,
    Hospital,
    HospitalResource,
    Patient,
    ReferralRequest,
    ResourceStatusHistory,
    ResourceReservation,
    User,
)
from app.security import create_token, hash_password
from fastapi import HTTPException
from app.services.resource_service import (
    calculate_usable_capacity,
    calculate_freshness,
    validate_resource_counts,
    attest_resource,
    create_reservation_hold,
    confirm_reservation,
    release_reservation,
    consume_reservation,
    expire_stale_reservations,
)


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def resource_fixture(client):
    """Sets up two isolated hospitals with staff, test resources, and patient case."""
    db = SessionLocal()
    u = uuid.uuid4().hex[:6]

    # Hospital 1
    h1 = Hospital(
        name=f"Metro General Hospital {u}",
        address="100 Main Street",
        city="Pune",
        lat=18.5204,
        lng=73.8567,
        phone="+91-20-11112222",
        status="VERIFIED",
        hospital_type="TERTIARY_CARE",
        contact_email=f"metro_{u}@hospital.demo",
    )
    # Hospital 2
    h2 = Hospital(
        name=f"Apex Memorial Hospital {u}",
        address="200 West Avenue",
        city="Mumbai",
        lat=19.0760,
        lng=72.8777,
        phone="+91-22-33334444",
        status="VERIFIED",
        hospital_type="GENERAL",
        contact_email=f"apex_{u}@hospital.demo",
    )
    db.add_all([h1, h2])
    db.flush()

    # Staff for Hospital 1
    u1 = User(
        email=f"staff1_{u}@metro.demo",
        password_hash=hash_password("Pass123!"),
        full_name="Staff One Metro",
        role="hospital",
        hospital_id=h1.id,
    )
    # Staff for Hospital 2
    u2 = User(
        email=f"staff2_{u}@apex.demo",
        password_hash=hash_password("Pass123!"),
        full_name="Staff Two Apex",
        role="hospital",
        hospital_id=h2.id,
    )
    # Ordinary Patient
    user_patient = User(
        email=f"patient_{u}@example.com",
        password_hash=hash_password("Pass123!"),
        full_name="Citizen Patient",
        role="patient",
    )
    db.add_all([u1, u2, user_patient])
    db.flush()

    pat = Patient(
        user_id=user_patient.id,
        gender="F",
        blood_group="O+",
        family_code=f"FAM-{u.upper()}",
    )
    db.add(pat)
    db.flush()

    case = EmergencyCase(
        patient_id=pat.id,
        hospital_id=h1.id,
        emergency_type="CARDIAC",
        priority="CRITICAL",
        status="IN_TRANSIT",
        lat=18.5204,
        lng=73.8567,
    )
    db.add(case)
    db.flush()

    ref_req = ReferralRequest(
        emergency_case_id=case.id,
        hospital_id=h1.id,
        request_reference=f"REF-{u.upper()}",
        status="PENDING",
    )
    db.add(ref_req)
    db.flush()

    # Initial resource for Hospital 1
    res1 = HospitalResource(
        hospital_id=h1.id,
        resource_type="ICU_BED",
        total=20,
        available=14,
        staffed_capacity=18,
        occupied_count=3,
        maintenance_count=1,
        operational_status="FUNCTIONAL",
        last_verified_at=datetime.now(timezone.utc),
        status_source="MANUAL_ATTESTATION",
        freshness_window_minutes=120,
    )
    db.add(res1)
    db.commit()

    t_h1 = create_token(u1)
    t_h2 = create_token(u2)
    t_pat = create_token(user_patient)

    h1_id = h1.id
    h2_id = h2.id
    res1_id = res1.id
    u1_id = u1.id
    ref_req_id = ref_req.id
    db.close()

    return {
        "h1_id": h1_id,
        "h2_id": h2_id,
        "res1_id": res1_id,
        "u1_id": u1_id,
        "ref_req_id": ref_req_id,
        "t_h1": t_h1,
        "t_h2": t_h2,
        "t_pat": t_pat,
    }


# ==============================================================================
# TEST 1: Capacity Calculation Formula Under All Conditions
# ==============================================================================
def test_capacity_calculation_formula(client, resource_fixture):
    db = SessionLocal()
    try:
        res = db.get(HospitalResource, resource_fixture["res1_id"])
        
        # Formula: usable_capacity = max(0, staffed - occupied - maintenance - holds)
        # 18 - 3 - 1 - 0 = 14
        usable = calculate_usable_capacity(res, active_holds=0)
        assert usable == 14

        # If maintenance increases: 18 - 3 - 10 = 5
        res.maintenance_count = 10
        assert calculate_usable_capacity(res, active_holds=0) == 5

        # If deductions exceed staffed capacity: floor at 0
        res.maintenance_count = 20
        assert calculate_usable_capacity(res, active_holds=0) == 0

        # If status is non-operational, usable is always 0
        res.maintenance_count = 1
        res.operational_status = "SUSPENDED"
        assert calculate_usable_capacity(res, active_holds=0) == 0
    finally:
        db.close()


# ==============================================================================
# TEST 2: Freshness Status Classification
# ==============================================================================
def test_freshness_classification(client, resource_fixture):
    db = SessionLocal()
    try:
        res = db.get(HospitalResource, resource_fixture["res1_id"])
        now = datetime.now(timezone.utc)

        # 1. Recent timestamp -> FRESH
        res.last_verified_at = now - timedelta(minutes=30)
        res.freshness_window_minutes = 120
        res.operational_status = "FUNCTIONAL"
        assert calculate_freshness(res, now=now) == "FRESH"

        # 2. Beyond threshold -> STALE
        res.last_verified_at = now - timedelta(hours=3)
        assert calculate_freshness(res, now=now) == "STALE"

        # 3. No timestamp -> UNKNOWN
        res.last_verified_at = None
        assert calculate_freshness(res, now=now) == "UNKNOWN"

        # 4. Closed / Suspended -> SUSPENDED
        res.operational_status = "CLOSED"
        assert calculate_freshness(res, now=now) == "SUSPENDED"
    finally:
        db.close()


# ==============================================================================
# TEST 3: Attestation Lifecycle & History Audit Trail
# ==============================================================================
def test_staff_attestation_lifecycle(client, resource_fixture):
    token = resource_fixture["t_h1"]
    res_id = resource_fixture["res1_id"]
    u1_id = resource_fixture["u1_id"]

    # Valid attestation payload
    payload = {
        "staffed_capacity": 16,
        "occupied_count": 5,
        "maintenance_count": 2,
        "operational_status": "FUNCTIONAL",
        "notes": "Shift turnover attestation by Charge Nurse",
    }
    resp = client.post(
        f"/api/hospital/resources/{res_id}/attest",
        json=payload,
        headers=_auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["staffed_capacity"] == 16
    assert data["occupied_count"] == 5
    assert data["maintenance_count"] == 2
    # usable_capacity = 16 - 5 - 2 - 0 = 9
    assert data["usable_capacity"] == 9
    assert data["available"] == 9
    assert data["freshness_status"] == "FRESH"

    # Check history endpoint
    hist_resp = client.get(
        f"/api/hospital/resources/{res_id}/history",
        headers=_auth_header(token),
    )
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["total"] >= 1
    latest_hist = hist_data["items"][0]
    assert latest_hist["new_available_count"] == 9
    assert latest_hist["verified_by_user_id"] == u1_id
    assert latest_hist["verification_source"] == "MANUAL"
    assert latest_hist["remarks"] == "Shift turnover attestation by Charge Nurse"

    # Invalid attestation: occupied + maintenance > staffed
    invalid_payload = {
        "staffed_capacity": 5,
        "occupied_count": 4,
        "maintenance_count": 3,  # sum = 7 > 5
    }
    bad_resp = client.post(
        f"/api/hospital/resources/{res_id}/attest",
        json=invalid_payload,
        headers=_auth_header(token),
    )
    assert bad_resp.status_code == 422


# ==============================================================================
# TEST 4: Reservation Lifecycle & Zero Double-Counting Safety
# ==============================================================================
def test_reservation_hold_confirm_release_consume(client, resource_fixture):
    db = SessionLocal()
    try:
        res = db.get(HospitalResource, resource_fixture["res1_id"])
        ref_id = resource_fixture["ref_req_id"]

        # Ensure clean initial state
        res.staffed_capacity = 16
        res.occupied_count = 5
        res.maintenance_count = 2
        res.operational_status = "FUNCTIONAL"
        db.commit()

        # Usable: 16 - 5 - 2 - 0 = 9
        assert calculate_usable_capacity(res, 0) == 9

        # 1. Create Hold (hold 3 beds for emergency inbound)
        hold, is_new = create_reservation_hold(
            db=db,
            hospital_resource_id=res.id,
            quantity=3,
            referral_request_id=ref_id,
            expires_in_minutes=15,
            idempotency_key="hold-tx-12345",
        )
        assert is_new is True
        assert hold.reservation_status == "HELD"
        db.refresh(res)
        # Usable capacity drops from 9 to 6
        assert res.available == 6

        # 2. Idempotent re-submission returns same hold without double deducting
        dup_hold, is_dup_new = create_reservation_hold(
            db=db,
            hospital_resource_id=res.id,
            quantity=3,
            referral_request_id=ref_id,
            expires_in_minutes=15,
            idempotency_key="hold-tx-12345",
        )
        assert is_dup_new is False
        assert dup_hold.id == hold.id
        db.refresh(res)
        assert res.available == 6

        # 3. Reject hold if requested quantity exceeds usable capacity
        with pytest.raises(HTTPException) as exc_info:
            create_reservation_hold(
                db=db,
                hospital_resource_id=res.id,
                quantity=10,  # Only 6 usable
                referral_request_id=ref_id,
                idempotency_key="hold-tx-excessive",
            )
        assert exc_info.value.status_code == 409

        # 4. Confirm Reservation
        confirmed = confirm_reservation(db, hold.id)
        assert confirmed.reservation_status == "CONFIRMED"

        # 5. Consume Reservation (patient arrives and is admitted)
        # Net capacity change must be ZERO: hold drops by 3, occupied increments by 3
        consumed = consume_reservation(db, hold.id)
        assert consumed.reservation_status == "CONSUMED"
        db.refresh(res)
        assert res.occupied_count == 8  # was 5 + 3
        # Usable capacity remains 6! (16 staffed - 8 occupied - 2 maintenance - 0 active holds = 6)
        assert res.available == 6

        # 6. Test Expiration of stale hold
        hold_to_expire, _ = create_reservation_hold(
            db=db,
            hospital_resource_id=res.id,
            quantity=2,
            referral_request_id=ref_id,
            expires_in_minutes=-5,  # already expired
            idempotency_key="hold-tx-expired-test",
        )
        # Expire stale holds
        expired_count = expire_stale_reservations(db)
        assert expired_count >= 1
        db.refresh(hold_to_expire)
        assert hold_to_expire.reservation_status == "EXPIRED"
        # Synchronize legacy available
        sync_usable = calculate_usable_capacity(res, 0)
        assert sync_usable == 6
    finally:
        db.close()


# ==============================================================================
# TEST 5: Authorization, Cross-Hospital Isolation & Public Projections
# ==============================================================================
def test_cross_hospital_authorization_and_public_discovery(client, resource_fixture):
    t_h1 = resource_fixture["t_h1"]
    t_h2 = resource_fixture["t_h2"]
    t_pat = resource_fixture["t_pat"]
    res1_id = resource_fixture["res1_id"]
    h1_id = resource_fixture["h1_id"]

    # 1. Hospital 1 staff can list own resources
    r1 = client.get("/api/hospital/resources", headers=_auth_header(t_h1))
    assert r1.status_code == 200
    assert len(r1.json()) >= 1

    # 2. Hospital 2 staff CANNOT attest or edit Hospital 1's resource (isolated by hospital_id)
    r2_attest = client.post(
        f"/api/hospital/resources/{res1_id}/attest",
        json={"staffed_capacity": 10},
        headers=_auth_header(t_h2),
    )
    assert r2_attest.status_code == 404

    # 3. Patient role cannot attest (403 Forbidden)
    r_patient_attest = client.post(
        f"/api/hospital/resources/{res1_id}/attest",
        json={"staffed_capacity": 10},
        headers=_auth_header(t_pat),
    )
    assert r_patient_attest.status_code == 403

    # 4. Public discovery endpoint safe projection
    pub_resp = client.get(f"/api/hospitals/{h1_id}/resources")
    assert pub_resp.status_code == 200
    pub_data = pub_resp.json()
    assert "resources" in pub_data
    assert len(pub_data["resources"]) >= 1
    pub_item = pub_data["resources"][0]
    # Check safe projections: returns usable_capacity, total, operational_status, freshness_status
    assert "usable_capacity" in pub_item
    assert "total" in pub_item
    assert "freshness_status" in pub_item
    # Internal audit notes not exposed
    assert "notes" not in pub_item or pub_item.get("notes") is None
