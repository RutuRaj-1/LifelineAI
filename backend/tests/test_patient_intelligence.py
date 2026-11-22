"""Unit and integration tests for Patient Intelligence, Health Vault, and Longitudinal Timeline (Prompt 04)."""
import uuid
import pytest
from app.db import SessionLocal
from app.models import (
    ClinicalProvenance,
    Doctor,
    EmergencyCase,
    Hospital,
    MedicalReport,
    Patient,
    PatientClinicalFact,
    User,
)


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def two_patients(client):
    """Registers two distinct patients with isolated accounts."""
    u1 = uuid.uuid4().hex[:8]
    u2 = uuid.uuid4().hex[:8]

    # Patient 1
    r1 = client.post("/api/auth/register", json={
        "email": f"patient_{u1}@example.com",
        "password": "Password123!",
        "full_name": f"Patient One {u1}",
        "role": "patient",
    })
    assert r1.status_code == 201
    t1 = r1.json()["access_token"]

    # Patient 2
    r2 = client.post("/api/auth/register", json={
        "email": f"patient_{u2}@example.com",
        "password": "Password123!",
        "full_name": f"Patient Two {u2}",
        "role": "patient",
    })
    assert r2.status_code == 201
    t2 = r2.json()["access_token"]

    return {"p1": t1, "p2": t2}


def test_health_vault_overview(client, two_patients):
    token = two_patients["p1"]
    resp = client.get("/api/patient/health-vault", headers=_auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert "patient" in data
    assert "health_summary" in data
    assert "recent_reports" in data
    assert "verification_summary" in data
    assert data["total_facts"] == 0
    assert data["total_reports"] == 0
    assert data["conditions_count"] == 0
    assert data["allergies_count"] == 0
    assert data["medications_count"] == 0
    assert "disclaimer" in data["health_summary"]
    assert "Patient One" in data["patient"]["full_name"]


def test_clinical_facts_lifecycle_and_provenance(client, two_patients):
    token = two_patients["p1"]

    # 1. Create a condition fact
    fact_payload = {
        "fact_type": "CONDITION",
        "fact_code": "hypertension",
        "fact_value": "Stage 1 Primary Hypertension",
        "clinical_status": "ACTIVE",
        "notes": "Patient self-reported blood pressure readings averaging 135/88.",
    }
    create_resp = client.post("/api/patient/clinical-facts", json=fact_payload, headers=_auth_header(token))
    assert create_resp.status_code == 201
    created = create_resp.json()
    fact_id = created["id"]
    assert created["fact_code"] == "hypertension"
    assert created["fact_type"] == "CONDITION"

    # Verify provenance was automatically attached with PATIENT_ENTERED
    assert len(created["provenance_records"]) >= 1
    prov = created["provenance_records"][0]
    assert prov["source_type"] == "PATIENT_ENTERED"
    assert prov["verification_status"] == "UNVERIFIED"

    # 2. Create an allergy fact
    allergy_payload = {
        "fact_type": "ALLERGY",
        "fact_code": "penicillin_allergy",
        "fact_value": "Penicillin (Anaphylaxis risk)",
        "clinical_status": "ACTIVE",
    }
    a_resp = client.post("/api/patient/clinical-facts", json=allergy_payload, headers=_auth_header(token))
    assert a_resp.status_code == 201

    # 3. Query all facts and filter by type
    list_all = client.get("/api/patient/clinical-facts", headers=_auth_header(token))
    assert list_all.status_code == 200
    assert len(list_all.json()) == 2

    filtered_allergy = client.get("/api/patient/clinical-facts?fact_type=ALLERGY", headers=_auth_header(token))
    assert filtered_allergy.status_code == 200
    assert len(filtered_allergy.json()) == 1
    assert filtered_allergy.json()[0]["fact_code"] == "penicillin_allergy"

    # 4. Get specific fact
    get_fact = client.get(f"/api/patient/clinical-facts/{fact_id}", headers=_auth_header(token))
    assert get_fact.status_code == 200
    assert get_fact.json()["id"] == fact_id

    # 5. Patch fact (update notes/value) -> verify new provenance record appended
    update_payload = {
        "fact_value": "Stage 2 Hypertension",
        "update_notes": "Updated after clinician consultation.",
    }
    patch_resp = client.patch(f"/api/patient/clinical-facts/{fact_id}", json=update_payload, headers=_auth_header(token))
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["fact_value"] == "Stage 2 Hypertension"
    assert len(updated["provenance_records"]) == 2
    assert "Updated" in updated["provenance_records"][-1]["source_excerpt"]

    # 6. Delete fact (soft deactivation)
    del_resp = client.delete(f"/api/patient/clinical-facts/{fact_id}", headers=_auth_header(token))
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deactivated"

    # Verify vault count reflects active facts
    vault_resp = client.get("/api/patient/health-vault", headers=_auth_header(token))
    assert vault_resp.status_code == 200
    vault_data = vault_resp.json()
    assert vault_data["allergies_count"] == 1
    assert vault_data["conditions_count"] == 0  # condition was inactivated


def test_cross_patient_authorization_isolation(client, two_patients):
    t1 = two_patients["p1"]
    t2 = two_patients["p2"]

    # Patient 1 creates a private clinical fact
    payload = {
        "fact_type": "MEDICATION",
        "fact_code": "atorvastatin",
        "fact_value": "Atorvastatin 20mg nightly",
        "clinical_status": "ACTIVE",
    }
    r1 = client.post("/api/patient/clinical-facts", json=payload, headers=_auth_header(t1))
    assert r1.status_code == 201
    fact_id = r1.json()["id"]

    # Patient 2 attempts to read Patient 1's fact -> 404 (Not Found / Forbidden)
    r2_get = client.get(f"/api/patient/clinical-facts/{fact_id}", headers=_auth_header(t2))
    assert r2_get.status_code == 404

    # Patient 2 attempts to patch Patient 1's fact -> 404
    r2_patch = client.patch(f"/api/patient/clinical-facts/{fact_id}", json={"fact_value": "Hacked"}, headers=_auth_header(t2))
    assert r2_patch.status_code == 404

    # Patient 2 attempts to delete Patient 1's fact -> 404
    r2_del = client.delete(f"/api/patient/clinical-facts/{fact_id}", headers=_auth_header(t2))
    assert r2_del.status_code == 404


def test_health_timeline_longitudinal(client, two_patients):
    token = two_patients["p1"]

    # Add a clinical fact
    add_resp = client.post("/api/patient/clinical-facts", json={
        "fact_type": "SURGERY",
        "fact_code": "appendectomy",
        "fact_value": "Laparoscopic Appendectomy",
        "clinical_status": "ACTIVE",
        "notes": "Uneventful surgical removal of appendix.",
    }, headers=_auth_header(token))
    assert add_resp.status_code == 201

    # Fetch timeline
    timeline_resp = client.get("/api/patient/health-timeline", headers=_auth_header(token))
    assert timeline_resp.status_code == 200
    t_data = timeline_resp.json()
    assert "events" in t_data
    assert "total" in t_data
    assert t_data["total"] >= 1

    event = t_data["events"][0]
    assert "event_type" in event
    assert "recorded_at" in event
    assert "title" in event
    assert "provenance_source" in event


def test_unauthenticated_patient_intelligence_endpoints_rejected(client):
    assert client.get("/api/patient/health-vault").status_code == 401
    assert client.get("/api/patient/clinical-facts").status_code == 401
    assert client.post("/api/patient/clinical-facts", json={}).status_code == 401
    assert client.get("/api/patient/health-timeline").status_code == 401
    assert client.get("/api/patient/medical-reports").status_code == 401
