from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

EmergencyType = Literal["stroke", "cardiac", "trauma", "diabetic", "accident", "other"]

DepartmentStatus = Literal["ACTIVE", "INACTIVE", "LIMITED"]
CapabilityCategory = str
HospitalStatus = Literal["DRAFT", "SUBMITTED", "UNDER_REVIEW", "VERIFIED", "REJECTED", "SUSPENDED", "INACTIVE"]
HospitalType = Literal["GENERAL", "TERTIARY_CARE", "TRAUMA_CENTER", "SPECIALTY", "COMMUNITY", "OTHER"]
CapabilityAvailability = Literal["24_7", "ON_CALL", "BUSINESS_HOURS", "CONDITIONAL"]
VerificationStatus = Literal["UNVERIFIED", "PENDING_REVIEW", "REVIEWED", "VERIFIED", "REJECTED", "SUPERSEDED", "SUSPENDED", "EXPIRED"]
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

# Hospital Registry & Profile Schemas
class HospitalOut(BaseModel):
    id: int
    name: str
    address: str
    city: str
    phone: str | None = None
    lat: float
    lng: float
    status: HospitalStatus = "VERIFIED"
    hospital_type: str = "GENERAL"
    contact_email: str | None = None
    verification_notes: str | None = None
    verified_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    department_count: int = 0
    capability_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class HospitalProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=30)
    contact_email: EmailStr | None = None
    hospital_type: str | None = Field(default=None, max_length=50)


# Hospital Department Schemas
class HospitalDepartmentBase(BaseModel):
    department_name: str = Field(min_length=2, max_length=120)
    department_code: str = Field(min_length=2, max_length=40)
    description: str | None = None
    operational_status: DepartmentStatus = "ACTIVE"
    contact_information: str | None = Field(default=None, max_length=100)


class HospitalDepartmentCreate(HospitalDepartmentBase):
    hospital_id: int


class HospitalDepartmentUserCreate(BaseModel):
    department_name: str = Field(min_length=2, max_length=120)
    department_code: str = Field(min_length=2, max_length=40)
    description: str | None = None
    operational_status: DepartmentStatus = "ACTIVE"
    contact_information: str | None = Field(default=None, max_length=100)


class HospitalDepartmentUpdate(BaseModel):
    department_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    operational_status: DepartmentStatus | None = None
    contact_information: str | None = Field(default=None, max_length=100)


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


class HospitalCapabilityUserCreate(BaseModel):
    capability_code: str = Field(min_length=2, max_length=60)
    capability_name: str = Field(min_length=2, max_length=120)
    capability_category: CapabilityCategory = "DIAGNOSTIC"
    department_id: int | None = None
    description: str | None = None
    availability_mode: CapabilityAvailability = "24_7"


class HospitalCapabilityUpdate(BaseModel):
    capability_name: str | None = Field(default=None, min_length=2, max_length=120)
    capability_category: CapabilityCategory | None = None
    department_id: int | None = None
    description: str | None = None
    availability_mode: CapabilityAvailability | None = None


class VerificationActionIn(BaseModel):
    notes: str | None = None
    verification_source: str | None = None


class HospitalCapabilityOut(HospitalCapabilityBase):
    id: int
    hospital_id: int
    department_id: int | None = None
    verified_by_user_id: int | None = None
    verified_at: datetime | None = None
    verification_notes: str | None = None
    verification_source: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Hospital Resource & Operational Schemas
class ResourceAttestationIn(BaseModel):
    staffed_capacity: int | None = Field(default=None, ge=0)
    occupied_count: int = Field(default=0, ge=0)
    maintenance_count: int = Field(default=0, ge=0)
    operational_status: ResourceOperationalStatus = "FUNCTIONAL"
    status_source: str = Field(default="MANUAL", max_length=40)
    remarks: str | None = None
    notes: str | None = None
    freshness_window_minutes: int | None = Field(default=None, gt=0)


class ResourceConfigUpdate(BaseModel):
    department_id: int | None = None
    total: int | None = Field(default=None, ge=0)
    freshness_window_minutes: int | None = Field(default=None, gt=0)


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


class OperationalResourceOut(BaseModel):
    id: int
    hospital_id: int
    department_id: int | None = None
    department_name: str | None = None
    resource_type: str
    total: int
    physical_capacity: int
    staffed_capacity: int
    occupied_count: int
    maintenance_count: int
    active_reserved_holds: int
    usable_capacity: int
    available: int
    operational_status: str
    freshness_status: str
    status_source: str
    last_verified_at: datetime | None = None
    freshness_window_minutes: int
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class PublicResourceOut(BaseModel):
    resource_type: str
    usable_capacity: int
    operational_status: str
    freshness_status: str
    last_verified_at: datetime | None = None
    is_confirmed_fresh: bool = False
    disclaimer: str = (
        "Operational resource capacity reflects latest hospital attestation and may fluctuate. "
        "Real-time allocation is confirmed only during emergency referral coordination."
    )


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


class PatientSelfFactCreate(BaseModel):
    fact_type: FactType = "CONDITION"
    fact_code: str | None = Field(default=None, max_length=80)
    fact_value: str = Field(min_length=1, max_length=255)
    normalized_value: str | None = Field(default=None, max_length=255)
    clinical_status: str = Field(default="ACTIVE", max_length=30)
    effective_from: str | None = None
    effective_to: str | None = None
    notes: str | None = None


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


class PatientClinicalFactUpdate(BaseModel):
    fact_value: str | None = Field(default=None, min_length=1, max_length=255)
    normalized_value: str | None = None
    clinical_status: str | None = Field(default=None, max_length=30)
    effective_from: str | None = None
    effective_to: str | None = None
    update_notes: str | None = None


class HealthTimelineEvent(BaseModel):
    id: str
    event_type: str  # REPORT_UPLOADED, CLINICAL_FACT, EMERGENCY_INCIDENT, EMERGENCY_VISIT, PROFILE_UPDATE
    title: str
    description: str
    event_date: str | None = None
    recorded_at: str
    source_reference: str | None = None
    provenance_source: str | None = None
    verification_status: str | None = None
    has_supporting_document: bool = False
    report_id: int | None = None
    metadata: dict = {}


class HealthTimelineResponse(BaseModel):
    events: list[HealthTimelineEvent]
    total: int
    limit: int
    offset: int


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


# Multi-Hospital Referral Engine Schemas (Prompt 07)
ReferralDeclineReasonCode = Literal[
    "NO_BEDS",
    "NO_SPECIALIST",
    "DIVERT",
    "RESOURCE_UNAVAILABLE",
    "CLINICAL_REVIEW_DECLINED",
    "CAPACITY_UNAVAILABLE",
    "REQUIRED_SPECIALIST_UNAVAILABLE",
    "REQUIRED_RESOURCE_UNAVAILABLE",
    "DEPARTMENT_UNAVAILABLE",
    "OTHER",
]


class ReferralBroadcastIn(BaseModel):
    hospital_ids: list[int] = Field(min_length=1)
    requested_resource_type: str = Field(default="ICU_BED", min_length=2, max_length=40)
    priority: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = None
    response_timeout_minutes: int = Field(default=15, ge=1, le=1440)
    idempotency_key: str | None = Field(default=None, max_length=100)


class ReferralAcceptIn(BaseModel):
    notes: str | None = None


class ReferralDeclineIn(BaseModel):
    reason_code: str = Field(default="OTHER", max_length=60)
    notes: str | None = None


class ReferralClarificationIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


class ReferralClarificationAnswerIn(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)


class ReferralCancelIn(BaseModel):
    reason: str | None = None


class ReferralResponseOut(BaseModel):
    id: int
    referral_request_id: int
    responding_user_id: int | None
    responding_user_name: str | None = None
    response_type: str
    response_notes: str | None
    reason_code: str | None
    responded_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReferralOut(BaseModel):
    id: int
    emergency_case_id: int
    hospital_id: int
    hospital_name: str | None = None
    hospital_city: str | None = None
    request_reference: str
    request_round: int
    status: str
    requested_resource_type: str | None
    priority: int | None
    requested_at: datetime
    response_deadline: datetime | None
    responded_at: datetime | None
    is_active_acceptance: bool
    decline_reason_code: str | None
    clarification_notes: str | None
    notes: str | None
    responses: list[ReferralResponseOut] = []
    patient_summary: dict | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EligibleHospitalResourceSummary(BaseModel):
    resource_type: str
    usable_capacity: int
    staffed_capacity: int | None = None
    operational_status: str
    freshness_status: str
    is_confirmed_fresh: bool


class EligibleHospitalItem(BaseModel):
    hospital_id: int
    hospital_name: str
    city: str | None = None
    address: str | None = None
    phone: str | None = None
    eligibility_status: str
    is_eligible: bool
    reasons: list[str] = []
    verified_capabilities: list[str] = []
    resource_summary: EligibleHospitalResourceSummary | None = None
    is_dispatched: bool = False
    referral_request_id: int | None = None
    current_referral_status: str | None = None


class ReferralEligibilityOut(BaseModel):
    emergency_case_id: int
    emergency_type: str
    specialty: str | None = None
    requested_resource_type: str
    referral_round: int
    eligible_hospitals: list[EligibleHospitalItem] = []


# ==============================================================================
# Prompt 08: Emergency Orchestration & Clinical Handover Schemas
# ==============================================================================

class SOSInitiateIn(BaseModel):
    emergency_type: str = Field(..., description="Emergency type, e.g. stroke, cardiac, trauma, etc.")
    symptoms: str | None = None
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    origin_type: str = "PATIENT_SOS"
    patient_id: int | None = None
    location_source: str = "DEVICE_GPS"
    location_accuracy_meters: float | None = None
    idempotency_key: str | None = None


class EmergencyLocationUpdateIn(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    location_source: str = "DEVICE_GPS"
    location_accuracy_meters: float | None = None


class EmergencyIncidentReportIn(BaseModel):
    reported_text: str = Field(..., min_length=2)
    reporter_type: str = "PATIENT"  # PATIENT | FAMILY | BYSTANDER | AMBULANCE | DISPATCHER | DOCTOR | OTHER
    report_type: str = "TEXT"  # TEXT | VOICE_TRANSCRIPTION | VITALS | OBSERVATION | OTHER
    observed_at: datetime | None = None
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_accuracy_meters: float | None = None
    audio_storage_url: str | None = None
    transcription_status: str = "NONE"
    parent_report_id: int | None = None
    idempotency_key: str | None = None


class EmergencyIncidentReportOut(BaseModel):
    id: int
    emergency_case_id: int
    reporter_user_id: int | None = None
    reporter_user_name: str | None = None
    reporter_type: str
    report_type: str
    reported_text: str
    observed_at: datetime | None = None
    received_at: datetime
    location_latitude: float | None = None
    location_longitude: float | None = None
    location_accuracy_meters: float | None = None
    verification_status: str
    parent_report_id: int | None = None
    idempotency_key: str | None = None
    audio_storage_url: str | None = None
    transcription_status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EmergencyStatusUpdateIn(BaseModel):
    status: str
    reason: str | None = None


class ClinicalHandoverGenerateIn(BaseModel):
    notes: str | None = None


class ClinicalHandoverApproveIn(BaseModel):
    approval_notes: str | None = None


class ClinicalHandoverRejectIn(BaseModel):
    rejection_reason: str = Field(..., min_length=2)


class ClinicalHandoverOut(BaseModel):
    id: int
    emergency_case_id: int
    version: int
    status: str
    handover_data: dict
    created_at: datetime
    approved_by_user_id: int | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    approval_notes: str | None = None
    rejection_reason: str | None = None
    is_current_approved: bool
    acknowledgements_count: int = 0
    model_config = ConfigDict(from_attributes=True)


class EmergencyArrivalIn(BaseModel):
    remarks: str | None = None


class HandoverAcknowledgeIn(BaseModel):
    handover_id: int
    operational_remarks: str | None = None


class HandoverAcknowledgementOut(BaseModel):
    id: int
    emergency_case_id: int
    hospital_id: int
    hospital_name: str | None = None
    handover_id: int
    handover_version: int | None = None
    acknowledged_by_user_id: int
    acknowledged_by_name: str | None = None
    acknowledged_at: datetime
    status: str
    operational_remarks: str | None = None
    model_config = ConfigDict(from_attributes=True)
