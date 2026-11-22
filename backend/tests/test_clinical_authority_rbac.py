"""Clinical Authority RBAC Security Verification Tests (Prompt 11).

Explicitly validates Section 5.2 of Prompt 11:
- Administrative role (ADMIN) must NOT automatically grant clinical verification authority.
- Approving clinical handovers requires DOCTOR role.
- Approving/rejecting discharge summaries requires DOCTOR role.
- Verifying medication reconciliation requires DOCTOR role.
- Non-clinicians (admin, hospital staff, family, patient) receive strict 403 Forbidden.
"""
from datetime import datetime, timezone
import pytest
from starlette.testclient import TestClient

from app.db import SessionLocal
from app.models import (
    ClinicalHandover,
    DischargeSummary,
    Doctor,
    EmergencyCase,
    Hospital,
    MedicationReconciliation,
    Patient,
    User,
)
from app.security import create_token, hash_password


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def clinical_rbac_fixture():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp() * 1000)

    # 1. Admin User (System administrator, NOT a physician)
    u_admin = User(
        email=f"sysadmin_{ts}@lifeline.org",
        password_hash=hash_password("adminSecret123"),
        full_name="Sys Admin",
        role="admin",
    )
    db.add(u_admin)

    # 2. Doctor User (Licensed physician)
    u_doc = User(
        email=f"physician_{ts}@hospital.org",
        password_hash=hash_password("docSecret123"),
        full_name="Dr. Gregory House",
        role="doctor",
    )
    db.add(u_doc)

    # 3. Patient User
    u_pat = User(
        email=f"patient_{ts}@domain.org",
        password_hash=hash_password("patSecret123"),
        full_name="Jane Doe",
        role="patient",
    )
    db.add(u_pat)

    # 4. Hospital Staff User
    hosp = Hospital(
        name=f"Metro General {ts}",
        address="100 Medical Center Way",
        city="Pune",
        lat=18.5204,
        lng=73.8567,
        status="VERIFIED",
    )
    db.add(hosp)
    db.flush()

    u_hosp = User(
        email=f"hospstaff_{ts}@metro.org",
        password_hash=hash_password("hospSecret123"),
        full_name="Triage Nurse Bob",
        role="hospital",
        hospital_id=hosp.id,
    )
    db.add(u_hosp)

    pat = Patient(user_id=u_pat.id, dob="1985-05-15", gender="female", blood_group="O+", family_code=f"FC{ts}", consent_ai_summary=True)
    db.add(pat)

    doc = Doctor(user_id=u_doc.id, hospital_id=hosp.id, specialty="Cardiology", qualification="MD, FACC", is_available=True)
    db.add(doc)
    db.flush()

    # Active Emergency Case
    case = EmergencyCase(
        patient_id=pat.id,
        hospital_id=hosp.id,
        doctor_id=doc.id,
        status="ARRIVED",
        priority=1,
        emergency_type="cardiac",
        symptoms="Acute chest pain",
        lat=18.5204,
        lng=73.8567,
    )
    db.add(case)
    db.flush()

    # Handover draft (PENDING_REVIEW)
    handover = ClinicalHandover(
        emergency_case_id=case.id,
        version=1,
        status="PENDING_REVIEW",
        handover_data={"non_diagnostic_disclaimer": "EVIDENCE-GROUNDED", "missing_and_uncertain_information": []},
        is_current_approved=False,
    )
    db.add(handover)

    # Discharge summary draft (PENDING_REVIEW)
    summary = DischargeSummary(
        emergency_case_id=case.id,
        patient_id=pat.id,
        hospital_id=hosp.id,
        version=1,
        status="PENDING_REVIEW",
        primary_diagnosis="Acute Coronary Syndrome",
        discharge_condition="Stable",
        discharge_date="2026-11-22",
        summary_data={
            "primary_diagnosis": "Acute Coronary Syndrome",
            "discharge_condition": "Stable",
            "precautions": ["Seek immediate emergency care if chest pressure returns"],
            "missing_data_warnings": [],
            "disclaimer": "EVIDENCE-GROUNDED CONTINUITY RECORD",
        },
        is_current_approved=False,
    )
    db.add(summary)

    # Medication reconciliation item (UNVERIFIED)
    med_rec = MedicationReconciliation(
        emergency_case_id=case.id,
        patient_id=pat.id,
        hospital_id=hosp.id,
        medication_name="Ticagrelor",
        dosage="90mg",
        route="oral",
        frequency="twice daily",
        reconciliation_status="START",
        clinical_reason="Post-PCI dual antiplatelet therapy",
        source_type="CLINICIAN_ENTERED",
        verification_status="UNVERIFIED",
    )
    db.add(med_rec)
    db.commit()

    case_id = case.id
    handover_id = handover.id
    summary_id = summary.id
    med_rec_id = med_rec.id

    tokens = {
        "admin": create_token(u_admin),
        "doctor": create_token(u_doc),
        "patient": create_token(u_pat),
        "hospital": create_token(u_hosp),
    }
    db.close()

    yield {
        "case_id": case_id,
        "handover_id": handover_id,
        "summary_id": summary_id,
        "med_rec_id": med_rec_id,
        "tokens": tokens,
    }


def test_admin_cannot_approve_or_reject_clinical_handover(client: TestClient, clinical_rbac_fixture):
    """Proves that an administrator without clinical licensing CANNOT approve/reject clinical handovers."""
    f = clinical_rbac_fixture
    case_id = f["case_id"]
    h_id = f["handover_id"]

    # 1. Admin attempt to approve handover -> 403 Forbidden
    res_admin = client.post(
        f"/api/emergency/{case_id}/handover/{h_id}/approve",
        json={"approval_notes": "Admin unauthorized attempt"},
        headers=_auth_header(f["tokens"]["admin"]),
    )
    assert res_admin.status_code == 403
    assert "Clinical authority required" in res_admin.json()["detail"]

    # 2. Hospital staff attempt to approve handover -> 403 Forbidden
    res_hosp = client.post(
        f"/api/emergency/{case_id}/handover/{h_id}/approve",
        headers=_auth_header(f["tokens"]["hospital"]),
    )
    assert res_hosp.status_code == 403

    # 3. Patient attempt to approve handover -> 403 Forbidden
    res_pat = client.post(
        f"/api/emergency/{case_id}/handover/{h_id}/approve",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_pat.status_code == 403

    # 4. Admin attempt to reject handover -> 403 Forbidden
    res_admin_rej = client.post(
        f"/api/emergency/{case_id}/handover/{h_id}/reject",
        json={"rejection_reason": "Admin rejection unauthorized"},
        headers=_auth_header(f["tokens"]["admin"]),
    )
    assert res_admin_rej.status_code == 403
    assert "Clinical authority required" in res_admin_rej.json()["detail"]

    # 5. Doctor approval succeeds -> 200 OK
    res_doc = client.post(
        f"/api/emergency/{case_id}/handover/{h_id}/approve",
        json={"approval_notes": "Doctor verified telemetry and baseline ECG"},
        headers=_auth_header(f["tokens"]["doctor"]),
    )
    assert res_doc.status_code == 200
    assert res_doc.json()["status"] == "APPROVED"


def test_admin_cannot_approve_or_reject_discharge_summary(client: TestClient, clinical_rbac_fixture):
    """Proves that an administrator CANNOT clinically approve or reject hospital discharge summaries."""
    f = clinical_rbac_fixture
    case_id = f["case_id"]
    s_id = f["summary_id"]

    # 1. Admin approval rejected with 403
    res_admin_appr = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{s_id}/approve",
        json={"approval_notes": "Admin approval"},
        headers=_auth_header(f["tokens"]["admin"]),
    )
    assert res_admin_appr.status_code == 403
    assert "Clinical authority required" in res_admin_appr.json()["detail"]

    # 2. Admin rejection rejected with 403
    res_admin_rej = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{s_id}/reject",
        json={"rejection_reason": "Admin rejection"},
        headers=_auth_header(f["tokens"]["admin"]),
    )
    assert res_admin_rej.status_code == 403
    assert "Clinical authority required" in res_admin_rej.json()["detail"]

    # 3. Qualified Doctor approval succeeds -> 200 OK
    res_doc = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{s_id}/approve",
        json={"approval_notes": "Physician clinical sign-off verified"},
        headers=_auth_header(f["tokens"]["doctor"]),
    )
    assert res_doc.status_code == 200
    assert res_doc.json()["status"] == "APPROVED"
    assert res_doc.json()["is_current_approved"] is True


def test_admin_cannot_verify_medication_reconciliation(client: TestClient, clinical_rbac_fixture):
    """Proves that an administrator CANNOT verify medication reconciliations (which promotes meds to facts)."""
    f = clinical_rbac_fixture
    case_id = f["case_id"]
    med_id = f["med_rec_id"]

    # 1. Admin attempt to verify medication reconciliation -> 403 Forbidden
    res_admin = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation/{med_id}/verify",
        json={"verification_status": "VERIFIED", "clinical_reason": "Admin attempt"},
        headers=_auth_header(f["tokens"]["admin"]),
    )
    assert res_admin.status_code == 403
    assert "Clinical authority required" in res_admin.json()["detail"]

    # 2. Qualified Doctor verification succeeds -> 200 OK
    res_doc = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation/{med_id}/verify",
        json={"verification_status": "VERIFIED", "clinical_reason": "Physician confirmed post-PCI protocol"},
        headers=_auth_header(f["tokens"]["doctor"]),
    )
    assert res_doc.status_code == 200
    assert res_doc.json()["verification_status"] == "VERIFIED"
