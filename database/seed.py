"""Seed the LifeLine AI database with a realistic demo dataset.

10 patients, 8 doctors, 3 hospitals, 50 medical reports, 5 ready-to-fire emergency scenarios
(stroke, cardiac, trauma, diabetic, accident - see backend/app/scenarios.py).

Usage:  python database/seed.py   (from the repo root, with backend/.venv active)
"""
import random
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Doctor, Hospital, HospitalResource, MedicalReport, Patient, User  # noqa: E402
from app.security import hash_password  # noqa: E402

random.seed(7)

HOSPITALS = [
    {"name": "CityCare Multispecialty Hospital", "address": "FC Road, Shivajinagar", "city": "Pune",
     "lat": 18.5304, "lng": 73.8467, "phone": "+91-20-40001111",
     "capabilities": ["stroke", "cardiac", "trauma", "diabetic", "accident"],
     "resources": {"ER_BED": 12, "ICU_BED": 6, "OT": 4, "CT_SCANNER": 2, "CATH_LAB": 1, "VENTILATOR": 8}},
    {"name": "Sahyadri Heart & Trauma Institute", "address": "Baner Road, Baner", "city": "Pune",
     "lat": 18.5636, "lng": 73.7898, "phone": "+91-20-40002222",
     "capabilities": ["cardiac", "trauma", "accident"],
     "resources": {"ER_BED": 10, "ICU_BED": 5, "OT": 3, "CT_SCANNER": 1, "CATH_LAB": 2, "VENTILATOR": 6}},
    {"name": "Wakad Neuro & General Hospital", "address": "Mumbai-Pune Highway, Wakad", "city": "Pune",
     "lat": 18.5975, "lng": 73.7622, "phone": "+91-20-40003333",
     "capabilities": ["stroke", "trauma", "diabetic", "accident"],
     "resources": {"ER_BED": 8, "ICU_BED": 4, "OT": 2, "CT_SCANNER": 1, "CATH_LAB": 0, "VENTILATOR": 5}},
]

DOCTORS = [
    ("Ananya Kulkarni", "Neurology", "MD, DM Neurology", 0), ("Rohan Deshmukh", "Cardiology", "MD, DM Cardiology", 0),
    ("Priya Nair", "Emergency Medicine", "MD Emergency Medicine", 0), ("Vikram Singh", "Trauma Surgery", "MS Surgery", 0),
    ("Sanjana Rao", "Cardiology", "MD, DM Cardiology", 1), ("Arjun Mehta", "Trauma Surgery", "MS Surgery", 1),
    ("Kavita Joshi", "Neurology", "MD, DM Neurology", 2), ("Imran Shaikh", "Endocrinology", "MD Endocrinology", 2),
]

PATIENTS = [
    ("Ramesh Iyer", "1968-03-14", "Male", "B+"), ("Sunita Patil", "1975-07-22", "Female", "O+"),
    ("Farhan Ansari", "1990-11-05", "Male", "A+"), ("Meena Gupta", "1958-01-30", "Female", "AB+"),
    ("Suresh Naik", "1982-09-18", "Male", "O-"), ("Anjali Verma", "1995-05-09", "Female", "B-"),
    ("Deepak Chavan", "1970-12-25", "Male", "A-"), ("Pooja Bhosale", "1988-04-02", "Female", "O+"),
    ("Ravindra Pawar", "1962-06-11", "Male", "B+"), ("Neha Kulkarni", "1993-08-27", "Female", "A+"),
]

# Per-patient clinical facts used to generate report text. Index 0-4 back the 5 emergency scenarios.
PROFILES = [
    {"conditions": ["Hypertension", "Type 2 Diabetes Mellitus", "Atrial Fibrillation"],
     "meds": ["Amlodipine 5mg once daily", "Metformin 500mg twice daily", "Apixaban 5mg twice daily"],
     "allergies": ["Penicillin"], "surgeries": ["Appendectomy (2005)"],
     "risks": ["On anticoagulant (Apixaban) - bleeding risk"]},
    {"conditions": ["Coronary Artery Disease", "Hyperlipidemia"],
     "meds": ["Atorvastatin 20mg once daily", "Clopidogrel 75mg once daily", "Metoprolol 25mg twice daily"],
     "allergies": ["Sulfa drugs"], "surgeries": ["Coronary angioplasty with stent (2021)"],
     "risks": ["On antiplatelet (Clopidogrel) - bleeding risk", "Prior cardiac stent"]},
    {"conditions": ["Asthma"], "meds": ["Salbutamol inhaler as needed", "Montelukast 10mg at night"],
     "allergies": ["NKDA"], "surgeries": ["None"], "risks": ["History of exercise-induced bronchospasm"]},
    {"conditions": ["Type 2 Diabetes Mellitus", "Chronic Kidney Disease Stage 2"],
     "meds": ["Insulin glargine 20 units at night", "Insulin aspart with meals", "Losartan 50mg once daily"],
     "allergies": ["Iodinated contrast"], "surgeries": ["Cataract surgery, left eye (2019)"],
     "risks": ["Insulin-dependent - hypoglycemia risk", "Reduced renal clearance"]},
    {"conditions": ["Hypertension"], "meds": ["Telmisartan 40mg once daily"], "allergies": ["Latex"],
     "surgeries": ["Tibia fracture fixation (2016)"], "risks": ["Metal implant in left leg"]},
    {"conditions": ["Epilepsy"], "meds": ["Levetiracetam 500mg twice daily"], "allergies": ["NKDA"],
     "surgeries": ["None"], "risks": ["History of seizures - airway risk during episode"]},
    {"conditions": ["Hypertension", "Benign Prostatic Hyperplasia"], "meds": ["Amlodipine 5mg once daily", "Tamsulosin 0.4mg at night"],
     "allergies": ["Aspirin"], "surgeries": ["Hernia repair (2010)"], "risks": ["Aspirin allergy - avoid NSAIDs"]},
    {"conditions": ["Hypothyroidism"], "meds": ["Levothyroxine 75mcg once daily"], "allergies": ["NKDA"],
     "surgeries": ["Caesarean section (2017)"], "risks": ["None significant"]},
    {"conditions": ["Chronic Obstructive Pulmonary Disease", "Hypertension"],
     "meds": ["Tiotropium inhaler once daily", "Amlodipine 10mg once daily"], "allergies": ["Codeine"],
     "surgeries": ["None"], "risks": ["Smoker - reduced respiratory reserve", "Codeine allergy - avoid opioid analgesics"]},
    {"conditions": ["Migraine"], "meds": ["Sumatriptan 50mg as needed"], "allergies": ["NKDA"],
     "surgeries": ["Wisdom tooth extraction (2015)"], "risks": ["None significant"]},
]

REPORT_TEMPLATES = ["Discharge Summary", "Prescription", "Lab Report - CBC & Metabolic Panel",
                    "Consultation Note", "Diagnostic Imaging Report"]


def report_text(name: str, profile: dict, kind: str, when: date) -> str:
    lines = [f"Patient: {name}", f"Report Type: {kind}", f"Date: {when.isoformat()}", ""]
    if kind == "Prescription":
        lines += ["Current Medications:", *[f"- {m}" for m in profile["meds"]], "",
                  f"Known Allergies: {', '.join(profile['allergies'])}"]
    elif kind == "Discharge Summary":
        lines += ["Past Medical History:", *[f"- {c}" for c in profile["conditions"]], "",
                  "Surgical History:", *[f"- {s}" for s in profile["surgeries"]], "",
                  f"Known Allergies: {', '.join(profile['allergies'])}", "",
                  "Current Medications:", *[f"- {m}" for m in profile["meds"]], "",
                  "Risk Flags:", *[f"- {r}" for r in profile["risks"]]]
    elif kind == "Lab Report - CBC & Metabolic Panel":
        lines += ["Findings: Hemoglobin 13.2 g/dL, WBC 7.8x10^9/L, Platelets 240x10^9/L, "
                  "Fasting glucose 118 mg/dL, Creatinine 0.9 mg/dL, eGFR 88 mL/min.",
                  "Impression: Values reviewed by ordering physician; no acute abnormality flagged by lab."]
    elif kind == "Consultation Note":
        lines += ["Reason for visit: Routine follow-up.", "Known conditions: " + ", ".join(profile["conditions"]),
                  "Plan: Continue current medications; " + ", ".join(profile["meds"]) + ".",
                  f"Allergies noted: {', '.join(profile['allergies'])}."]
    else:
        lines += ["Modality: X-Ray / Ultrasound (as ordered).", "Findings: No acute abnormality on review.",
                  "Relevant history considered: " + ", ".join(profile["conditions"]) + "."]
    return "\n".join(lines)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(User).count():
        print("Database already has data - skipping seed. Delete backend/lifeline.db to reseed.")
        return

    hospitals = []
    for h in HOSPITALS:
        row = Hospital(name=h["name"], address=h["address"], city=h["city"], lat=h["lat"], lng=h["lng"],
                       phone=h["phone"], capabilities=h["capabilities"])
        db.add(row)
        db.flush()
        for rtype, total in h["resources"].items():
            db.add(HospitalResource(hospital_id=row.id, resource_type=rtype, total=total, available=total))
        hospitals.append(row)

    doctors = []
    for i, (name, specialty, qual, h_idx) in enumerate(DOCTORS):
        u = User(email=f"doctor{i + 1}@lifeline.demo", password_hash=hash_password("Doctor@123"),
                full_name=name, role="doctor", phone=f"+91-90000{10000 + i}")
        db.add(u)
        db.flush()
        d = Doctor(user_id=u.id, hospital_id=hospitals[h_idx].id, specialty=specialty, qualification=qual)
        db.add(d)
        doctors.append(d)

    # One hospital-staff login per hospital, for the dashboard
    for i, h in enumerate(hospitals):
        db.add(User(email=f"hospital{i + 1}@lifeline.demo", password_hash=hash_password("Hospital@123"),
                    full_name=f"{h.name} - Admin Desk", role="hospital", hospital_id=h.id))

    patients = []
    for i, (name, dob, gender, bg) in enumerate(PATIENTS):
        u = User(email=f"patient{i + 1}@lifeline.demo", password_hash=hash_password("Patient@123"),
                full_name=name, role="patient", phone=f"+91-98000{20000 + i}")
        db.add(u)
        db.flush()
        profile = PROFILES[i]
        p = Patient(user_id=u.id, dob=dob, gender=gender, blood_group=bg,
                   address=f"{100 + i} Model Colony, Pune", consent_ai_summary=True,
                   known_conditions=", ".join(profile["conditions"]), known_allergies=", ".join(profile["allergies"]),
                   current_medications=", ".join(profile["meds"]),
                   emergency_contacts=[{"name": f"Contact for {name}", "phone": f"+91-99000{30000 + i}", "relation": "Family"}],
                   family_code=secrets.token_hex(3).upper())
        db.add(p)
        db.flush()
        patients.append(p)

    # First family member, linked to patient 1, for demoing the Family Portal
    db.add(User(email="family1@lifeline.demo", password_hash=hash_password("Family@123"), full_name="Meera Iyer",
               role="family", linked_patient_id=patients[0].id))

    # 50 medical reports across the 10 patients (5 each, one of each template type)
    today = date.today()
    for i, p in enumerate(patients):
        profile = PROFILES[i]
        for j, kind in enumerate(REPORT_TEMPLATES):
            when = today - timedelta(days=(j + 1) * 40 + i)
            text = report_text(PATIENTS[i][0], profile, kind, when)
            db.add(MedicalReport(patient_id=p.id, title=f"{kind} - {when.strftime('%b %Y')}", report_type=kind,
                                 original_filename=None, storage_url=None, extracted_text=text, ocr_status="ok",
                                 report_date=when.isoformat()))

    db.commit()
    print(f"Seeded {len(hospitals)} hospitals, {len(doctors)} doctors, {len(patients)} patients, "
         f"{len(patients) * len(REPORT_TEMPLATES)} medical reports.")
    print("\nDemo logins (password shown):")
    print("  Patients:  patient1..patient10@lifeline.demo / Patient@123")
    print("  Doctors:   doctor1..doctor8@lifeline.demo / Doctor@123")
    print("  Hospitals: hospital1..hospital3@lifeline.demo / Hospital@123")
    print("  Family:    family1@lifeline.demo / Family@123  (linked to patient1)")
    print("\n5 ready-to-fire emergency scenarios are defined in backend/app/scenarios.py")
    print("(stroke->patient1, cardiac->patient2, trauma->patient3, diabetic->patient4, accident->patient5).")
    db.close()


if __name__ == "__main__":
    main()
