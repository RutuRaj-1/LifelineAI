"""Seed the LifeLine AI database with a realistic demo dataset.

10 patients, 8 doctors, 3 hospitals, 50 medical reports, 5 ready-to-fire emergency scenarios,
plus Prompt 03 Domain Extensions: hospital departments, capabilities, specialist availability,
structured clinical facts with provenance, and referral coordination records.

Usage:  python database/seed.py   (from the repo root, with backend active)
"""
import random
import secrets
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    ClinicalProvenance,
    Doctor,
    EmergencyCase,
    EmergencyIncidentReport,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    HospitalResource,
    MedicalReport,
    Patient,
    PatientClinicalFact,
    ReferralRequest,
    ReferralResponse,
    ResourceReservation,
    ResourceStatusHistory,
    SpecialistAvailability,
    User,
)
from app.security import hash_password  # noqa: E402

random.seed(7)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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

DEPARTMENTS = [
    ("Emergency Department", "EMERGENCY", "24/7 acute trauma and resuscitation unit"),
    ("Intensive Care Unit", "ICU", "Critical care, hemodynamic monitoring and mechanical ventilation"),
    ("Cardiology", "CARDIO", "Non-invasive and interventional cardiac care"),
    ("Neurology & Stroke Unit", "NEURO", "Acute stroke triage and neurological monitoring"),
    ("Trauma & Orthopaedic Surgery", "TRAUMA", "Emergency surgical intervention"),
    ("Diagnostic Radiology", "RADIO", "CT, MRI, Ultrasound, and X-Ray diagnostics"),
]

CAPABILITIES = [
    ("EMERGENCY_STABILIZATION", "Emergency Stabilization", "STABILIZATION", "24_7", "Level 1/2 acute emergency care"),
    ("ADULT_ICU", "Adult Intensive Care", "CRITICAL_CARE", "24_7", "Fully monitored multi-organ support"),
    ("MECHANICAL_VENTILATION", "Mechanical Ventilation", "CRITICAL_CARE", "24_7", "Invasive and non-invasive ventilation"),
    ("CT_IMAGING", "CT Scan (64+ Slice)", "DIAGNOSTIC", "24_7", "Rapid non-contrast and CT angiography"),
    ("CATH_LAB", "Cardiac Catheterization Lab", "DIAGNOSTIC", "24_7", "Emergency PCI and primary coronary intervention"),
    ("STROKE_THROMBOLYSIS", "Acute Stroke Thrombolysis", "STABILIZATION", "24_7", "IV thrombolysis and neuro-critical pathway"),
    ("TRAUMA_SURGERY", "Emergency Trauma Surgery", "SURGICAL", "24_7", "Damage control laparotomy and orthopedic fixation"),
]


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
        lines += ["Findings: Hemoglobin 13.2 g/dL, WBC 7.8x10^9/L, Platelets 240x10^9/L, ",
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


def seed_domain_extensions(db) -> None:
    """Idempotently seed Prompt 03 domain models: departments, capabilities, facts, provenance."""
    hospitals = db.query(Hospital).all()
    if not hospitals:
        return

    # 1. Hospital Departments
    if db.query(HospitalDepartment).count() == 0:
        for h in hospitals:
            for dept_name, dept_code, desc in DEPARTMENTS:
                dept = HospitalDepartment(
                    hospital_id=h.id,
                    department_name=dept_name,
                    department_code=dept_code,
                    description=f"{desc} (SYNTHETIC / DEMO)",
                    operational_status="ACTIVE",
                    contact_information=f"+91-20-{h.id}000{dept_code[:4]}",
                )
                db.add(dept)
        db.flush()
        print("Seeded hospital departments across all hospitals.")

    # 2. Hospital Capabilities
    if db.query(HospitalCapability).count() == 0:
        for h in hospitals:
            em_dept = db.query(HospitalDepartment).filter_by(hospital_id=h.id, department_code="EMERGENCY").first()
            for cap_code, cap_name, category, mode, desc in CAPABILITIES:
                # Sahyadri and Wakad have specialized capabilities
                if h.id == 3 and cap_code == "CATH_LAB":
                    continue  # Wakad has no cath lab in demo profile
                cap = HospitalCapability(
                    hospital_id=h.id,
                    department_id=em_dept.id if em_dept else None,
                    capability_code=cap_code,
                    capability_name=cap_name,
                    capability_category=category,
                    availability_mode=mode,
                    description=f"{desc} (SYNTHETIC / DEMO)",
                    verification_status="VERIFIED",
                )
                db.add(cap)
        db.flush()
        print("Seeded hospital capabilities.")

    # 3. Associate Hospital Resources with Departments and add Verification History
    resources = db.query(HospitalResource).all()
    for r in resources:
        if not r.department_id:
            dept_code = "EMERGENCY" if "ER" in r.resource_type else "ICU" if "ICU" in r.resource_type or "VENT" in r.resource_type else "RADIO" if "CT" in r.resource_type else "CARDIO" if "CATH" in r.resource_type else "TRAUMA"
            dept = db.query(HospitalDepartment).filter_by(hospital_id=r.hospital_id, department_code=dept_code).first()
            if dept:
                r.department_id = dept.id
            r.operational_status = "FUNCTIONAL"
            r.staffed_capacity = r.total
            r.occupied_count = max(0, r.total - r.available)
            r.maintenance_count = 0
            r.last_verified_at = utc_now()
            r.status_source = "MANUAL_AUDIT"
            r.freshness_window_minutes = 60

            # Add an initial status history record if none exists
            if not db.query(ResourceStatusHistory).filter_by(hospital_resource_id=r.id).first():
                hist = ResourceStatusHistory(
                    hospital_resource_id=r.id,
                    previous_status="FUNCTIONAL",
                    new_status="FUNCTIONAL",
                    previous_available_count=r.total,
                    new_available_count=r.available,
                    verification_source="MANUAL_AUDIT",
                    remarks="Initial verified baseline (SYNTHETIC / DEMO)",
                )
                db.add(hist)
    db.flush()

    # 4. Specialist Availability (Shifts)
    if db.query(SpecialistAvailability).count() == 0:
        doctors = db.query(Doctor).all()
        now_dt = utc_now()
        for doc in doctors:
            avail = SpecialistAvailability(
                doctor_id=doc.id,
                hospital_id=doc.hospital_id,
                availability_status="AVAILABLE" if doc.is_available else "BUSY",
                shift_start=now_dt - timedelta(hours=2),
                shift_end=now_dt + timedelta(hours=6),
                on_call=True,
                last_verified_at=now_dt,
            )
            db.add(avail)
        db.flush()
        print("Seeded specialist availability shifts.")

    # 5. Patient Clinical Facts & Provenance
    if db.query(PatientClinicalFact).count() == 0:
        patients = db.query(Patient).all()
        for idx, p in enumerate(patients):
            profile = PROFILES[idx % len(PROFILES)]
            # First medical report for this patient
            report = db.query(MedicalReport).filter_by(patient_id=p.id).first()

            # Conditions
            for c in profile["conditions"]:
                fact = PatientClinicalFact(
                    patient_id=p.id,
                    fact_type="CONDITION",
                    fact_value=c,
                    clinical_status="ACTIVE",
                )
                db.add(fact)
                db.flush()
                # Provenance from report
                db.add(ClinicalProvenance(
                    clinical_fact_id=fact.id,
                    source_type="OCR_EXTRACTED" if report else "PATIENT_ENTERED",
                    source_report_id=report.id if report else None,
                    source_reference=f"Extracted from {report.title}" if report else "Self-declared at registration",
                    source_excerpt=f"Past Medical History: {c}",
                    verification_status="REVIEWED",
                ))

            # Allergies
            for a in profile["allergies"]:
                fact = PatientClinicalFact(
                    patient_id=p.id,
                    fact_type="ALLERGY",
                    fact_value=a,
                    clinical_status="ACTIVE",
                )
                db.add(fact)
                db.flush()
                db.add(ClinicalProvenance(
                    clinical_fact_id=fact.id,
                    source_type="PATIENT_ENTERED",
                    source_reference="Patient Medical Profile",
                    verification_status="REVIEWED",
                ))

            # Medications
            for m in profile["meds"]:
                fact = PatientClinicalFact(
                    patient_id=p.id,
                    fact_type="MEDICATION",
                    fact_value=m,
                    clinical_status="ACTIVE",
                )
                db.add(fact)
                db.flush()
                db.add(ClinicalProvenance(
                    clinical_fact_id=fact.id,
                    source_type="OCR_EXTRACTED" if report else "PATIENT_ENTERED",
                    source_report_id=report.id if report else None,
                    source_reference=f"Prescription extract from {report.title}" if report else "Self-declared",
                    verification_status="REVIEWED",
                ))
        db.flush()
        print("Seeded structured clinical facts and provenance records.")

    # 6. Referral Requests & Responses (Demonstration Referral Foundation)
    if db.query(ReferralRequest).count() == 0:
        demo_case = db.query(EmergencyCase).first()
        if demo_case:
            h1 = hospitals[0]
            h2 = hospitals[1]
            ref1 = ReferralRequest(
                emergency_case_id=demo_case.id,
                hospital_id=h1.id,
                request_reference=f"REF-DEMO-CASE{demo_case.id}-HOSP1",
                request_round=1,
                status="ACCEPTED",
                is_active_acceptance=True,
                responded_at=utc_now(),
            )
            ref2 = ReferralRequest(
                emergency_case_id=demo_case.id,
                hospital_id=h2.id,
                request_reference=f"REF-DEMO-CASE{demo_case.id}-HOSP2",
                request_round=1,
                status="DECLINED",
                decline_reason_code="NO_BEDS",
                responded_at=utc_now(),
            )
            db.add_all([ref1, ref2])
            db.flush()

            db.add(ReferralResponse(
                referral_request_id=ref1.id,
                response_type="ACCEPT",
                response_notes="Cath Lab and Stroke team on standby (SYNTHETIC / DEMO)",
            ))
            db.add(ReferralResponse(
                referral_request_id=ref2.id,
                response_type="DECLINE",
                reason_code="NO_BEDS",
                response_notes="Emergency capacity at peak (SYNTHETIC / DEMO)",
            ))

            # Sample reservation for accepted referral
            res_bed = db.query(HospitalResource).filter_by(hospital_id=h1.id, resource_type="ER_BED").first()
            if res_bed:
                db.add(ResourceReservation(
                    referral_request_id=ref1.id,
                    hospital_resource_id=res_bed.id,
                    quantity=1,
                    reservation_status="CONFIRMED",
                    idempotency_key=f"DEMO-RES-{secrets.token_hex(6)}",
                ))

            # Incident report
            db.add(EmergencyIncidentReport(
                emergency_case_id=demo_case.id,
                reporter_type="FAMILY",
                report_type="TEXT",
                reported_text="Patient showed acute right-sided weakness and facial droop starting 25 mins ago (SYNTHETIC / DEMO).",
                verification_status="REVIEWED",
            ))
        db.flush()
        print("Seeded referral requests, responses, and incident report.")

    db.commit()


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(User).count() == 0:
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
        print(f"Base seed completed: {len(hospitals)} hospitals, {len(doctors)} doctors, {len(patients)} patients.")

    # Seed or extend domain models idempotently
    seed_domain_extensions(db)

    print("\nDatabase is fully seeded with baseline entities and Prompt 03 domain extensions.")
    print("  Departments:              ", db.query(HospitalDepartment).count())
    print("  Capabilities:             ", db.query(HospitalCapability).count())
    print("  Specialist Availabilities:", db.query(SpecialistAvailability).count())
    print("  Clinical Facts:           ", db.query(PatientClinicalFact).count())
    print("  Clinical Provenance:      ", db.query(ClinicalProvenance).count())
    print("  Referral Requests:        ", db.query(ReferralRequest).count())
    print("  Referral Responses:       ", db.query(ReferralResponse).count())
    print("  Resource Reservations:    ", db.query(ResourceReservation).count())
    print("  Incident Reports:         ", db.query(EmergencyIncidentReport).count())
    db.close()


if __name__ == "__main__":
    main()
