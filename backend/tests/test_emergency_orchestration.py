"""Emergency Orchestration, Live Incident Intake, Clinical Handover & Regression Test Suite (Prompt 08).

Verifies:
1. Critical Gate (Prompt 07 regression): Concurrent acceptance race conditions, transaction rollback atomicity, and read-only GET endpoints.
2. SOS Initiation & Idempotency: Duplicate protection, role boundaries, location accuracy.
3. Live Incident Intake: Witness reports vs. clinician observations, provenance retention, corrections versioning.
4. Evidence-Grounded Clinical Handover: Structured non-diagnostic summary, missing data warnings, human approval gate, versioning.
5. Arrival & Handover Acknowledgement: Single reservation consumption, double-counting prevention, hospital acknowledgement.
"""
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.db import SessionLocal
from app.models import (
    ActivityLog,
    ClinicalHandover,
    Doctor,
    EmergencyCase,
    EmergencyIncidentReport,
    HandoverAcknowledgement,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    Patient,
    PatientClinicalFact,
    ClinicalProvenance,
    ReferralRequest,
    ReferralResponse,
    ResourceReservation,
    User,
)
from app.services import emergency_service, handover_service, referral_service, resource_service


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def orch_fixture(client):
    """
    Sets up a complete clinical emergency environment:
    - 1 Patient User + Patient Profile (with clinical facts and provenance)
    - 1 Family User linked to Patient
    - 1 Doctor User (Emergency Physician)
    - 2 Hospital Users & Institutions: Hospital Alpha and Hospital Beta
    - Fresh operational resources configured with usable capacity
    """
    import uuid
    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:6]

    # 1. Users with unique emails
    u_pat = User(email=f"orch_patient_{uid}@test.com", password_hash="h", full_name="John Emergency", role="patient")
    u_fam = User(email=f"orch_family_{uid}@test.com", password_hash="h", full_name="Mary Emergency", role="family")
    u_doc = User(email=f"orch_doc_{uid}@test.com", password_hash="h", full_name="Dr. Sarah Connor", role="doctor")
    u_hosp_alpha = User(email=f"orch_alpha_{uid}@test.com", password_hash="h", full_name="Alpha Triage Staff", role="hospital")
    u_hosp_beta = User(email=f"orch_beta_{uid}@test.com", password_hash="h", full_name="Beta Triage Staff", role="hospital")
    db.add_all([u_pat, u_fam, u_doc, u_hosp_alpha, u_hosp_beta])
    db.flush()

    # 2. Hospitals
    h_alpha = Hospital(name=f"Alpha Trauma Center {uid}", address="100 Medical Way", city="Metro", lat=18.52, lng=73.85, status="VERIFIED")
    h_beta = Hospital(name=f"Beta General Hospital {uid}", address="200 Health Ave", city="Metro", lat=18.54, lng=73.87, status="VERIFIED")
    db.add_all([h_alpha, h_beta])
    db.flush()

    u_hosp_alpha.hospital_id = h_alpha.id
    u_hosp_beta.hospital_id = h_beta.id

    # 3. Patient Profile
    patient = Patient(
        user_id=u_pat.id,
        dob="1978-04-12",
        gender="M",
        blood_group="O+",
        address="321 Main St",
        family_code=f"O{uid}".upper()[:10],
    )
    db.add(patient)
    db.flush()
    u_fam.linked_patient_id = patient.id

    # 4. Doctor Profile
    doctor = Doctor(user_id=u_doc.id, hospital_id=h_alpha.id, specialty="Emergency Medicine", is_available=True)
    db.add(doctor)
    db.flush()

    # 5. Patient Clinical Facts & Provenance
    fact_htn = PatientClinicalFact(
        patient_id=patient.id,
        fact_type="CONDITION",
        fact_code="I10",
        fact_value="Essential Hypertension",
        clinical_status="ACTIVE",
    )
    db.add(fact_htn)
    db.flush()

    prov = ClinicalProvenance(
        clinical_fact_id=fact_htn.id,
        source_type="DOCTOR_VERIFIED",
        source_reference="Cardiology Consult 2024",
        source_excerpt="Patient treated for chronic primary hypertension.",
        verification_status="VERIFIED",
    )
    db.add(prov)

    # 6. Departments & Operational Resources (10 usable ICU beds each)
    dept_alpha = HospitalDepartment(hospital_id=h_alpha.id, department_name="Emergency Dept", department_code="ED")
    dept_beta = HospitalDepartment(hospital_id=h_beta.id, department_name="Emergency Dept", department_code="ED")
    db.add_all([dept_alpha, dept_beta])
    db.flush()

    res_alpha = HospitalResource(
        hospital_id=h_alpha.id,
        department_id=dept_alpha.id,
        resource_type="ICU_BED",
        total=10,
        available=8,
        staffed_capacity=10,
        occupied_count=2,
        maintenance_count=0,
        operational_status="FUNCTIONAL",
        last_verified_at=now - timedelta(minutes=10),
        freshness_window_minutes=60,
    )
    res_beta = HospitalResource(
        hospital_id=h_beta.id,
        department_id=dept_beta.id,
        resource_type="ICU_BED",
        total=10,
        available=7,
        staffed_capacity=10,
        occupied_count=3,
        maintenance_count=0,
        operational_status="FUNCTIONAL",
        last_verified_at=now - timedelta(minutes=10),
        freshness_window_minutes=60,
    )
    db.add_all([res_alpha, res_beta])
    db.commit()

    # Generate Auth Tokens
    from app.security import create_token
    token_pat = create_token(u_pat)
    token_fam = create_token(u_fam)
    token_doc = create_token(u_doc)
    token_alpha = create_token(u_hosp_alpha)
    token_beta = create_token(u_hosp_beta)

    return {
        "db": db,
        "u_pat": u_pat,
        "u_fam": u_fam,
        "u_doc": u_doc,
        "u_alpha": u_hosp_alpha,
        "u_beta": u_hosp_beta,
        "patient": patient,
        "h_alpha": h_alpha,
        "h_beta": h_beta,
        "token_pat": token_pat,
        "token_fam": token_fam,
        "token_doc": token_doc,
        "token_alpha": token_alpha,
        "token_beta": token_beta,
    }


# ==============================================================================
# SECTION 1: CRITICAL GATE — PROMPT 07 REGRESSION TESTS
# ==============================================================================

def test_critical_gate_read_only_get_referral_detail(client, orch_fixture):
    """
    CRITICAL GATE 3.3:
    Verify that GET /api/hospital/referrals/{id} is strictly read-only and does NOT
    change status from SENT to REVIEWING.
    Verify that POST /api/hospital/referrals/{id}/review explicitly transitions it to REVIEWING.
    """
    db = SessionLocal()
    patient = orch_fixture["patient"]
    h_alpha = orch_fixture["h_alpha"]

    case = EmergencyCase(patient_id=patient.id, emergency_type="stroke", lat=18.52, lng=73.85, status="INITIATED")
    db.add(case)
    db.flush()

    ref = ReferralRequest(
        emergency_case_id=case.id,
        hospital_id=h_alpha.id,
        request_reference="GATE-REF-001",
        request_round=1,
        status="SENT",
        requested_resource_type="ICU_BED",
    )
    db.add(ref)
    db.commit()

    token_alpha = orch_fixture["token_alpha"]

    # 1. First GET: Status must remain SENT!
    resp1 = client.get(f"/api/hospital/referrals/{ref.id}", headers=_auth_header(token_alpha))
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "SENT"

    # 2. Second GET: Status must still remain SENT!
    resp2 = client.get(f"/api/hospital/referrals/{ref.id}", headers=_auth_header(token_alpha))
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "SENT"

    # 3. Explicit POST review action: Transitions to REVIEWING
    resp_review = client.post(f"/api/hospital/referrals/{ref.id}/review", headers=_auth_header(token_alpha))
    assert resp_review.status_code == 200
    assert resp_review.json()["status"] == "REVIEWING"

    # 4. Subsequent GET: Remains REVIEWING without further mutation
    resp3 = client.get(f"/api/hospital/referrals/{ref.id}", headers=_auth_header(token_alpha))
    assert resp3.status_code == 200
    assert resp3.json()["status"] == "REVIEWING"
    db.close()


def test_critical_gate_concurrent_acceptance_invariant(orch_fixture):
    """
    CRITICAL GATE 3.1:
    Concurrent acceptance test verifying Single Active Acceptance Invariant:
    - One emergency has pending referral requests to Hospital Alpha and Hospital Beta.
    - Both hospitals attempt acceptance.
    - Exactly ONE request becomes ACCEPTED with confirmed reservation.
    - The losing request raises 409 Conflict and is safely rolled back.
    - No resource capacity is double-counted.
    """
    db1 = SessionLocal()
    db2 = SessionLocal()
    patient = orch_fixture["patient"]
    h_alpha = orch_fixture["h_alpha"]
    h_beta = orch_fixture["h_beta"]

    case = EmergencyCase(patient_id=patient.id, emergency_type="cardiac", lat=18.52, lng=73.85, status="INITIATED")
    db1.add(case)
    db1.flush()

    ref_alpha = ReferralRequest(
        emergency_case_id=case.id,
        hospital_id=h_alpha.id,
        request_reference="GATE-CONC-ALPHA",
        request_round=1,
        status="SENT",
        requested_resource_type="ICU_BED",
        response_deadline=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    ref_beta = ReferralRequest(
        emergency_case_id=case.id,
        hospital_id=h_beta.id,
        request_reference="GATE-CONC-BETA",
        request_round=1,
        status="SENT",
        requested_resource_type="ICU_BED",
        response_deadline=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db1.add_all([ref_alpha, ref_beta])
    db1.commit()

    u_alpha = db1.get(User, orch_fixture["u_alpha"].id)
    u_beta = db2.get(User, orch_fixture["u_beta"].id)

    # 1. Hospital Alpha accepts first
    accepted_alpha = referral_service.accept_referral(db=db1, referral_id=ref_alpha.id, responding_user=u_alpha)
    assert accepted_alpha.status == "ACCEPTED"
    assert accepted_alpha.is_active_acceptance is True

    # 2. Hospital Beta attempts acceptance on same emergency case -> MUST raise 409 Conflict!
    with pytest.raises(HTTPException) as exc_info:
        referral_service.accept_referral(db=db2, referral_id=ref_beta.id, responding_user=u_beta)
    assert exc_info.value.status_code == 409

    # 3. Verify exactly ONE accepted referral in database
    db_verify = SessionLocal()
    accepted_refs = (
        db_verify.query(ReferralRequest)
        .filter(ReferralRequest.emergency_case_id == case.id, ReferralRequest.status == "ACCEPTED")
        .all()
    )
    assert len(accepted_refs) == 1
    assert accepted_refs[0].hospital_id == h_alpha.id

    # 4. Verify exactly ONE reservation confirmed
    reservations = (
        db_verify.query(ResourceReservation)
        .filter(ResourceReservation.reservation_status == "CONFIRMED")
        .all()
    )
    case_reservations = [r for r in reservations if r.referral_request_id in (ref_alpha.id, ref_beta.id)]
    assert len(case_reservations) == 1
    assert case_reservations[0].referral_request_id == ref_alpha.id

    db1.close()
    db2.close()
    db_verify.close()


def test_critical_gate_acceptance_transaction_rollback(orch_fixture):
    """
    CRITICAL GATE 3.2:
    Verify that if reservation creation fails (e.g. non-existent resource),
    the referral is NOT left in ACCEPTED and emergency case hospital_id is NOT assigned.
    """
    db = SessionLocal()
    patient = orch_fixture["patient"]
    h_alpha = orch_fixture["h_alpha"]

    case = EmergencyCase(patient_id=patient.id, emergency_type="trauma", lat=18.52, lng=73.85, status="INITIATED")
    db.add(case)
    db.flush()

    # Request a non-existent resource type to induce reservation failure
    ref = ReferralRequest(
        emergency_case_id=case.id,
        hospital_id=h_alpha.id,
        request_reference="GATE-FAIL-001",
        request_round=1,
        status="SENT",
        requested_resource_type="HYPERBARIC_CHAMBER_NON_EXISTENT",
        response_deadline=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(ref)
    db.commit()

    u_alpha = db.get(User, orch_fixture["u_alpha"].id)

    with pytest.raises(HTTPException) as exc_info:
        referral_service.accept_referral(db=db, referral_id=ref.id, responding_user=u_alpha)
    assert exc_info.value.status_code == 409

    # Verify rollback: referral is still SENT, emergency case hospital_id is None
    db.refresh(ref)
    db.refresh(case)
    assert ref.status == "SENT"
    assert ref.is_active_acceptance is False
    assert case.hospital_id is None
    db.close()


# ==============================================================================
# SECTION 2: SOS INITIATION & IDEMPOTENCY
# ==============================================================================

def test_sos_initiation_and_idempotency(client, orch_fixture):
    token_pat = orch_fixture["token_pat"]

    payload = {
        "emergency_type": "cardiac",
        "symptoms": "Severe crushing chest pain radiating to left arm",
        "lat": 18.5300,
        "lng": 73.8500,
        "origin_type": "PATIENT_SOS",
        "location_source": "DEVICE_GPS",
        "location_accuracy_meters": 12.5,
        "idempotency_key": "sos-idemp-001",
    }

    # 1. Initial SOS
    resp1 = client.post("/api/emergency/sos", json=payload, headers=_auth_header(token_pat))
    assert resp1.status_code == 201, resp1.text
    data1 = resp1.json()
    case_id = data1["id"]
    assert data1["status"] in ("CREATED", "INITIATED")
    assert data1["origin_type"] == "PATIENT_SOS"

    # 2. Idempotent Retry: returns existing case without creating a second one
    resp2 = client.post("/api/emergency/sos", json=payload, headers=_auth_header(token_pat))
    assert resp2.status_code == 201
    assert resp2.json()["id"] == case_id

    # 3. Simultaneous separate SOS while case is active: MUST return 409 Conflict
    diff_payload = {
        "emergency_type": "stroke",
        "symptoms": "Facial droop",
        "lat": 18.5300,
        "lng": 73.8500,
        "idempotency_key": "sos-idemp-002",
    }
    resp3 = client.post("/api/emergency/sos", json=diff_payload, headers=_auth_header(token_pat))
    assert resp3.status_code == 409


def test_family_assisted_sos(client, orch_fixture):
    token_fam = orch_fixture["token_fam"]
    patient = orch_fixture["patient"]

    # Close any lingering cases for patient
    db = SessionLocal()
    for c in db.query(EmergencyCase).filter(EmergencyCase.patient_id == patient.id).all():
        c.status = "COMPLETED"
    db.commit()
    db.close()

    payload = {
        "emergency_type": "diabetic",
        "symptoms": "Patient unresponsive, blood glucose reading high",
        "lat": 18.5250,
        "lng": 73.8550,
        "origin_type": "FAMILY_ASSISTED",
        "patient_id": patient.id,
        "idempotency_key": "fam-sos-001",
    }

    resp = client.post("/api/emergency/sos", json=payload, headers=_auth_header(token_fam))
    assert resp.status_code == 201
    assert resp.json()["origin_type"] == "FAMILY_ASSISTED"


# ==============================================================================
# SECTION 3: LIVE INCIDENT INTAKE & PROVENANCE
# ==============================================================================

def test_incident_intake_and_corrections(client, orch_fixture):
    token_pat = orch_fixture["token_pat"]
    token_doc = orch_fixture["token_doc"]

    # Create case
    resp_sos = client.post(
        "/api/emergency/sos",
        json={"emergency_type": "trauma", "lat": 18.52, "lng": 73.85, "idempotency_key": "inc-test-sos-1"},
        headers=_auth_header(token_pat),
    )
    case_id = resp_sos.json()["id"]

    # 1. Bystander/Witness Incident Report
    rep_payload = {
        "reported_text": "Patient fell from bicycle onto pavement, possible head laceration.",
        "reporter_type": "BYSTANDER",
        "report_type": "OBSERVATION",
        "location_latitude": 18.521,
        "location_longitude": 73.852,
        "idempotency_key": "inc-rep-001",
    }
    resp_inc1 = client.post(f"/api/emergency/{case_id}/incidents", json=rep_payload, headers=_auth_header(token_pat))
    assert resp_inc1.status_code == 201
    inc1 = resp_inc1.json()
    assert inc1["verification_status"] == "UNVERIFIED"
    assert inc1["reporter_type"] == "BYSTANDER"

    # 2. Correction linked to parent report
    corr_payload = {
        "reported_text": "CORRECTION: Patient fell from motor scooter, not bicycle. Helmet was worn.",
        "reporter_type": "BYSTANDER",
        "report_type": "OBSERVATION",
        "idempotency_key": "inc-corr-001",
    }
    resp_corr = client.post(
        f"/api/emergency/{case_id}/incidents/{inc1['id']}/corrections",
        json=corr_payload,
        headers=_auth_header(token_pat),
    )
    assert resp_corr.status_code == 201
    inc_corr = resp_corr.json()
    assert inc_corr["parent_report_id"] == inc1["id"]

    # 3. Doctor/Clinician Observation
    doc_payload = {
        "reported_text": "Glasgow Coma Scale: 14. Pupils equal and reactive. Neck immobilized.",
        "reporter_type": "DOCTOR",
        "report_type": "VITALS",
    }
    resp_doc = client.post(f"/api/emergency/{case_id}/incidents", json=doc_payload, headers=_auth_header(token_doc))
    assert resp_doc.status_code == 201
    assert resp_doc.json()["verification_status"] == "CLINICIAN_CONFIRMED"

    # 4. List all reports
    resp_list = client.get(f"/api/emergency/{case_id}/incidents", headers=_auth_header(token_pat))
    assert resp_list.status_code == 200
    assert len(resp_list.json()) >= 3


# ==============================================================================
# SECTION 4: EVIDENCE-GROUNDED CLINICAL HANDOVER ENGINE
# ==============================================================================

def test_clinical_handover_generation_and_approval_workflow(client, orch_fixture):
    token_pat = orch_fixture["token_pat"]
    token_doc = orch_fixture["token_doc"]
    token_fam = orch_fixture["token_fam"]

    # Create emergency case
    resp_sos = client.post(
        "/api/emergency/sos",
        json={"emergency_type": "cardiac", "lat": 18.52, "lng": 73.85, "symptoms": "Severe angina", "idempotency_key": "ho-sos-1"},
        headers=_auth_header(token_pat),
    )
    case_id = resp_sos.json()["id"]

    # Add witness incident report
    client.post(
        f"/api/emergency/{case_id}/incidents",
        json={"reported_text": "Patient clutching chest, broke into cold sweat", "reporter_type": "WITNESS"},
        headers=_auth_header(token_pat),
    )

    # 1. Generate Handover v1 (Doctor only)
    resp_gen = client.post(
        f"/api/emergency/{case_id}/handover/generate",
        json={"notes": "Pre-hospital clinical briefing generated"},
        headers=_auth_header(token_doc),
    )
    assert resp_gen.status_code == 201
    h1 = resp_gen.json()
    assert h1["version"] == 1
    assert h1["status"] == "PENDING_REVIEW"
    assert h1["is_current_approved"] is False

    data = h1["handover_data"]
    # Verify non-diagnostic disclaimer
    assert "EVIDENCE-GROUNDED INFORMATION HANDOVER ONLY" in data["non_diagnostic_disclaimer"]
    # Verify strict missing data warning (absence of records does NOT imply absence of allergies)
    assert any("NO DOCUMENTED ALLERGY RECORDS" in w for w in data["missing_and_uncertain_information"])
    # Verify historical clinical fact is included with provenance
    assert len(data["historical_medical_context"]["clinical_facts"]) >= 1

    # 2. Doctor Approval Gate
    resp_appr = client.post(
        f"/api/emergency/{case_id}/handover/{h1['id']}/approve",
        json={"approval_notes": "Reviewed and verified against telemetry"},
        headers=_auth_header(token_doc),
    )
    assert resp_appr.status_code == 200
    assert resp_appr.json()["status"] == "APPROVED"
    assert resp_appr.json()["is_current_approved"] is True

    # 3. Family View Redaction Check
    resp_fam = client.get(f"/api/emergency/{case_id}/handover/{h1['id']}", headers=_auth_header(token_fam))
    assert resp_fam.status_code == 200
    assert resp_fam.json()["handover_data"]["status"] == "Redacted for family view per patient privacy consent"

    # 4. New Incident Update triggers version 2
    client.post(
        f"/api/emergency/{case_id}/incidents",
        json={"reported_text": "Patient vomited once in transit", "reporter_type": "AMBULANCE"},
        headers=_auth_header(token_doc),
    )
    resp_gen2 = client.post(
        f"/api/emergency/{case_id}/handover/generate",
        json={"notes": "Updated for transit emesis"},
        headers=_auth_header(token_doc),
    )
    assert resp_gen2.status_code == 201
    h2 = resp_gen2.json()
    assert h2["version"] == 2
    assert h2["status"] == "PENDING_REVIEW"

    # Approving v2 marks v1 as SUPERSEDED
    client.post(f"/api/emergency/{case_id}/handover/{h2['id']}/approve", headers=_auth_header(token_doc))
    resp_v1_check = client.get(f"/api/emergency/{case_id}/handover/{h1['id']}", headers=_auth_header(token_doc))
    assert resp_v1_check.json()["status"] == "SUPERSEDED"
    assert resp_v1_check.json()["is_current_approved"] is False


# ==============================================================================
# SECTION 5: ARRIVAL, RESERVATION CONSUMPTION & HANDOVER ACKNOWLEDGEMENT
# ==============================================================================

def test_arrival_consumption_and_handover_acknowledgement(client, orch_fixture):
    db = SessionLocal()
    patient = orch_fixture["patient"]
    h_alpha = orch_fixture["h_alpha"]
    token_alpha = orch_fixture["token_alpha"]
    token_beta = orch_fixture["token_beta"]
    token_doc = orch_fixture["token_doc"]

    # 1. Setup emergency case with accepted referral & confirmed reservation
    case = EmergencyCase(
        patient_id=patient.id,
        emergency_type="stroke",
        hospital_id=h_alpha.id,
        lat=18.52,
        lng=73.85,
        status="ACCEPTED",
    )
    db.add(case)
    db.flush()

    ref = ReferralRequest(
        emergency_case_id=case.id,
        hospital_id=h_alpha.id,
        request_reference="ARRIV-REF-001",
        status="ACCEPTED",
        is_active_acceptance=True,
    )
    db.add(ref)
    db.flush()

    res = (
        db.query(HospitalResource)
        .filter(HospitalResource.hospital_id == h_alpha.id, HospitalResource.resource_type == "ICU_BED")
        .first()
    )
    initial_occupied = res.occupied_count or 0

    reservation = ResourceReservation(
        referral_request_id=ref.id,
        hospital_resource_id=res.id,
        quantity=1,
        reservation_status="CONFIRMED",
        idempotency_key="res-arriv-test-1",
    )
    db.add(reservation)
    db.commit()

    # Generate and approve clinical handover
    handover = handover_service.generate_clinical_handover(db, case.id)
    u_doc = db.get(User, orch_fixture["u_doc"].id)
    handover_service.approve_clinical_handover(db, handover.id, u_doc)
    db.close()

    # 2. Unauthorized Hospital Beta cannot record arrival
    resp_bad = client.post(f"/api/emergency/{case.id}/arrival", headers=_auth_header(token_beta))
    assert resp_bad.status_code == 403

    # 3. Authorized Hospital Alpha records arrival
    resp_arriv1 = client.post(
        f"/api/emergency/{case.id}/arrival",
        json={"remarks": "Ambulance arrived at Emergency Bay 2"},
        headers=_auth_header(token_alpha),
    )
    assert resp_arriv1.status_code == 200
    assert resp_arriv1.json()["status"] == "ARRIVED"

    # Verify reservation consumed and occupancy incremented exactly once
    db_check = SessionLocal()
    res_after = db_check.get(HospitalResource, res.id)
    assert res_after.occupied_count == initial_occupied + 1
    resv_after = db_check.get(ResourceReservation, reservation.id)
    assert resv_after.reservation_status == "CONSUMED"

    # 4. Idempotent Arrival Retry: Does NOT consume reservation twice or increment occupancy twice!
    resp_arriv2 = client.post(f"/api/emergency/{case.id}/arrival", headers=_auth_header(token_alpha))
    assert resp_arriv2.status_code == 200
    db_check.refresh(res_after)
    assert res_after.occupied_count == initial_occupied + 1  # Unchanged!

    # 5. Handover Acknowledgement
    ack_payload = {
        "handover_id": handover.id,
        "operational_remarks": "Received by Dr. Miller on shift. Stroke team assembled.",
    }
    resp_ack = client.post(
        f"/api/emergency/{case.id}/handover/acknowledge",
        json=ack_payload,
        headers=_auth_header(token_alpha),
    )
    assert resp_ack.status_code == 201
    ack_data = resp_ack.json()
    assert ack_data["status"] == "ACKNOWLEDGED"
    assert ack_data["handover_id"] == handover.id
    db_check.close()
