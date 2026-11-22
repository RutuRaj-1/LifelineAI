"""Unit and integration tests for Hospital Registry, Department Hierarchy, and Capability Lifecycle (Prompt 05)."""
import uuid
import pytest
from app.db import SessionLocal
from app.models import (
    Doctor,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    User,
)
from app.security import create_token, hash_password


def _auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def registry_fixture(client):
    """Sets up two isolated hospitals with staff and an administrative reviewer."""
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
        name=f"Suburban Care Clinic {u}",
        address="200 West Avenue",
        city="Mumbai",
        lat=19.0760,
        lng=72.8777,
        phone="+91-22-33334444",
        status="DRAFT",
        hospital_type="GENERAL",
        contact_email=f"suburban_{u}@hospital.demo",
    )
    db.add_all([h1, h2])
    db.flush()

    # Staff for Hospital 1
    u1 = User(
        email=f"staff1_{u}@hospital.demo",
        password_hash=hash_password("Pass123!"),
        full_name="Staff One",
        role="hospital",
        hospital_id=h1.id,
    )
    # Staff for Hospital 2
    u2 = User(
        email=f"staff2_{u}@hospital.demo",
        password_hash=hash_password("Pass123!"),
        full_name="Staff Two",
        role="hospital",
        hospital_id=h2.id,
    )
    # Admin Reviewer
    admin = User(
        email=f"admin_{u}@state.gov",
        password_hash=hash_password("Pass123!"),
        full_name="State Reviewer Admin",
        role="admin",
    )
    # Ordinary Patient
    patient = User(
        email=f"patient_{u}@example.com",
        password_hash=hash_password("Pass123!"),
        full_name="Citizen Patient",
        role="patient",
    )
    db.add_all([u1, u2, admin, patient])
    db.commit()

    t_h1 = create_token(u1)
    t_h2 = create_token(u2)
    t_admin = create_token(admin)
    t_pat = create_token(patient)

    h1_id = h1.id
    h2_id = h2.id
    db.close()

    return {
        "h1_id": h1_id,
        "h2_id": h2_id,
        "t_h1": t_h1,
        "t_h2": t_h2,
        "t_admin": t_admin,
        "t_pat": t_pat,
    }


def test_public_hospital_registry_discovery(client, registry_fixture):
    # 1. Public list endpoint
    resp = client.get("/api/hospitals")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "disclaimer" in data
    # By default, only VERIFIED hospitals are returned in public discovery
    statuses = {h["status"] for h in data["items"]}
    assert "VERIFIED" in statuses

    # Filter by city
    pune_resp = client.get("/api/hospitals?city=Pune")
    assert pune_resp.status_code == 200
    for it in pune_resp.json()["items"]:
        assert it["city"].lower() == "pune"

    # 2. Public hospital detail
    h1_id = registry_fixture["h1_id"]
    det_resp = client.get(f"/api/hospitals/{h1_id}")
    assert det_resp.status_code == 200
    det = det_resp.json()
    assert det["id"] == h1_id
    assert "Metro General" in det["name"]
    assert "disclaimer" in det


def test_hospital_profile_lifecycle_and_submission(client, registry_fixture):
    t_h2 = registry_fixture["t_h2"]

    # 1. Get own profile
    prof_resp = client.get("/api/hospital/profile", headers=_auth_header(t_h2))
    assert prof_resp.status_code == 200
    assert prof_resp.json()["status"] == "DRAFT"

    # 2. Patch own profile
    patch_resp = client.patch(
        "/api/hospital/profile",
        json={"phone": "+91-9999988888", "hospital_type": "TRAUMA_CENTER"},
        headers=_auth_header(t_h2),
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["hospital_type"] == "TRAUMA_CENTER"

    # 3. Submit profile for review (DRAFT -> UNDER_REVIEW)
    sub_resp = client.post("/api/hospital/profile/submit", headers=_auth_header(t_h2))
    assert sub_resp.status_code == 200
    assert sub_resp.json()["status"] == "UNDER_REVIEW"

    # Verify updated status
    updated = client.get("/api/hospital/profile", headers=_auth_header(t_h2)).json()
    assert updated["status"] == "UNDER_REVIEW"


def test_department_hierarchy_and_constraints(client, registry_fixture):
    t_h1 = registry_fixture["t_h1"]
    t_h2 = registry_fixture["t_h2"]

    # 1. Create department for Hospital 1
    d_resp = client.post(
        "/api/hospital/departments",
        json={
            "department_name": "Emergency & Trauma",
            "department_code": "EMERGENCY",
            "description": "Level 1 Acute Emergency Ward",
            "contact_information": "Ext 101",
        },
        headers=_auth_header(t_h1),
    )
    assert d_resp.status_code == 201
    d1 = d_resp.json()
    dept_id = d1["id"]
    assert d1["department_code"] == "EMERGENCY"

    # 2. Duplicate department code within Hospital 1 must fail with 409 Conflict
    dup_resp = client.post(
        "/api/hospital/departments",
        json={
            "department_name": "Emergency Second Wing",
            "department_code": "EMERGENCY",
        },
        headers=_auth_header(t_h1),
    )
    assert dup_resp.status_code == 409

    # 3. Same department code for Hospital 2 MUST succeed (unique per hospital)
    d2_resp = client.post(
        "/api/hospital/departments",
        json={
            "department_name": "Emergency Department",
            "department_code": "EMERGENCY",
        },
        headers=_auth_header(t_h2),
    )
    assert d2_resp.status_code == 201

    # 4. Hospital 2 cannot access or edit Hospital 1's department (Object Isolation)
    cross_get = client.get(f"/api/hospital/departments/{dept_id}", headers=_auth_header(t_h2))
    assert cross_get.status_code == 404

    cross_del = client.delete(f"/api/hospital/departments/{dept_id}", headers=_auth_header(t_h2))
    assert cross_del.status_code == 404

    # 5. Soft deactivation
    del_resp = client.delete(f"/api/hospital/departments/{dept_id}", headers=_auth_header(t_h1))
    assert del_resp.status_code == 200
    assert del_resp.json()["operational_status"] == "INACTIVE"


def test_capability_lifecycle_and_review_workflow(client, registry_fixture):
    t_h1 = registry_fixture["t_h1"]
    t_admin = registry_fixture["t_admin"]

    # 1. Create department first
    dept = client.post(
        "/api/hospital/departments",
        json={"department_name": "Cardiac Sciences", "department_code": "CARDIOLOGY"},
        headers=_auth_header(t_h1),
    ).json()

    # 2. Register capability under department
    cap_resp = client.post(
        "/api/hospital/capabilities",
        json={
            "capability_code": "CATH_LAB_PRIMARY_PCI",
            "capability_name": "Primary Coronary Intervention",
            "capability_category": "DIAGNOSTIC",
            "department_id": dept["id"],
            "availability_mode": "24_7",
            "description": "Round-the-clock emergency angioplasty team",
        },
        headers=_auth_header(t_h1),
    )
    assert cap_resp.status_code == 201
    cap = cap_resp.json()
    cap_id = cap["id"]
    assert cap["verification_status"] == "UNVERIFIED"

    # 3. Duplicate capability code in same hospital rejected
    dup_cap = client.post(
        "/api/hospital/capabilities",
        json={
            "capability_code": "CATH_LAB_PRIMARY_PCI",
            "capability_name": "Duplicate Cath Lab",
            "capability_category": "DIAGNOSTIC",
        },
        headers=_auth_header(t_h1),
    )
    assert dup_cap.status_code == 409

    # 4. Submit capability for review
    sub_resp = client.post(f"/api/hospital/capabilities/{cap_id}/submit-review", headers=_auth_header(t_h1))
    assert sub_resp.status_code == 200
    assert sub_resp.json()["verification_status"] == "PENDING_REVIEW"

    # 5. Admin lists pending reviews
    rev_list = client.get("/api/admin/hospital-reviews", headers=_auth_header(t_admin))
    assert rev_list.status_code == 200
    data = rev_list.json()
    assert any(c["id"] == cap_id for c in data["pending_capabilities"])

    # 6. Admin verifies capability
    verify_resp = client.post(
        f"/api/admin/hospital-capabilities/{cap_id}/verify",
        json={"notes": "Cath lab verified against NABH certification.", "verification_source": "NABH_AUDIT_2026"},
        headers=_auth_header(t_admin),
    )
    assert verify_resp.status_code == 200
    verified_cap = verify_resp.json()
    assert verified_cap["verification_status"] == "VERIFIED"
    assert "NABH" in verified_cap["verification_notes"]

    # 7. Verified capability now appears in public hospital capabilities list
    h1_id = registry_fixture["h1_id"]
    pub_caps = client.get(f"/api/hospitals/{h1_id}/capabilities").json()
    assert any(c["id"] == cap_id for c in pub_caps["capabilities"])


def test_authorization_role_boundaries(client, registry_fixture):
    t_pat = registry_fixture["t_pat"]
    t_h1 = registry_fixture["t_h1"]

    # Citizen patient cannot create department or capability (403)
    assert client.post("/api/hospital/departments", json={}, headers=_auth_header(t_pat)).status_code == 403
    assert client.post("/api/hospital/capabilities", json={}, headers=_auth_header(t_pat)).status_code == 403
    assert client.get("/api/hospital/profile", headers=_auth_header(t_pat)).status_code == 403

    # Hospital staff cannot call administrative verification endpoints (403)
    assert client.get("/api/admin/hospital-reviews", headers=_auth_header(t_h1)).status_code == 403
    assert client.post("/api/admin/hospital-capabilities/1/verify", json={}, headers=_auth_header(t_h1)).status_code == 403
    assert client.post("/api/admin/hospitals/1/verify", json={}, headers=_auth_header(t_h1)).status_code == 403
