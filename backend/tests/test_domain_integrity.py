import pytest
from sqlalchemy.exc import IntegrityError
from app.models import (
    Hospital,
    HospitalDepartment,
    HospitalResource,
    Patient,
    ResourceReservation,
    User,
)


def test_unique_department_code_within_hospital(client):
    from app.db import SessionLocal
    db = SessionLocal()

    h = Hospital(name="Dept Check Hospital", address="Addr", city="Pune", lat=18.5, lng=73.8)
    db.add(h)
    db.flush()

    d1 = HospitalDepartment(hospital_id=h.id, department_name="ICU 1", department_code="ICU")
    db.add(d1)
    db.commit()

    # Duplicate department_code for the SAME hospital must fail
    d2 = HospitalDepartment(hospital_id=h.id, department_name="ICU 2", department_code="ICU")
    db.add(d2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_resource_negative_quantity_check_constraint(client):
    from app.db import SessionLocal
    db = SessionLocal()

    h = Hospital(name="Resource Check Hospital", address="Addr", city="Pune", lat=18.5, lng=73.8)
    db.add(h)
    db.flush()

    res = HospitalResource(hospital_id=h.id, resource_type="ICU_BED", total=-5, available=0)
    db.add(res)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_reservation_positive_quantity_constraint(client):
    from app.db import SessionLocal
    from app.models import EmergencyCase, ReferralRequest
    db = SessionLocal()

    u = User(email="res_q_user@test.com", password_hash="h", full_name="User", role="patient")
    db.add(u)
    db.flush()
    p = Patient(user_id=u.id, family_code="RESQ1")
    h = Hospital(name="Hosp", address="A", city="P", lat=18.5, lng=73.8)
    db.add_all([p, h])
    db.flush()

    c = EmergencyCase(patient_id=p.id, hospital_id=h.id, emergency_type="cardiac", lat=18.5, lng=73.8)
    db.add(c)
    db.flush()

    ref = ReferralRequest(emergency_case_id=c.id, hospital_id=h.id, request_reference="REF-Q-1")
    res = HospitalResource(hospital_id=h.id, resource_type="ER_BED", total=5, available=5)
    db.add_all([ref, res])
    db.flush()

    # Zero or negative quantity must fail check constraint ck_reservation_positive_quantity
    bad_reservation = ResourceReservation(
        referral_request_id=ref.id,
        hospital_resource_id=res.id,
        quantity=0,
        idempotency_key="IDEM-ZERO",
    )
    db.add(bad_reservation)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_duplicate_idempotency_key_rejected(client):
    from app.db import SessionLocal
    from app.models import EmergencyCase, ReferralRequest
    db = SessionLocal()

    u = User(email="idem_user@test.com", password_hash="h", full_name="User", role="patient")
    db.add(u)
    db.flush()
    p = Patient(user_id=u.id, family_code="IDEM1")
    h = Hospital(name="Hosp Idem", address="A", city="P", lat=18.5, lng=73.8)
    db.add_all([p, h])
    db.flush()

    c = EmergencyCase(patient_id=p.id, hospital_id=h.id, emergency_type="cardiac", lat=18.5, lng=73.8)
    db.add(c)
    db.flush()

    ref = ReferralRequest(emergency_case_id=c.id, hospital_id=h.id, request_reference="REF-IDEM-1")
    res = HospitalResource(hospital_id=h.id, resource_type="ER_BED", total=5, available=5)
    db.add_all([ref, res])
    db.flush()

    r1 = ResourceReservation(referral_request_id=ref.id, hospital_resource_id=res.id, quantity=1, idempotency_key="IDEM-DUP")
    db.add(r1)
    db.commit()

    # Duplicate idempotency_key must fail
    r2 = ResourceReservation(referral_request_id=ref.id, hospital_resource_id=res.id, quantity=1, idempotency_key="IDEM-DUP")
    db.add(r2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()
