from datetime import datetime, timedelta, timezone
from app.models import (
    ClinicalProvenance,
    Doctor,
    EmergencyCase,
    EmergencyIncidentReport,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    Patient,
    PatientClinicalFact,
    ReferralRequest,
    ReferralResponse,
    ResourceReservation,
    ResourceStatusHistory,
    SpecialistAvailability,
    User,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_hospital_department_and_capabilities_relationship(client):
    from app.db import SessionLocal
    db = SessionLocal()

    h = Hospital(
        name="Test Metro Hospital",
        address="Test Road, Pune",
        city="Pune",
        lat=18.52,
        lng=73.85,
    )
    db.add(h)
    db.flush()

    dept = HospitalDepartment(
        hospital_id=h.id,
        department_name="Emergency Medicine",
        department_code="EM_TEST",
        operational_status="ACTIVE",
    )
    db.add(dept)
    db.flush()

    cap = HospitalCapability(
        hospital_id=h.id,
        department_id=dept.id,
        capability_code="CT_TEST",
        capability_name="CT Scan",
        capability_category="DIAGNOSTIC",
        verification_status="VERIFIED",
    )
    db.add(cap)
    db.commit()

    # Verify relationships
    h_fetched = db.get(Hospital, h.id)
    assert len(h_fetched.departments) >= 1
    assert h_fetched.departments[0].department_code == "EM_TEST"
    assert len(h_fetched.departments[0].capabilities) >= 1
    assert h_fetched.departments[0].capabilities[0].capability_code == "CT_TEST"
    db.close()


def test_patient_clinical_facts_and_multiple_provenance(client):
    from app.db import SessionLocal
    db = SessionLocal()

    u = User(email="test_pat_fact@test.com", password_hash="hash", full_name="Fact Patient", role="patient")
    db.add(u)
    db.flush()
    p = Patient(user_id=u.id, family_code="FACT123")
    db.add(p)
    db.flush()

    # Fact: Atrial Fibrillation
    fact = PatientClinicalFact(
        patient_id=p.id,
        fact_type="CONDITION",
        fact_value="Atrial Fibrillation",
        clinical_status="ACTIVE",
    )
    db.add(fact)
    db.flush()

    # Provenance 1: Patient entered
    prov1 = ClinicalProvenance(
        clinical_fact_id=fact.id,
        source_type="PATIENT_ENTERED",
        source_reference="Registration form",
        verification_status="UNVERIFIED",
    )
    # Provenance 2: Doctor verified
    prov2 = ClinicalProvenance(
        clinical_fact_id=fact.id,
        source_type="DOCTOR_VERIFIED",
        source_reference="Clinical examination notes",
        verification_status="VERIFIED",
    )
    db.add_all([prov1, prov2])
    db.commit()

    p_fetched = db.get(Patient, p.id)
    assert len(p_fetched.clinical_facts) == 1
    stored_fact = p_fetched.clinical_facts[0]
    assert len(stored_fact.provenance_records) == 2
    sources = {pr.source_type for pr in stored_fact.provenance_records}
    assert sources == {"PATIENT_ENTERED", "DOCTOR_VERIFIED"}
    db.close()


def test_emergency_referral_and_reservation_chain(client):
    from app.db import SessionLocal
    db = SessionLocal()

    u = User(email="ref_pat@test.com", password_hash="hash", full_name="Ref Patient", role="patient")
    db.add(u)
    db.flush()
    p = Patient(user_id=u.id, family_code="REF123")
    db.add(p)
    h = Hospital(name="Ref Hospital", address="Addr", city="Pune", lat=18.5, lng=73.8)
    db.add(h)
    db.flush()

    c = EmergencyCase(
        patient_id=p.id,
        hospital_id=h.id,
        emergency_type="stroke",
        lat=18.5,
        lng=73.8,
        origin_type="PATIENT_SOS",
        referral_round=1,
    )
    db.add(c)
    db.flush()

    # Referral Request
    ref = ReferralRequest(
        emergency_case_id=c.id,
        hospital_id=h.id,
        request_reference="REF-TEST-001",
        request_round=1,
        status="ACCEPTED",
        is_active_acceptance=True,
    )
    db.add(ref)
    db.flush()

    # Referral Response
    resp = ReferralResponse(
        referral_request_id=ref.id,
        response_type="ACCEPT",
        response_notes="Ready for patient",
    )
    db.add(resp)

    # Resource & Reservation
    res = HospitalResource(hospital_id=h.id, resource_type="ER_BED", total=10, available=9)
    db.add(res)
    db.flush()

    reservation = ResourceReservation(
        referral_request_id=ref.id,
        hospital_resource_id=res.id,
        quantity=1,
        reservation_status="CONFIRMED",
        idempotency_key="IDEM-TEST-101",
    )
    db.add(reservation)

    # Incident Report
    incident = EmergencyIncidentReport(
        emergency_case_id=c.id,
        reporter_type="PATIENT",
        report_type="TEXT",
        reported_text="Sudden numbness in right arm",
    )
    db.add(incident)
    db.commit()

    # Verify relationships from EmergencyCase
    case_fetched = db.get(EmergencyCase, c.id)
    assert len(case_fetched.referral_requests) == 1
    assert case_fetched.referral_requests[0].request_reference == "REF-TEST-001"
    assert len(case_fetched.referral_requests[0].responses) == 1
    assert len(case_fetched.referral_requests[0].reservations) == 1
    assert case_fetched.referral_requests[0].reservations[0].quantity == 1
    assert len(case_fetched.incident_reports) == 1
    assert case_fetched.incident_reports[0].reported_text == "Sudden numbness in right arm"
    db.close()
