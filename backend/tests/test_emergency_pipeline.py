"""End-to-end: SOS -> AI brief -> doctor assignment -> resource reservation, entirely offline
(no OpenAI/Google Maps keys needed - falls back to extractive RAG + haversine ETA)."""
import time


def _register(client, email, role="patient", **extra):
    body = {"email": email, "password": "supersecret1", "full_name": "Test User", "role": role, **extra}
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["user"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _seed_hospital(client, tag="e2e"):
    """Seed one capable hospital with an ER bed, directly via the ORM (no public hospital-creation API)."""
    from app.db import SessionLocal
    from app.models import Doctor, Hospital, HospitalResource, User
    from app.security import hash_password

    with SessionLocal() as db:
        h = Hospital(name=f"Test General Hospital {tag}", address="Test St", city="TestCity", lat=18.52, lng=73.85,
                    capabilities=["stroke", "cardiac", "trauma", "diabetic", "accident"])
        db.add(h)
        db.flush()
        db.add(HospitalResource(hospital_id=h.id, resource_type="ER_BED", total=5, available=5))
        db.add(HospitalResource(hospital_id=h.id, resource_type="CT_SCANNER", total=1, available=1))
        u = User(email=f"doc-{tag}@example.com", password_hash=hash_password("supersecret1"), full_name="Dr. Test",
                role="doctor")
        db.add(u)
        db.flush()
        db.add(Doctor(user_id=u.id, hospital_id=h.id, specialty="Neurology"))
        db.commit()
        return h.id, h.name


def test_full_emergency_pipeline(client):
    hospital_id, hospital_name = _seed_hospital(client, "e2e")
    token, user = _register(client, "patient-e2e@example.com")

    # Upload a report containing a clear, extractable fact set
    report = (
        "Patient: Test User\nReport Type: Discharge Summary\n\n"
        "Past Medical History:\n- Hypertension\n\nKnown Allergies: Penicillin\n\n"
        "Current Medications:\n- Amlodipine 5mg once daily\n\nRisk Flags:\n- History of stroke\n"
    )
    files = {"file": ("summary.txt", report, "text/plain")}
    r = client.post("/api/report/upload", headers=_auth(token),
                    data={"title": "Discharge Summary", "report_type": "discharge"}, files=files)
    assert r.status_code == 201, r.text

    # Trigger SOS
    r = client.post("/api/emergency", headers=_auth(token),
                    json={"lat": 18.521, "lng": 73.851, "emergency_type": "stroke", "symptoms": "slurred speech"})
    assert r.status_code == 201, r.text
    case_id = r.json()["id"]

    # A second SOS while one is active must be rejected
    r_dup = client.post("/api/emergency", headers=_auth(token),
                        json={"lat": 18.521, "lng": 73.851, "emergency_type": "stroke"})
    assert r_dup.status_code == 409

    # Poll until the async agent pipeline completes (generous timeout for CI)
    deadline = time.time() + 45
    case = None
    while time.time() < deadline:
        case = client.get(f"/api/emergency/{case_id}", headers=_auth(token)).json()
        if case["status"] in ("ROOM_RESERVED", "DOCTOR_ASSIGNED"):
            break
        time.sleep(0.3)

    assert case is not None
    assert case["hospital"]["name"] == hospital_name
    assert case["doctor"]["specialty"] == "Neurology"
    assert "ER_BED" in case["reserved_resources"]
    assert case["ai_summary"] is not None
    brief = case["ai_summary"]
    assert any("penicillin" in i["text"].lower() for i in brief["allergies"])
    assert all(i["evidence"] for section in
              ("major_diseases", "current_medicines", "allergies", "critical_risks") for i in brief[section])
    assert "diagnosis" not in brief["disclaimer"].lower() or "not a diagnosis" in brief["disclaimer"].lower()


def test_family_view_hides_clinical_detail(client):
    _seed_hospital(client, "fam")
    ptoken, puser = _register(client, "patient-fam@example.com")
    p = client.get("/api/patient/me", headers=_auth(ptoken)).json()
    ftoken, _ = _register(client, "family-fam@example.com", role="family", family_code=p["family_code"])

    r = client.post("/api/emergency", headers=_auth(ptoken),
                    json={"lat": 18.521, "lng": 73.851, "emergency_type": "cardiac", "symptoms": "chest pain"})
    case_id = r.json()["id"]

    fam_view = client.get(f"/api/emergency/{case_id}", headers=_auth(ftoken)).json()
    assert "symptoms" not in fam_view
    assert "ai_summary" not in fam_view
    assert fam_view["status"]  # still gets status/ETA/hospital
