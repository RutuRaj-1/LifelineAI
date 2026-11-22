import pytest
from sqlalchemy.exc import IntegrityError
from app.models import EmergencyCase, Hospital, Patient, ReferralRequest, ReferralResponse, User


def test_multiple_referrals_and_single_accepted_integrity(client):
    """Verify that:
    1. An emergency can fan out to multiple hospitals (Hospital A, Hospital B).
    2. Only ONE referral for the same emergency can hold status = 'ACCEPTED'.
    3. Multiple emergencies can each have their own accepted referral.
    """
    from app.db import SessionLocal
    db = SessionLocal()

    u = User(email="ref_mult_user@test.com", password_hash="h", full_name="Multi User", role="patient")
    db.add(u)
    db.flush()
    p = Patient(user_id=u.id, family_code="MULT1")
    h1 = Hospital(name="Hospital Alpha", address="A1", city="Pune", lat=18.5, lng=73.8)
    h2 = Hospital(name="Hospital Beta", address="A2", city="Pune", lat=18.6, lng=73.9)
    db.add_all([p, h1, h2])
    db.flush()

    # Case 1
    c1 = EmergencyCase(patient_id=p.id, emergency_type="stroke", lat=18.5, lng=73.8)
    db.add(c1)
    db.flush()

    # Referral 1 to Hospital Alpha: SENT -> ACCEPTED
    ref1 = ReferralRequest(
        emergency_case_id=c1.id,
        hospital_id=h1.id,
        request_reference="REF-C1-H1",
        request_round=1,
        status="ACCEPTED",
        is_active_acceptance=True,
    )
    # Referral 2 to Hospital Beta: SENT -> DECLINED
    ref2 = ReferralRequest(
        emergency_case_id=c1.id,
        hospital_id=h2.id,
        request_reference="REF-C1-H2",
        request_round=1,
        status="DECLINED",
        decline_reason_code="NO_BEDS",
    )
    db.add_all([ref1, ref2])
    db.commit()

    # Multiple referrals successfully coexist
    refs_c1 = db.query(ReferralRequest).filter_by(emergency_case_id=c1.id).all()
    assert len(refs_c1) == 2

    # Integrity Check: Attempting to accept referral 2 while referral 1 is already ACCEPTED
    # must trigger the partial unique index uq_case_single_active_accepted!
    ref2.status = "ACCEPTED"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # If referral 1 transitions to CANCELLED or DECLINED, referral 2 CAN be ACCEPTED
    ref1_reload = db.query(ReferralRequest).filter_by(request_reference="REF-C1-H1").first()
    ref2_reload = db.query(ReferralRequest).filter_by(request_reference="REF-C1-H2").first()
    ref1_reload.status = "DECLINED"
    ref2_reload.status = "ACCEPTED"
    db.commit()
    assert ref2_reload.status == "ACCEPTED"

    # Case 2 for another patient can simultaneously have an ACCEPTED referral
    u2 = User(email="ref_mult2@test.com", password_hash="h", full_name="User 2", role="patient")
    db.add(u2)
    db.flush()
    p2 = Patient(user_id=u2.id, family_code="MULT2")
    db.add(p2)
    db.flush()
    c2 = EmergencyCase(patient_id=p2.id, emergency_type="cardiac", lat=18.5, lng=73.8)
    db.add(c2)
    db.flush()

    ref_c2 = ReferralRequest(
        emergency_case_id=c2.id,
        hospital_id=h1.id,
        request_reference="REF-C2-H1",
        status="ACCEPTED",
    )
    db.add(ref_c2)
    db.commit()
    assert ref_c2.status == "ACCEPTED"
    db.close()


def test_referral_history_preserved_on_status_change(client):
    from app.db import SessionLocal
    db = SessionLocal()

    u = User(email="ref_hist_user@test.com", password_hash="h", full_name="User Hist", role="patient")
    db.add(u)
    db.flush()
    p = Patient(user_id=u.id, family_code="HIST1")
    h = Hospital(name="Hospital Hist", address="A", city="Pune", lat=18.5, lng=73.8)
    db.add_all([p, h])
    db.flush()

    c = EmergencyCase(patient_id=p.id, emergency_type="trauma", lat=18.5, lng=73.8)
    db.add(c)
    db.flush()

    ref = ReferralRequest(
        emergency_case_id=c.id,
        hospital_id=h.id,
        request_reference="REF-HIST-01",
        status="REVIEWING",
    )
    db.add(ref)
    db.flush()

    # Response 1: Clarification Requested
    resp1 = ReferralResponse(
        referral_request_id=ref.id,
        response_type="REQUEST_CLARIFICATION",
        response_notes="Please confirm if patient is intubated",
    )
    # Response 2: Clarification Provided
    resp2 = ReferralResponse(
        referral_request_id=ref.id,
        response_type="CLARIFICATION_PROVIDED",
        response_notes="Patient spontaneous breathing, on 4L nasal cannula",
    )
    # Response 3: Accept
    resp3 = ReferralResponse(
        referral_request_id=ref.id,
        response_type="ACCEPT",
        response_notes="Trauma bay 1 reserved",
    )
    db.add_all([resp1, resp2, resp3])
    ref.status = "ACCEPTED"
    db.commit()

    ref_fetched = db.get(ReferralRequest, ref.id)
    assert len(ref_fetched.responses) == 3
    types = [r.response_type for r in ref_fetched.responses]
    assert types == ["REQUEST_CLARIFICATION", "CLARIFICATION_PROVIDED", "ACCEPT"]
    db.close()
