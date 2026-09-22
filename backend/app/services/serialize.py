from datetime import date

from sqlalchemy.orm import Session

from ..models import Doctor, EmergencyCase, MedicalReport, Patient


def age_of(dob: str | None) -> int | None:
    try:
        d = date.fromisoformat(dob or "")
        t = date.today()
        return t.year - d.year - ((t.month, t.day) < (d.month, d.day))
    except ValueError:
        return None


def patient_dict(p: Patient) -> dict:
    return {"id": p.id, "full_name": p.user.full_name, "email": p.user.email, "phone": p.user.phone, "dob": p.dob,
            "age": age_of(p.dob), "gender": p.gender, "blood_group": p.blood_group, "address": p.address,
            "known_conditions": p.known_conditions, "known_allergies": p.known_allergies,
            "current_medications": p.current_medications, "consent_ai_summary": p.consent_ai_summary,
            "emergency_contacts": p.emergency_contacts or [], "family_code": p.family_code}


def report_dict(r: MedicalReport, with_text: bool = False) -> dict:
    d = {"id": r.id, "patient_id": r.patient_id, "title": r.title, "report_type": r.report_type,
         "report_date": r.report_date, "ocr_status": r.ocr_status, "original_filename": r.original_filename,
         "uploaded_at": r.uploaded_at.isoformat()}
    if with_text:
        d["extracted_text"] = r.extracted_text
    return d


def doctor_dict(d: Doctor) -> dict:
    return {"id": d.id, "name": d.user.full_name, "specialty": d.specialty, "qualification": d.qualification,
            "hospital_id": d.hospital_id, "is_available": d.is_available}


def case_dict(c: EmergencyCase, role: str, detail: bool = False) -> dict:
    """Role-aware: family never receives the medical brief or clinical profile."""
    p, h, d = c.patient, c.hospital, c.doctor
    out = {
        "id": c.id, "status": c.status, "priority": c.priority, "emergency_type": c.emergency_type,
        "lat": c.lat, "lng": c.lng, "current_lat": c.current_lat, "current_lng": c.current_lng,
        "eta_minutes": c.eta_minutes, "initial_eta_minutes": c.initial_eta_minutes,
        "specialty": c.specialty, "reserved_resources": c.reserved_resources or [],
        "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
        "patient": {"id": p.id, "full_name": p.user.full_name},
        "hospital": h and {"id": h.id, "name": h.name, "address": h.address, "lat": h.lat, "lng": h.lng, "phone": h.phone},
        "doctor": d and {"id": d.id, "name": d.user.full_name, "specialty": d.specialty},
        "summary_ready": c.ai_summary is not None,
    }
    if role != "family":
        out["symptoms"] = c.symptoms
        out["patient"].update({"age": age_of(p.dob), "gender": p.gender, "blood_group": p.blood_group,
                               "phone": p.user.phone, "emergency_contacts": p.emergency_contacts or []})
        out["checklist"] = c.checklist or []
        if detail:
            out["ai_summary"] = c.ai_summary
    return out
