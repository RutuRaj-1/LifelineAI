"""Unit and integration tests for Multi-Hospital Referral Engine, Broadcasting, and Acceptance Coordination (Prompt 07)."""
from datetime import datetime, timezone, timedelta
import uuid
import pytest
from app.db import SessionLocal
from app.models import (
    EmergencyCase,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    Patient,
    ReferralRequest,
    ReferralResponse,
    ResourceReservation,
    User,
)
from app.security import create_token, hash_password
from fastapi import HTTPException
from app.services import referral_service, resource_service


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def referral_fixture(client):
    """Sets up a realistic referral environment with an active emergency case and two hospitals."""
    db = SessionLocal()
    u = uuid.uuid4().hex[:6]

    # Hospital Alpha (Verified, active department, fresh ICU bed)
    h_alpha = Hospital(
        name=f"Alpha General Hospital {u}",
        address="100 Alpha Way",
        city="Pune",
        lat=18.5204,
        lng=73.8567,
        phone="+91-20-11112222",
        status="VERIFIED",
        hospital_type="TERTIARY_CARE",
        contact_email=f"alpha_{u}@hospital.demo",
    )
    # Hospital Beta (Verified, active department, stale ICU bed)
    h_beta = Hospital(
        name=f"Beta Medical Center {u}",
        address="200 Beta Road",
        city="Pune",
        lat=18.5300,
        lng=73.8400,
        phone="+91-20-33334444",
        status="VERIFIED",
        hospital_type="GENERAL",
        contact_email=f"beta_{u}@hospital.demo",
    )
    db.add_all([h_alpha, h_beta])
    db.flush()

    # Staff for Alpha
    staff_alpha = User(
        email=f"staff_alpha_{u}@hospital.demo",
        password_hash=hash_password("Pass123!"),
        full_name="Nurse Alpha",
        role="hospital",
        hospital_id=h_alpha.id,
    )
    # Staff for Beta
    staff_beta = User(
        email=f"staff_beta_{u}@hospital.demo",
        password_hash=hash_password("Pass123!"),
        full_name="Dr Beta",
        role="hospital",
        hospital_id=h_beta.id,
    )
    # Emergency Coordinator / Doctor
    coordinator = User(
        email=f"coordinator_{u}@ems.gov",
        password_hash=hash_password("Pass123!"),
        full_name="Dr Coordinator",
        role="doctor",
    )
    # Patient
    user_patient = User(
        email=f"patient_{u}@example.com",
        password_hash=hash_password("Pass123!"),
        full_name="Emergency Patient",
        role="patient",
    )
    db.add_all([staff_alpha, staff_beta, coordinator, user_patient])
    db.flush()

    # Patient record
    patient = Patient(
        user_id=user_patient.id,
        gender="M",
        blood_group="A+",
        family_code=f"FAM-{u.upper()}",
    )
    db.add(patient)
    db.flush()

    # Departments
    dept_alpha = HospitalDepartment(
        hospital_id=h_alpha.id,
        department_name="Emergency & Critical Care",
        department_code="ICU",
        operational_status="ACTIVE",
    )
    dept_beta = HospitalDepartment(
        hospital_id=h_beta.id,
        department_name="Critical Care",
        department_code="ICU",
        operational_status="ACTIVE",
    )
    db.add_all([dept_alpha, dept_beta])
    db.flush()

    # Capabilities
    cap_alpha = HospitalCapability(
        hospital_id=h_alpha.id,
        department_id=dept_alpha.id,
        capability_code="CARDIAC_ICU",
        capability_name="Cardiac Critical Care",
        capability_category="CRITICAL_CARE",
        verification_status="VERIFIED",
    )
    db.add(cap_alpha)
    db.flush()

    now = datetime.now(timezone.utc)

    # Resources: Alpha is FRESH with 10 usable
    res_alpha = HospitalResource(
        hospital_id=h_alpha.id,
        resource_type="ICU_BED",
        total=15,
        available=10,
        staffed_capacity=12,
        occupied_count=2,
        maintenance_count=0,
        operational_status="FUNCTIONAL",
        last_verified_at=now - timedelta(minutes=15),
        freshness_window_minutes=60,
    )
    # Resources: Beta is STALE (last verified 4 hours ago, window is 60m)
    res_beta = HospitalResource(
        hospital_id=h_beta.id,
        resource_type="ICU_BED",
        total=10,
        available=5,
        staffed_capacity=8,
        occupied_count=3,
        maintenance_count=0,
        operational_status="FUNCTIONAL",
        last_verified_at=now - timedelta(hours=4),
        freshness_window_minutes=60,
    )
    db.add_all([res_alpha, res_beta])
    db.flush()

    # Active Emergency Case (in transit, unassigned hospital)
    case = EmergencyCase(
        patient_id=patient.id,
        hospital_id=None,
        doctor_id=None,
        emergency_type="CARDIAC",
        specialty="CARDIAC_ICU",
        priority=1,
        status="IN_TRANSIT",
        lat=18.5204,
        lng=73.8567,
    )
    db.add(case)
    db.commit()

    token_alpha = create_token(staff_alpha)
    token_beta = create_token(staff_beta)
    token_coord = create_token(coordinator)
    token_pat = create_token(user_patient)

    data = {
        "h_alpha_id": h_alpha.id,
        "h_beta_id": h_beta.id,
        "case_id": case.id,
        "patient_id": patient.id,
        "res_alpha_id": res_alpha.id,
        "res_beta_id": res_beta.id,
        "token_alpha": token_alpha,
        "token_beta": token_beta,
        "token_coord": token_coord,
        "token_pat": token_pat,
    }
    db.close()
    return data


# ==============================================================================
# TEST 1: Hospital Eligibility Discovery
# ==============================================================================
def test_referral_eligibility_discovery(client, referral_fixture):
    token = referral_fixture["token_coord"]
    case_id = referral_fixture["case_id"]

    resp = client.get(
        f"/api/emergency/{case_id}/referral-eligibility?requested_resource_type=ICU_BED",
        headers=_auth_header(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["emergency_case_id"] == case_id
    assert len(data["eligible_hospitals"]) >= 2

    # Find Alpha and Beta in results
    h_alpha = next(h for h in data["eligible_hospitals"] if h["hospital_id"] == referral_fixture["h_alpha_id"])
    h_beta = next(h for h in data["eligible_hospitals"] if h["hospital_id"] == referral_fixture["h_beta_id"])

    # Alpha is verified, capability verified, fresh operational resource -> ELIGIBLE
    assert h_alpha["is_eligible"] is True
    assert h_alpha["eligibility_status"] == "ELIGIBLE"
    assert h_alpha["resource_summary"]["is_confirmed_fresh"] is True
    assert h_alpha["resource_summary"]["usable_capacity"] == 10

    # Beta has STALE resource -> RESOURCE_STALE
    assert h_beta["is_eligible"] is False
    assert h_beta["eligibility_status"] == "RESOURCE_STALE"
    assert h_beta["resource_summary"]["is_confirmed_fresh"] is False


# ==============================================================================
# TEST 2: Multi-Hospital Referral Broadcasting & Idempotency
# ==============================================================================
def test_broadcast_referrals_and_idempotency(client, referral_fixture):
    token = referral_fixture["token_coord"]
    case_id = referral_fixture["case_id"]
    alpha_id = referral_fixture["h_alpha_id"]
    beta_id = referral_fixture["h_beta_id"]

    payload = {
        "hospital_ids": [alpha_id, beta_id],
        "requested_resource_type": "ICU_BED",
        "priority": 1,
        "notes": "Severe STEMI in transit, cardiac ICU bed requested.",
        "response_timeout_minutes": 20,
        "idempotency_key": "idemp-broadcast-test-1",
    }

    # First Broadcast
    resp = client.post(
        f"/api/emergency/{case_id}/referrals",
        json=payload,
        headers=_auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["dispatched_count"] == 2
    refs = data["referrals"]
    assert len(refs) == 2
    ref_alpha = next(r for r in refs if r["hospital_id"] == alpha_id)
    ref_beta = next(r for r in refs if r["hospital_id"] == beta_id)
    assert ref_alpha["status"] == "SENT"
    assert ref_beta["status"] == "SENT"

    # Idempotent re-submission returns same referrals without creating duplicates
    resp_dup = client.post(
        f"/api/emergency/{case_id}/referrals",
        json=payload,
        headers=_auth_header(token),
    )
    assert resp_dup.status_code == 201
    assert resp_dup.json()["dispatched_count"] == 2


# ==============================================================================
# TEST 3: Hospital Inbox, Isolation & Reviewing Transition
# ==============================================================================
def test_hospital_inbox_and_isolation(client, referral_fixture):
    token_coord = referral_fixture["token_coord"]
    token_alpha = referral_fixture["token_alpha"]
    token_beta = referral_fixture["token_beta"]
    case_id = referral_fixture["case_id"]
    alpha_id = referral_fixture["h_alpha_id"]
    beta_id = referral_fixture["h_beta_id"]

    # Dispatch referrals
    client.post(
        f"/api/emergency/{case_id}/referrals",
        json={"hospital_ids": [alpha_id, beta_id], "requested_resource_type": "ICU_BED"},
        headers=_auth_header(token_coord),
    )

    # 1. Hospital Alpha checks incoming inbox
    inbox_alpha = client.get("/api/hospital/referrals/incoming", headers=_auth_header(token_alpha))
    assert inbox_alpha.status_code == 200
    items_alpha = inbox_alpha.json()["items"]
    assert len(items_alpha) == 1
    ref_alpha_id = items_alpha[0]["id"]
    assert items_alpha[0]["hospital_id"] == alpha_id

    # 2. Hospital Beta checks incoming inbox (only sees its own)
    inbox_beta = client.get("/api/hospital/referrals/incoming", headers=_auth_header(token_beta))
    assert inbox_beta.status_code == 200
    items_beta = inbox_beta.json()["items"]
    assert len(items_beta) == 1
    ref_beta_id = items_beta[0]["id"]
    assert items_beta[0]["hospital_id"] == beta_id

    # 3. Cross-Hospital Isolation: Alpha CANNOT view Beta's referral detail
    bad_view = client.get(f"/api/hospital/referrals/{ref_beta_id}", headers=_auth_header(token_alpha))
    assert bad_view.status_code == 404

    # 4. Opening referral detail transitions status from SENT to REVIEWING
    detail_resp = client.get(f"/api/hospital/referrals/{ref_alpha_id}", headers=_auth_header(token_alpha))
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "REVIEWING"


# ==============================================================================
# TEST 4: Clarification Workflow (Hospital -> Doctor -> Hospital)
# ==============================================================================
def test_referral_clarification_roundtrip(client, referral_fixture):
    token_coord = referral_fixture["token_coord"]
    token_alpha = referral_fixture["token_alpha"]
    case_id = referral_fixture["case_id"]
    alpha_id = referral_fixture["h_alpha_id"]

    # Dispatch
    disp = client.post(
        f"/api/emergency/{case_id}/referrals",
        json={"hospital_ids": [alpha_id], "requested_resource_type": "ICU_BED"},
        headers=_auth_header(token_coord),
    )
    ref_id = disp.json()["referrals"][0]["id"]

    # Hospital asks clarification
    clar_resp = client.post(
        f"/api/hospital/referrals/{ref_id}/clarification",
        json={"question": "Has the patient received aspirin and ticagrelor?"},
        headers=_auth_header(token_alpha),
    )
    assert clar_resp.status_code == 200
    data = clar_resp.json()
    assert data["status"] == "CLARIFICATION_REQUIRED"
    assert "ticagrelor" in data["clarification_notes"]

    # Coordinator answers clarification
    ans_resp = client.post(
        f"/api/referrals/{ref_id}/clarifications/respond",
        json={"answer": "Yes, 300mg aspirin and 180mg ticagrelor administered at 14:10."},
        headers=_auth_header(token_coord),
    )
    assert ans_resp.status_code == 200
    ans_data = ans_resp.json()
    assert ans_data["status"] == "REVIEWING"
    assert "administered" in ans_data["clarification_notes"]


# ==============================================================================
# TEST 5: Explicit Acceptance, Resource Reservation & Single Acceptance Invariant
# ==============================================================================
def test_explicit_acceptance_and_single_accepted_invariant(client, referral_fixture):
    token_coord = referral_fixture["token_coord"]
    token_alpha = referral_fixture["token_alpha"]
    token_beta = referral_fixture["token_beta"]
    case_id = referral_fixture["case_id"]
    alpha_id = referral_fixture["h_alpha_id"]
    beta_id = referral_fixture["h_beta_id"]

    # Dispatch to both Alpha and Beta
    disp = client.post(
        f"/api/emergency/{case_id}/referrals",
        json={"hospital_ids": [alpha_id, beta_id], "requested_resource_type": "ICU_BED"},
        headers=_auth_header(token_coord),
    )
    refs = disp.json()["referrals"]
    ref_alpha_id = next(r["id"] for r in refs if r["hospital_id"] == alpha_id)
    ref_beta_id = next(r["id"] for r in refs if r["hospital_id"] == beta_id)

    # 1. Attempting to accept on STALE resource (Beta) fails safely with 409
    bad_beta_accept = client.post(
        f"/api/hospital/referrals/{ref_beta_id}/accept",
        json={"notes": "Trying to accept despite stale bed count"},
        headers=_auth_header(token_beta),
    )
    assert bad_beta_accept.status_code == 409
    assert "stale" in bad_beta_accept.text.lower()

    # 2. Hospital Alpha accepts (fresh resource, usable capacity > 0)
    accept_alpha = client.post(
        f"/api/hospital/referrals/{ref_alpha_id}/accept",
        json={"notes": "Cath lab prepared, Cardiac ICU bed 4 reserved."},
        headers=_auth_header(token_alpha),
    )
    assert accept_alpha.status_code == 200, accept_alpha.text
    data = accept_alpha.json()
    assert data["status"] == "ACCEPTED"
    assert data["is_active_acceptance"] is True

    # Verify reservation created and confirmed
    db = SessionLocal()
    resv = db.query(ResourceReservation).filter_by(referral_request_id=ref_alpha_id).first()
    assert resv is not None
    assert resv.reservation_status == "CONFIRMED"
    # Verify EmergencyCase updated
    case = db.get(EmergencyCase, case_id)
    assert case.hospital_id == alpha_id
    assert case.status == "ACCEPTED"
    db.close()

    # 3. Single Active Acceptance Invariant: Hospital Beta now CANNOT accept (409 Conflict)
    # Even if Beta attests its resource now to become fresh:
    db = SessionLocal()
    res_b = db.get(HospitalResource, referral_fixture["res_beta_id"])
    res_b.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.close()

    conflict_accept = client.post(
        f"/api/hospital/referrals/{ref_beta_id}/accept",
        json={"notes": "Beta attempting concurrent acceptance"},
        headers=_auth_header(token_beta),
    )
    assert conflict_accept.status_code == 409
    assert "already accepted" in conflict_accept.text.lower()


# ==============================================================================
# TEST 6: Decline Workflow
# ==============================================================================
def test_hospital_decline_workflow(client, referral_fixture):
    token_coord = referral_fixture["token_coord"]
    token_beta = referral_fixture["token_beta"]
    case_id = referral_fixture["case_id"]
    beta_id = referral_fixture["h_beta_id"]

    # Dispatch
    disp = client.post(
        f"/api/emergency/{case_id}/referrals",
        json={"hospital_ids": [beta_id], "requested_resource_type": "ICU_BED"},
        headers=_auth_header(token_coord),
    )
    ref_id = disp.json()["referrals"][0]["id"]

    # Decline
    dec_resp = client.post(
        f"/api/hospital/referrals/{ref_id}/decline",
        json={"reason_code": "NO_BEDS", "notes": "All critical beds occupied."},
        headers=_auth_header(token_beta),
    )
    assert dec_resp.status_code == 200
    data = dec_resp.json()
    assert data["status"] == "DECLINED"
    assert data["decline_reason_code"] == "NO_BEDS"

    # Terminal state: cannot accept after declining
    cannot_accept = client.post(
        f"/api/hospital/referrals/{ref_id}/accept",
        json={"notes": "Changing mind"},
        headers=_auth_header(token_beta),
    )
    assert cannot_accept.status_code == 400


# ==============================================================================
# TEST 7: Cancellation & Reservation Release
# ==============================================================================
def test_referral_cancellation_and_reservation_release(client, referral_fixture):
    token_coord = referral_fixture["token_coord"]
    token_alpha = referral_fixture["token_alpha"]
    case_id = referral_fixture["case_id"]
    alpha_id = referral_fixture["h_alpha_id"]

    # Dispatch & Accept
    disp = client.post(
        f"/api/emergency/{case_id}/referrals",
        json={"hospital_ids": [alpha_id], "requested_resource_type": "ICU_BED"},
        headers=_auth_header(token_coord),
    )
    ref_id = disp.json()["referrals"][0]["id"]
    client.post(f"/api/hospital/referrals/{ref_id}/accept", json={}, headers=_auth_header(token_alpha))

    # Cancel referral by coordinator
    cancel_resp = client.post(
        f"/api/referrals/{ref_id}/cancel",
        json={"reason": "Patient diverted to specialized trauma center upon EMS re-evaluation."},
        headers=_auth_header(token_coord),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "CANCELLED"

    # Verify reservation was released
    db = SessionLocal()
    resv = db.query(ResourceReservation).filter_by(referral_request_id=ref_id).first()
    assert resv is not None
    assert resv.reservation_status == "RELEASED"
    db.close()
