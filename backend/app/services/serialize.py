from datetime import date

from sqlalchemy.orm import Session

from ..models import (
    ClinicalProvenance,
    Doctor,
    EmergencyCase,
    Hospital,
    HospitalCapability,
    HospitalDepartment,
    MedicalReport,
    Patient,
    PatientClinicalFact,
)


def age_of(dob: str | None) -> int | None:
    try:
        d = date.fromisoformat(dob or "")
        t = date.today()
        return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    except ValueError:
        return None


def patient_dict(p: Patient) -> dict:
    return {
        "id": p.id,
        "full_name": p.user.full_name,
        "email": p.user.email,
        "phone": p.user.phone,
        "dob": p.dob,
        "age": age_of(p.dob),
        "gender": p.gender,
        "blood_group": p.blood_group,
        "address": p.address,
        "known_conditions": p.known_conditions,
        "known_allergies": p.known_allergies,
        "current_medications": p.current_medications,
        "consent_ai_summary": p.consent_ai_summary,
        "emergency_contacts": p.emergency_contacts or [],
        "family_code": p.family_code,
    }


def report_dict(r: MedicalReport, with_text: bool = False) -> dict:
    d = {
        "id": r.id,
        "patient_id": r.patient_id,
        "title": r.title,
        "report_type": r.report_type,
        "report_date": r.report_date,
        "ocr_status": r.ocr_status,
        "original_filename": r.original_filename,
        "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
    }
    if with_text:
        d["extracted_text"] = r.extracted_text
    return d


def provenance_dict(pr: ClinicalProvenance) -> dict:
    return {
        "id": pr.id,
        "clinical_fact_id": pr.clinical_fact_id,
        "source_type": pr.source_type,
        "source_report_id": pr.source_report_id,
        "source_user_id": pr.source_user_id,
        "source_reference": pr.source_reference,
        "source_excerpt": pr.source_excerpt,
        "extracted_at": pr.extracted_at.isoformat() if pr.extracted_at else None,
        "verification_status": pr.verification_status,
        "verified_by_user_id": pr.verified_by_user_id,
        "verified_at": pr.verified_at.isoformat() if pr.verified_at else None,
        "verification_notes": pr.verification_notes,
        "created_at": pr.created_at.isoformat() if pr.created_at else None,
    }


def fact_dict(f: PatientClinicalFact) -> dict:
    return {
        "id": f.id,
        "patient_id": f.patient_id,
        "fact_type": f.fact_type,
        "fact_code": f.fact_code,
        "fact_value": f.fact_value,
        "normalized_value": f.normalized_value,
        "clinical_status": f.clinical_status,
        "effective_from": f.effective_from,
        "effective_to": f.effective_to,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
        "provenance_records": [provenance_dict(pr) for pr in (f.provenance_records or [])],
    }


def hospital_dict(h: Hospital, detail: bool = False) -> dict:
    d = {
        "id": h.id,
        "name": h.name,
        "address": h.address,
        "city": h.city,
        "phone": h.phone,
        "lat": h.lat,
        "lng": h.lng,
        "status": getattr(h, "status", "VERIFIED"),
        "hospital_type": getattr(h, "hospital_type", "GENERAL"),
        "contact_email": getattr(h, "contact_email", None),
        "department_count": len(h.departments) if hasattr(h, "departments") and h.departments else 0,
        "capability_count": len(h.capabilities_rel) if hasattr(h, "capabilities_rel") and h.capabilities_rel else 0,
    }
    if detail:
        d.update({
            "verification_notes": getattr(h, "verification_notes", None),
            "verified_at": h.verified_at.isoformat() if getattr(h, "verified_at", None) else None,
            "created_at": h.created_at.isoformat() if getattr(h, "created_at", None) else None,
            "updated_at": h.updated_at.isoformat() if getattr(h, "updated_at", None) else None,
        })
    return d


def department_dict(d: HospitalDepartment) -> dict:
    return {
        "id": d.id,
        "hospital_id": d.hospital_id,
        "department_name": d.department_name,
        "department_code": d.department_code,
        "description": d.description,
        "operational_status": d.operational_status,
        "contact_information": d.contact_information,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def capability_dict(c: HospitalCapability) -> dict:
    return {
        "id": c.id,
        "hospital_id": c.hospital_id,
        "department_id": c.department_id,
        "department_name": c.department.department_name if c.department else None,
        "capability_code": c.capability_code,
        "capability_name": c.capability_name,
        "capability_category": c.capability_category,
        "description": c.description,
        "availability_mode": c.availability_mode,
        "verification_status": c.verification_status,
        "verified_by_user_id": c.verified_by_user_id,
        "verified_at": c.verified_at.isoformat() if c.verified_at else None,
        "verification_notes": getattr(c, "verification_notes", None),
        "verification_source": getattr(c, "verification_source", None),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def doctor_dict(d: Doctor) -> dict:
    return {
        "id": d.id,
        "name": d.user.full_name,
        "specialty": d.specialty,
        "qualification": d.qualification,
        "hospital_id": d.hospital_id,
        "is_available": d.is_available,
    }


def case_dict(c: EmergencyCase, role: str, detail: bool = False) -> dict:
    """Role-aware: family never receives the medical brief or clinical profile."""
    p, h, d = c.patient, c.hospital, c.doctor
    out = {
        "id": c.id,
        "status": c.status,
        "priority": c.priority,
        "emergency_type": c.emergency_type,
        "lat": c.lat,
        "lng": c.lng,
        "current_lat": c.current_lat,
        "current_lng": c.current_lng,
        "eta_minutes": c.eta_minutes,
        "initial_eta_minutes": c.initial_eta_minutes,
        "specialty": c.specialty,
        "reserved_resources": c.reserved_resources or [],
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "patient": {"id": p.id, "full_name": p.user.full_name},
        "hospital": h and {
            "id": h.id,
            "name": h.name,
            "address": h.address,
            "lat": h.lat,
            "lng": h.lng,
            "phone": h.phone,
        },
        "doctor": d and {"id": d.id, "name": d.user.full_name, "specialty": d.specialty},
        "summary_ready": c.ai_summary is not None,
    }
    if role != "family":
        out["symptoms"] = c.symptoms
        out["patient"].update({
            "age": age_of(p.dob),
            "gender": p.gender,
            "blood_group": p.blood_group,
            "phone": p.user.phone,
            "emergency_contacts": p.emergency_contacts or [],
        })
        out["checklist"] = c.checklist or []
        if detail:
            out["ai_summary"] = c.ai_summary
    return out
