from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

EmergencyType = Literal["stroke", "cardiac", "trauma", "diabetic", "accident", "other"]

DepartmentStatus = Literal["ACTIVE", "INACTIVE", "LIMITED"]
CapabilityCategory = Literal["DIAGNOSTIC", "SURGICAL", "CRITICAL_CARE", "STABILIZATION", "OTHER"]
CapabilityAvailability = Literal["24_7", "ON_CALL", "BUSINESS_HOURS", "CONDITIONAL"]
VerificationStatus = Literal["UNVERIFIED", "REVIEWED", "VERIFIED", "REJECTED", "SUPERSEDED", "SUSPENDED"]
ResourceOperationalStatus = Literal["FUNCTIONAL", "LIMITED", "MAINTENANCE", "NON_OPERATIONAL", "UNSTAFFED", "UNKNOWN"]
SpecialistStatus = Literal["AVAILABLE", "ON_CALL", "BUSY", "OFF_DUTY", "UNAVAILABLE", "UNKNOWN"]
FactType = Literal["CONDITION", "ALLERGY", "MEDICATION", "SURGERY", "DEVICE", "RISK", "OTHER"]
ProvenanceSourceType = Literal[
    "PATIENT_ENTERED",
    "FAMILY_REPORTED",
    "OCR_EXTRACTED",
    "HOSPITAL_IMPORTED",
    "DOCTOR_VERIFIED",
    "OTHER",
    "LEGACY_IMPORT",
]
ReferralStatus = Literal[
    "DRAFT",
    "SENT",
    "REVIEWING",
    "ACCEPTED",
    "DECLINED",
    "CLARIFICATION_REQUIRED",
    "EXPIRED",
    "CANCELLED",
]
ReferralResponseType = Literal[
    "ACCEPT",
    "DECLINE",
    "REQUEST_CLARIFICATION",
    "CLARIFICATION_PROVIDED",
    "WITHDRAW",
]
ReservationStatus = Literal["HELD", "CONFIRMED", "RELEASED", "EXPIRED", "CONSUMED"]
IncidentReporterType = Literal[
    "PATIENT", "FAMILY", "BYSTANDER", "AMBULANCE", "DISPATCHER", "HOSPITAL_STAFF", "OTHER"
]
IncidentReportType = Literal["TEXT", "VOICE_TRANSCRIPTION", "VITALS", "OBSERVATION", "OTHER"]


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


# --- Prompt 03: Domain Schemas ---

# Hospital Department Schemas
class HospitalDepartmentBase(BaseModel):
    department_name: str = Field(min_length=2, max_length=120)
    department_code: str = Field(min_length=2, max_length=40)
    description: str | None = None
    operational_status: DepartmentStatus = "ACTIVE"
    contact_information: str | None = Field(default=None, max_length=100)


class HospitalDepartmentCreate(HospitalDepartmentBase):
    hospital_id: int


class HospitalDepartmentOut(HospitalDepartmentBase):
    id: int
    hospital_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Hospital Capability Schemas
class HospitalCapabilityBase(BaseModel):
    capability_code: str = Field(min_length=2, max_length=60)
    capability_name: str = Field(min_length=2, max_length=120)
    capability_category: CapabilityCategory = "DIAGNOSTIC"
    description: str | None = None
    availability_mode: CapabilityAvailability = "24_7"
    verification_status: VerificationStatus = "UNVERIFIED"


class HospitalCapabilityCreate(HospitalCapabilityBase):
    hospital_id: int
    department_id: int | None = None


class HospitalCapabilityOut(HospitalCapabilityBase):
    id: int
    hospital_id: int
    department_id: int | None = None
    verified_by_user_id: int | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Hospital Resource & Operational Schemas
class HospitalResourceUpdate(BaseModel):
    operational_status: ResourceOperationalStatus | None = None
    staffed_capacity: int | None = Field(default=None, ge=0)
    occupied_count: int | None = Field(default=None, ge=0)
    maintenance_count: int | None = Field(default=None, ge=0)
    available: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    status_source: str | None = Field(default=None, max_length=40)
    freshness_window_minutes: int | None = Field(default=None, gt=0)
    remarks: str | None = None


class ResourceStatusHistoryOut(BaseModel):
    id: int
    hospital_resource_id: int
    previous_status: str | None
    new_status: str
    previous_available_count: int | None
    new_available_count: int
    verification_source: str
    verified_by_user_id: int | None
    verified_at: datetime
    remarks: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class HospitalResourceOut(BaseModel):
    id: int
    hospital_id: int
    department_id: int | None
    resource_type: str
    total: int
    available: int
    operational_status: ResourceOperationalStatus
    staffed_capacity: int | None
    occupied_count: int
    maintenance_count: int
    last_verified_at: datetime | None
    verified_by_user_id: int | None
    status_source: str
    freshness_window_minutes: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Specialist Availability Schemas
class SpecialistAvailabilityBase(BaseModel):
    doctor_id: int
    hospital_id: int
    department_id: int | None = None
    availability_status: SpecialistStatus = "AVAILABLE"
    shift_start: datetime
    shift_end: datetime
    on_call: bool = False


class SpecialistAvailabilityCreate(SpecialistAvailabilityBase):
    pass


class SpecialistAvailabilityOut(SpecialistAvailabilityBase):
    id: int
    last_verified_at: datetime | None = None
    verified_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Patient Clinical Fact & Provenance Schemas
class ClinicalProvenanceCreate(BaseModel):
    source_type: ProvenanceSourceType
    source_report_id: int | None = None
    source_reference: str | None = Field(default=None, max_length=255)
    source_excerpt: str | None = None
    verification_status: VerificationStatus = "UNVERIFIED"
    verification_notes: str | None = None


class ClinicalProvenanceOut(BaseModel):
    id: int
    clinical_fact_id: int
    source_type: str
    source_report_id: int | None
    source_user_id: int | None
    source_reference: str | None
    source_excerpt: str | None
    extracted_at: datetime
    verification_status: str
    verified_by_user_id: int | None
    verified_at: datetime | None
    verification_notes: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PatientClinicalFactCreate(BaseModel):
    patient_id: int
    fact_type: FactType
    fact_code: str | None = Field(default=None, max_length=80)
    fact_value: str = Field(min_length=1, max_length=255)
    normalized_value: str | None = Field(default=None, max_length=255)
    clinical_status: str = Field(default="ACTIVE", max_length=30)
    effective_from: str | None = None
    effective_to: str | None = None
    provenance: ClinicalProvenanceCreate | None = None


class PatientClinicalFactOut(BaseModel):
    id: int
    patient_id: int
    fact_type: str
    fact_code: str | None
    fact_value: str
    normalized_value: str | None
    clinical_status: str
    effective_from: str | None
    effective_to: str | None
    created_at: datetime
    updated_at: datetime
    provenance_records: list[ClinicalProvenanceOut] = []
    model_config = ConfigDict(from_attributes=True)


# Referral Schemas
class ReferralRequestCreate(BaseModel):
    emergency_case_id: int
    hospital_id: int
    request_reference: str = Field(min_length=3, max_length=60)
    request_round: int = Field(default=1, ge=1)
    response_deadline: datetime | None = None
    clarification_notes: str | None = None


class ReferralResponseCreate(BaseModel):
    response_type: ReferralResponseType
    response_notes: str | None = None
    reason_code: str | None = Field(default=None, max_length=60)


class ReferralResponseOut(BaseModel):
    id: int
    referral_request_id: int
    responding_user_id: int | None
    response_type: str
    response_notes: str | None
    reason_code: str | None
    responded_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReferralRequestOut(BaseModel):
    id: int
    emergency_case_id: int
    hospital_id: int
    request_reference: str
    request_round: int
    status: ReferralStatus
    requested_by_user_id: int | None
    requested_at: datetime
    response_deadline: datetime | None
    responded_at: datetime | None
    accepted_by_user_id: int | None
    decline_reason_code: str | None
    clarification_notes: str | None
    is_active_acceptance: bool
    created_at: datetime
    updated_at: datetime
    responses: list[ReferralResponseOut] = []
    model_config = ConfigDict(from_attributes=True)


# Resource Reservation Schemas
class ResourceReservationCreate(BaseModel):
    referral_request_id: int
    hospital_resource_id: int
    quantity: int = Field(default=1, gt=0)
    expires_at: datetime | None = None
    idempotency_key: str = Field(min_length=8, max_length=100)


class ResourceReservationOut(BaseModel):
    id: int
    referral_request_id: int
    hospital_resource_id: int
    quantity: int
    reservation_status: ReservationStatus
    held_at: datetime
    expires_at: datetime | None
    confirmed_at: datetime | None
    confirmed_by_user_id: int | None
    released_at: datetime | None
    release_reason: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Emergency Incident Report Schemas
class EmergencyIncidentReportCreate(BaseModel):
    emergency_case_id: int
    reporter_type: IncidentReporterType = "PATIENT"
    report_type: IncidentReportType = "TEXT"
    reported_text: str = Field(min_length=1)
    observed_at: datetime | None = None
    location_latitude: float | None = Field(default=None, ge=-90, le=90)
    location_longitude: float | None = Field(default=None, ge=-180, le=180)


class EmergencyIncidentReportOut(BaseModel):
    id: int
    emergency_case_id: int
    reporter_user_id: int | None
    reporter_type: str
    report_type: str
    reported_text: str
    observed_at: datetime | None
    received_at: datetime
    location_latitude: float | None
    location_longitude: float | None
    verification_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
