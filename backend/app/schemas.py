from typing import Literal

from pydantic import BaseModel, EmailStr, Field

EmergencyType = Literal["stroke", "cardiac", "trauma", "diabetic", "accident", "other"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["patient", "family"] = "patient"
    phone: str | None = None
    dob: str | None = None
    gender: str | None = None
    blood_group: str | None = None
    family_code: str | None = Field(default=None, description="Required for role=family (from the patient's profile)")


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class EmergencyContact(BaseModel):
    name: str
    phone: str
    relation: str | None = None


class PatientUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    dob: str | None = None
    gender: str | None = None
    blood_group: str | None = None
    address: str | None = None
    known_conditions: str | None = None
    known_allergies: str | None = None
    current_medications: str | None = None
    consent_ai_summary: bool | None = None
    emergency_contacts: list[EmergencyContact] | None = None


class EmergencyIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    emergency_type: EmergencyType
    symptoms: str | None = Field(default=None, max_length=500)


class LocationIn(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class AssignIn(BaseModel):
    case_id: int
    doctor_id: int


class ReserveIn(BaseModel):
    case_id: int
    resource_type: Literal["ER_BED", "ICU_BED", "OT", "CT_SCANNER", "CATH_LAB", "VENTILATOR"]


class CaseRef(BaseModel):
    case_id: int


class ChecklistIn(BaseModel):
    index: int = Field(ge=0)
    done: bool
