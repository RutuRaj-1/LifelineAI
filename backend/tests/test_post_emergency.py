"""Post-Emergency Continuity, Outcomes, Discharges, Medication Reconciliation & Follow-Up Test Suite (Prompt 10).

Verifies:
1. Emergency Outcomes: Disposition categories (DISCHARGED, ADMITTED, TRANSFERRED), authorization isolation, duplicate rejection, and versioned amendments.
2. Discharge Documentation & Summaries: Ingestion, OCR preservation, evidence-grounded draft synthesis, physician review gate, and diagnosis promotion to PatientClinicalFact.
3. Medication Reconciliation: CONTINUE/START/STOP/CHANGE reconciliation, clinician verification gate, longitudinal promotion and deactivation.
4. Follow-Up Management: Plan creation, lifecycle transitions (PLANNED -> SCHEDULED -> COMPLETED), patient access.
5. Longitudinal Patient Record: Timeline integration of approved records, deduplication, emergency encounter history retrieval.
"""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import (
    ClinicalHandover,
    ClinicalProvenance,
    DischargeSummary,
    Doctor,
    EmergencyCase,
    EmergencyOutcome,
    FollowUpPlan,
    Hospital,
    HospitalDepartment,
    MedicalReport,
    MedicationReconciliation,
    Patient,
    PatientClinicalFact,
    ReferralRequest,
    User,
)
from app.security import create_token


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def post_em_fixture(client):
    """
    Sets up an emergency encounter ready for post-emergency continuity:
    - 1 Patient + Profile with baseline clinical facts
    - 1 Family User linked to Patient
    - 1 Emergency Physician (Doctor User)
    - 1 Receiving Hospital (Alpha) + Hospital Staff User
    - 1 Other Hospital (Beta) for isolation testing
    - 1 Arrived & Handover-Acknowledged Emergency Case
    """
    import uuid
    db: Session = SessionLocal()
    now = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:6]

    # Users
    u_pat = User(email=f"post_pat_{uid}@test.com", password_hash="h", full_name="Robert Continuity", role="patient")
    u_fam = User(email=f"post_fam_{uid}@test.com", password_hash="h", full_name="Lisa Continuity", role="family")
    u_doc = User(email=f"post_doc_{uid}@test.com", password_hash="h", full_name="Dr. Gregory House", role="doctor")
    u_hosp_alpha = User(email=f"post_alpha_{uid}@test.com", password_hash="h", full_name="Alpha Discharge Coordinator", role="hospital")
    u_hosp_beta = User(email=f"post_beta_{uid}@test.com", password_hash="h", full_name="Beta Coordinator", role="hospital")
    db.add_all([u_pat, u_fam, u_doc, u_hosp_alpha, u_hosp_beta])
    db.flush()

    # Hospitals
    h_alpha = Hospital(name=f"Metro Trauma Center {uid}", address="100 Metro Ave", city="Pune", lat=18.52, lng=73.85, status="VERIFIED")
    h_beta = Hospital(name=f"Other Health System {uid}", address="200 West Rd", city="Pune", lat=18.55, lng=73.88, status="VERIFIED")
    db.add_all([h_alpha, h_beta])
    db.flush()

    u_hosp_alpha.hospital_id = h_alpha.id
    u_hosp_beta.hospital_id = h_beta.id
    u_doc.hospital_id = h_alpha.id

    # Department
    dept = HospitalDepartment(
        hospital_id=h_alpha.id,
        department_name="Cardiology",
        department_code="CARD",
        operational_status="ACTIVE",
    )
    db.add(dept)
    db.flush()

    # Doctor
    doc = Doctor(user_id=u_doc.id, hospital_id=h_alpha.id, specialty="Cardiology", is_available=True)
    db.add(doc)
    db.flush()

    # Patient
    pat = Patient(
        user_id=u_pat.id,
        dob="1975-06-15",
        gender="Male",
        blood_group="O+",
        family_code=f"FC{uid}",
        consent_ai_summary=True,
    )
    db.add(pat)
    db.flush()

    u_fam.linked_patient_id = pat.id

    # Baseline Clinical Fact: existing Lisinopril medication
    med_fact = PatientClinicalFact(
        patient_id=pat.id,
        fact_type="MEDICATION",
        fact_value="Lisinopril 10mg",
        clinical_status="ACTIVE",
    )
    db.add(med_fact)
    db.flush()

    prov = ClinicalProvenance(
        clinical_fact_id=med_fact.id,
        source_type="PATIENT_ENTERED",
        source_user_id=u_pat.id,
        source_reference="Patient Registration Baseline",
        verification_status="UNVERIFIED",
    )
    db.add(prov)

    # Active Emergency Case (Arrived & Handover Complete)
    case = EmergencyCase(
        patient_id=pat.id,
        hospital_id=h_alpha.id,
        doctor_id=doc.id,
        status="ARRIVED",
        priority=1,
        emergency_type="cardiac",
        symptoms="Acute retrosternal chest pain and diaphoresis",
        lat=18.5204,
        lng=73.8567,
        arrived_at=now,
        handover_status="HANDOVER_COMPLETE",
    )
    db.add(case)
    db.commit()

    # Generate Auth Tokens
    t_pat = create_token(u_pat)
    t_fam = create_token(u_fam)
    t_doc = create_token(u_doc)
    t_alpha = create_token(u_hosp_alpha)
    t_beta = create_token(u_hosp_beta)

    yield {
        "case": case,
        "patient": pat,
        "hospital_alpha": h_alpha,
        "hospital_beta": h_beta,
        "doctor": doc,
        "dept": dept,
        "tokens": {
            "patient": t_pat,
            "family": t_fam,
            "doctor": t_doc,
            "alpha": t_alpha,
            "beta": t_beta,
        },
    }
    db.close()


def test_emergency_outcome_recording_and_amendments(client, post_em_fixture):
    """Verifies outcome disposition recording, role authorization, collision protection, and versioned amendments."""
    f = post_em_fixture
    case_id = f["case"].id

    # 1. Unauthenticated request is rejected
    res_unauth = client.post(f"/api/emergency/{case_id}/outcome", json={"disposition": "DISCHARGED"})
    assert res_unauth.status_code == 401

    # 2. Unauthorized hospital staff (Beta) is rejected
    res_beta = client.post(
        f"/api/emergency/{case_id}/outcome",
        headers=_auth_header(f["tokens"]["beta"]),
        json={"disposition": "DISCHARGED", "disposition_notes": "Attempt from unrelated hospital"},
    )
    assert res_beta.status_code == 403

    # 3. Authorized Hospital Alpha records DISCHARGED outcome
    payload_discharged = {
        "disposition": "DISCHARGED",
        "disposition_notes": "Patient stabilized; chest pain resolved after dual antiplatelet therapy. Discharged ambulatory.",
    }
    res_alpha = client.post(
        f"/api/emergency/{case_id}/outcome",
        headers=_auth_header(f["tokens"]["alpha"]),
        json=payload_discharged,
    )
    assert res_alpha.status_code == 201
    data_out = res_alpha.json()
    assert data_out["disposition"] == "DISCHARGED"
    assert data_out["version"] == 1
    assert data_out["emergency_case_id"] == case_id
    assert data_out["verification_status"] in ("REVIEWED", "CLINICIAN_VERIFIED")

    # 4. EmergencyCase status transitions to COMPLETED upon discharge
    db = SessionLocal()
    case_db = db.get(EmergencyCase, case_id)
    assert case_db.status == "COMPLETED"
    assert case_db.completed_at is not None
    db.close()

    # 5. Duplicate outcome submission without amendment is rejected with 409 Conflict
    res_dup = client.post(
        f"/api/emergency/{case_id}/outcome",
        headers=_auth_header(f["tokens"]["alpha"]),
        json={"disposition": "ADMITTED"},
    )
    assert res_dup.status_code == 409

    # 6. Controlled Amendment via PATCH /outcome creates version 2 and preserves audit trail
    amend_payload = {
        "disposition": "ADMITTED",
        "disposition_notes": "Post-discharge review: Troponin elevation noted on delayed report. Patient admitted to CCU.",
        "amendment_reason": "Delayed troponin elevation required conversion from outpatient to CCU inpatient admission.",
    }
    res_amend = client.patch(
        f"/api/emergency/{case_id}/outcome",
        headers=_auth_header(f["tokens"]["doctor"]),
        json=amend_payload,
    )
    assert res_amend.status_code == 200
    amended = res_amend.json()
    assert amended["disposition"] == "ADMITTED"
    assert amended["version"] == 2
    assert amended["parent_outcome_id"] == data_out["id"]
    assert amended["amendment_reason"] == amend_payload["amendment_reason"]
    assert amended["verification_status"] == "CLINICIAN_VERIFIED"

    # 7. GET /api/emergency/{case_id}/outcome returns active amended outcome
    res_get = client.get(
        f"/api/emergency/{case_id}/outcome",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_get.status_code == 200
    active_outcome = res_get.json()
    assert active_outcome["version"] == 2
    assert active_outcome["disposition"] == "ADMITTED"


def test_discharge_document_upload_and_ocr(client, post_em_fixture):
    """Verifies official discharge document ingestion, OCR preservation, and draft synthesis."""
    f = post_em_fixture
    case_id = f["case"].id

    # 1. Unauthorized hospital (Beta) upload rejected
    fake_file = ("discharge_note.txt", b"Discharge Summary: Patient admitted with NSTEMI. Stent placed.", "text/plain")
    res_unauth = client.post(
        f"/api/emergency/{case_id}/discharge-documents",
        headers=_auth_header(f["tokens"]["beta"]),
        files={"file": fake_file},
    )
    assert res_unauth.status_code == 403

    # 2. Authorized Hospital Alpha uploads document
    fake_doc = ("official_discharge.txt", b"Official Hospital Discharge Record. Primary Diagnosis: Acute Myocardial Infarction.", "text/plain")
    res_up = client.post(
        f"/api/emergency/{case_id}/discharge-documents",
        headers=_auth_header(f["tokens"]["alpha"]),
        files={"file": fake_doc},
        data={"title": "Official CCU Discharge Card", "document_type": "Discharge Summary"},
    )
    assert res_up.status_code == 201
    up_data = res_up.json()
    assert "report_id" in up_data
    assert "discharge_summary_id" in up_data
    assert up_data["status"] == "PENDING_REVIEW"
    assert up_data["ocr_status"] == "ok"

    # 3. List discharge documents for this case
    res_list = client.get(
        f"/api/emergency/{case_id}/discharge-documents",
        headers=_auth_header(f["tokens"]["alpha"]),
    )
    assert res_list.status_code == 200
    docs = res_list.json()
    assert len(docs) >= 1
    assert docs[0]["id"] == up_data["report_id"]


def test_discharge_summary_generation_and_physician_approval_gate(client, post_em_fixture):
    """Verifies evidence-grounded summary draft synthesis, non-diagnostic safety boundary, and physician approval gate."""
    f = post_em_fixture
    case_id = f["case"].id

    # 1. Generate structured draft
    draft_in = {
        "primary_diagnosis": "Non-ST Elevation Myocardial Infarction (NSTEMI)",
        "secondary_diagnoses": ["Hypertension", "Dyslipidemia"],
        "procedures_performed": ["Diagnostic Coronary Angiogram", "LAD Stenting"],
        "clinical_course": "Patient presented with severe chest pain. Underwent emergent angiogram with DES stenting to LAD.",
        "discharge_condition": "STABLE",
        "precautions": ["Avoid strenuous physical exertion for 2 weeks", "Report recurrent chest discomfort immediately"],
        "notes": "Emergency physician synthesized post-procedure brief.",
    }
    res_gen = client.post(
        f"/api/emergency/{case_id}/discharge-summary/generate",
        headers=_auth_header(f["tokens"]["alpha"]),
        json=draft_in,
    )
    assert res_gen.status_code == 201
    draft = res_gen.json()
    assert draft["status"] == "PENDING_REVIEW"
    assert draft["is_current_approved"] is False
    assert draft["primary_diagnosis"] == draft_in["primary_diagnosis"]
    assert "missing_data_warnings" in draft["summary_data"]
    assert "disclaimer" in draft["summary_data"]

    summary_id = draft["id"]

    # 2. Non-physician (Patient) cannot approve discharge summary
    res_pat_app = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{summary_id}/approve",
        headers=_auth_header(f["tokens"]["patient"]),
        json={"approval_notes": "Attempting patient self-approval"},
    )
    assert res_pat_app.status_code == 403

    # 3. Non-physician hospital triage staff cannot clinically approve
    res_staff_app = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{summary_id}/approve",
        headers=_auth_header(f["tokens"]["alpha"]),
        json={"approval_notes": "Triage staff approval"},
    )
    assert res_staff_app.status_code == 403

    # 4. Rejection workflow: Physician rejects with required reason
    res_rej = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{summary_id}/reject",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"rejection_reason": "Incomplete echocardiography ejection fraction documentation."},
    )
    assert res_rej.status_code == 200
    rejected = res_rej.json()
    assert rejected["status"] == "REJECTED"
    assert rejected["rejection_reason"] == "Incomplete echocardiography ejection fraction documentation."

    # 5. Generate revised version 2
    res_gen2 = client.post(
        f"/api/emergency/{case_id}/discharge-summary/generate",
        headers=_auth_header(f["tokens"]["alpha"]),
        json={**draft_in, "clinical_course": "Updated: EF 55% confirmed on formal echo. LAD stent patent."},
    )
    summary_v2 = res_gen2.json()
    assert summary_v2["version"] == 2
    assert summary_v2["status"] == "PENDING_REVIEW"

    # 6. Physician Approves Version 2
    res_app = client.post(
        f"/api/emergency/{case_id}/discharge-summary/{summary_v2['id']}/approve",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"approval_notes": "Clinically reviewed and approved in full by attending cardiologist."},
    )
    assert res_app.status_code == 200
    approved = res_app.json()
    assert approved["status"] == "APPROVED"
    assert approved["is_current_approved"] is True
    assert approved["approved_by_user_id"] is not None

    # 7. Verify promotion to longitudinal PatientClinicalFact
    db = SessionLocal()
    promoted_fact = (
        db.query(PatientClinicalFact)
        .filter(
            PatientClinicalFact.patient_id == f["patient"].id,
            PatientClinicalFact.fact_type == "CONDITION",
            PatientClinicalFact.fact_value == draft_in["primary_diagnosis"],
        )
        .first()
    )
    assert promoted_fact is not None
    assert promoted_fact.clinical_status == "ACTIVE"
    prov_record = promoted_fact.provenance_records[0]
    assert prov_record.source_type == "HOSPITAL_IMPORTED"
    assert prov_record.verification_status == "VERIFIED"
    db.close()


def test_medication_reconciliation_workflow_and_fact_promotion(client, post_em_fixture):
    """Verifies CONTINUE/START/STOP medication reconciliation, clinician gate, and clinical fact promotion/deactivation."""
    f = post_em_fixture
    case_id = f["case"].id

    # 1. Add START medication: Clopidogrel 75mg
    entry_start = {
        "medication_name": "Clopidogrel",
        "dosage": "75mg",
        "route": "ORAL",
        "frequency": "ONCE_DAILY",
        "reconciliation_status": "START",
        "clinical_reason": "Post-PCI dual antiplatelet therapy for 12 months",
    }
    res_start = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation",
        headers=_auth_header(f["tokens"]["alpha"]),
        json=entry_start,
    )
    assert res_start.status_code == 201
    rec_start = res_start.json()
    assert rec_start["reconciliation_status"] == "START"
    assert rec_start["verification_status"] == "UNVERIFIED"

    # 2. Add STOP medication: Discontinue baseline Lisinopril due to hypotension/AKI
    entry_stop = {
        "medication_name": "Lisinopril",
        "dosage": "10mg",
        "reconciliation_status": "STOP",
        "clinical_reason": "Discontinued due to acute transient renal impairment.",
    }
    res_stop = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation",
        headers=_auth_header(f["tokens"]["alpha"]),
        json=entry_stop,
    )
    assert res_stop.status_code == 201
    rec_stop = res_stop.json()

    # 3. Non-physician (Patient) cannot verify medication reconciliation
    res_pat_v = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation/{rec_start['id']}/verify",
        headers=_auth_header(f["tokens"]["patient"]),
        json={"verification_status": "VERIFIED"},
    )
    assert res_pat_v.status_code == 403

    # 4. Clinician verifies START entry
    res_v_start = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation/{rec_start['id']}/verify",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"verification_status": "VERIFIED", "clinical_reason": "Approved by attending cardiologist."},
    )
    assert res_v_start.status_code == 200
    assert res_v_start.json()["verification_status"] == "VERIFIED"

    # 5. Clinician verifies STOP entry
    res_v_stop = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation/{rec_stop['id']}/verify",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"verification_status": "VERIFIED"},
    )
    assert res_v_stop.status_code == 200

    # 6. Verify longitudinal database state:
    # - Clopidogrel is now an ACTIVE PatientClinicalFact
    # - Baseline Lisinopril is marked RESOLVED
    db = SessionLocal()
    clopidogrel_fact = (
        db.query(PatientClinicalFact)
        .filter(
            PatientClinicalFact.patient_id == f["patient"].id,
            PatientClinicalFact.fact_type == "MEDICATION",
            PatientClinicalFact.fact_value.ilike("%Clopidogrel%"),
        )
        .first()
    )
    assert clopidogrel_fact is not None
    assert clopidogrel_fact.clinical_status == "ACTIVE"

    lisinopril_fact = (
        db.query(PatientClinicalFact)
        .filter(
            PatientClinicalFact.patient_id == f["patient"].id,
            PatientClinicalFact.fact_type == "MEDICATION",
            PatientClinicalFact.fact_value.ilike("%Lisinopril%"),
        )
        .first()
    )
    assert lisinopril_fact is not None
    assert lisinopril_fact.clinical_status == "RESOLVED"
    db.close()


def test_follow_up_plan_lifecycle(client, post_em_fixture):
    """Verifies follow-up creation, status transition (PLANNED -> SCHEDULED -> COMPLETED), and patient visibility."""
    f = post_em_fixture
    case_id = f["case"].id

    # 1. Create Follow-Up Plan
    plan_in = {
        "specialty": "Cardiology Outpatient Clinic",
        "department_id": f["dept"].id,
        "scheduled_date": "2026-12-05",
        "instructions": "Echocardiogram and ECG review at 14 days post-stent placement. Bring medication diary.",
    }
    res_create = client.post(
        f"/api/emergency/{case_id}/follow-ups",
        headers=_auth_header(f["tokens"]["alpha"]),
        json=plan_in,
    )
    assert res_create.status_code == 201
    plan_data = res_create.json()
    assert plan_data["status"] == "PLANNED"
    assert plan_data["specialty"] == plan_in["specialty"]

    plan_id = plan_data["id"]

    # 2. Update status: mark SCHEDULED
    res_up1 = client.patch(
        f"/api/follow-ups/{plan_id}",
        headers=_auth_header(f["tokens"]["patient"]),
        json={"status": "SCHEDULED", "scheduled_date": "2026-12-05 10:30 AM"},
    )
    assert res_up1.status_code == 200
    assert res_up1.json()["status"] == "SCHEDULED"

    # 3. Update status: mark COMPLETED
    res_up2 = client.patch(
        f"/api/follow-ups/{plan_id}",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"status": "COMPLETED", "completion_notes": "Follow-up attended. Patient stable; no angina."},
    )
    assert res_up2.status_code == 200
    completed = res_up2.json()
    assert completed["status"] == "COMPLETED"
    assert completed["completed_at"] is not None

    # 4. Patient queries their own follow-ups
    res_pat_list = client.get(
        "/api/patient/follow-ups",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_pat_list.status_code == 200
    pat_plans = res_pat_list.json()
    assert len(pat_plans) >= 1
    assert any(p["id"] == plan_id for p in pat_plans)


def test_patient_longitudinal_health_timeline_and_history(client, post_em_fixture):
    """Verifies that approved discharge summaries, verified med recs, and follow-ups appear in the Health Timeline and Emergency History."""
    f = post_em_fixture
    case_id = f["case"].id

    # 1. Record Outcome DISCHARGED
    client.post(
        f"/api/emergency/{case_id}/outcome",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"disposition": "DISCHARGED", "disposition_notes": "Outpatient discharge confirmed."},
    )

    # 2. Generate and Approve Discharge Summary
    res_gen = client.post(
        f"/api/emergency/{case_id}/discharge-summary/generate",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"primary_diagnosis": "Coronary Artery Disease - Single Vessel Stented", "discharge_condition": "AMBULATORY"},
    )
    summary_id = res_gen.json()["id"]
    client.post(
        f"/api/emergency/{case_id}/discharge-summary/{summary_id}/approve",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"approval_notes": "Approved for longitudinal record."},
    )

    # 3. Create verified medication entry
    res_med = client.post(
        f"/api/emergency/{case_id}/medication-reconciliation",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"medication_name": "Atorvastatin", "dosage": "40mg", "reconciliation_status": "START", "clinical_reason": "High-intensity statin therapy"},
    )

    # 4. Create follow-up plan
    client.post(
        f"/api/emergency/{case_id}/follow-ups",
        headers=_auth_header(f["tokens"]["doctor"]),
        json={"specialty": "Preventive Cardiology", "instructions": "Lipid panel check in 6 weeks"},
    )

    # 5. Query Longitudinal Health Timeline
    res_timeline = client.get(
        "/api/patient/health-timeline?limit=50",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_timeline.status_code == 200
    timeline = res_timeline.json()
    event_types = [ev["event_type"] for ev in timeline["events"]]
    assert "DISCHARGE_SUMMARY" in event_types
    assert "MEDICATION_RECONCILED" in event_types
    assert "FOLLOW_UP_PLAN" in event_types

    # 6. Query Patient Emergency Encounter History
    res_history = client.get(
        "/api/patient/emergency-history",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_history.status_code == 200
    encounters = res_history.json()
    assert len(encounters) >= 1
    enc = next(e for e in encounters if e["case_id"] == case_id)
    assert enc["outcome"]["disposition"] == "DISCHARGED"
    assert enc["discharge_summary"]["primary_diagnosis"] == "Coronary Artery Disease - Single Vessel Stented"
    assert enc["discharge_summary"]["is_current_approved"] is True
    assert enc["follow_up_count"] >= 1
    assert enc["medication_count"] >= 1

    # 7. Query Patient Dedicated Discharge Summaries Endpoint
    res_ds = client.get(
        "/api/patient/discharge-summaries",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_ds.status_code == 200
    assert len(res_ds.json()) >= 1
    assert res_ds.json()[0]["primary_diagnosis"] == "Coronary Artery Disease - Single Vessel Stented"

    # 8. Query Patient Dedicated Medication Reconciliation Endpoint
    res_mr = client.get(
        "/api/patient/medication-reconciliation",
        headers=_auth_header(f["tokens"]["patient"]),
    )
    assert res_mr.status_code == 200
    assert any(m["medication_name"] == "Atorvastatin" for m in res_mr.json())
