from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

STATUS_FLOW = [
    "CREATED",
    "PATIENT_IDENTIFIED",
    "SUMMARY_GENERATED",
    "DOCTOR_ASSIGNED",
    "ROOM_RESERVED",
    "PATIENT_ARRIVED",
    "COMPLETED",
]


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), index=True)  # patient | doctor | hospital | family
    phone: Mapped[str | None] = mapped_column(String(30))
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"))  # hospital staff
    linked_patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"))  # family members
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Hospital(Base):
    __tablename__ = "hospitals"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    address: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(80))
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    phone: Mapped[str | None] = mapped_column(String(30))
    capabilities: Mapped[list] = mapped_column(JSON, default=list)  # legacy JSON capabilities
    status: Mapped[str] = mapped_column(String(30), default="VERIFIED", index=True)  # DRAFT | SUBMITTED | UNDER_REVIEW | VERIFIED | REJECTED | SUSPENDED | INACTIVE
    hospital_type: Mapped[str] = mapped_column(String(50), default="GENERAL")  # GENERAL | TERTIARY_CARE | TRAUMA_CENTER | SPECIALTY
    contact_email: Mapped[str | None] = mapped_column(String(120))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    verification_source: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    resources: Mapped[list["HospitalResource"]] = relationship(back_populates="hospital")
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])

    # New Domain Relationships
    departments: Mapped[list["HospitalDepartment"]] = relationship(back_populates="hospital", cascade="all, delete-orphan")
    capabilities_rel: Mapped[list["HospitalCapability"]] = relationship(back_populates="hospital", cascade="all, delete-orphan")


class HospitalDepartment(Base):
    __tablename__ = "hospital_departments"
    __table_args__ = (UniqueConstraint("hospital_id", "department_code", name="uq_hospital_dept_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    department_name: Mapped[str] = mapped_column(String(120))
    department_code: Mapped[str] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)
    operational_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")  # ACTIVE | INACTIVE | LIMITED
    contact_information: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    hospital: Mapped["Hospital"] = relationship(back_populates="departments")
    capabilities: Mapped[list["HospitalCapability"]] = relationship(back_populates="department")
    resources: Mapped[list["HospitalResource"]] = relationship(back_populates="department")
    specialist_availabilities: Mapped[list["SpecialistAvailability"]] = relationship(back_populates="department")


class HospitalCapability(Base):
    __tablename__ = "hospital_capabilities"
    __table_args__ = (UniqueConstraint("hospital_id", "capability_code", name="uq_hospital_capability"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("hospital_departments.id", ondelete="SET NULL"), index=True)
    capability_code: Mapped[str] = mapped_column(String(60), index=True)
    capability_name: Mapped[str] = mapped_column(String(120))
    capability_category: Mapped[str] = mapped_column(String(60), index=True)  # DIAGNOSTIC | SURGICAL | CRITICAL_CARE | STABILIZATION
    description: Mapped[str | None] = mapped_column(Text)
    availability_mode: Mapped[str] = mapped_column(String(30), default="24_7")  # 24_7 | ON_CALL | BUSINESS_HOURS | CONDITIONAL
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")  # UNVERIFIED | REVIEWED | VERIFIED | SUSPENDED
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    verification_source: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    hospital: Mapped["Hospital"] = relationship(back_populates="capabilities_rel")
    department: Mapped["HospitalDepartment | None"] = relationship(back_populates="capabilities")
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])


class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    specialty: Mapped[str] = mapped_column(String(80), index=True)
    qualification: Mapped[str | None] = mapped_column(String(120))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship()


class SpecialistAvailability(Base):
    __tablename__ = "specialist_availabilities"
    __table_args__ = (
        Index("ix_specialist_avail_lookup", "hospital_id", "doctor_id", "availability_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("hospital_departments.id", ondelete="SET NULL"), index=True)
    availability_status: Mapped[str] = mapped_column(String(30), default="AVAILABLE")  # AVAILABLE | ON_CALL | BUSY | OFF_DUTY | UNAVAILABLE | UNKNOWN
    shift_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    shift_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    on_call: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    doctor: Mapped["Doctor"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
    department: Mapped["HospitalDepartment | None"] = relationship(back_populates="specialist_availabilities")
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])


class Patient(Base):
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    dob: Mapped[str | None] = mapped_column(String(10))
    gender: Mapped[str | None] = mapped_column(String(20))
    blood_group: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(String(255))
    emergency_contacts: Mapped[list] = mapped_column(JSON, default=list)  # [{name, phone, relation}]
    known_conditions: Mapped[str | None] = mapped_column(Text)  # self-declared, shown separately from AI brief
    known_allergies: Mapped[str | None] = mapped_column(Text)
    current_medications: Mapped[str | None] = mapped_column(Text)
    consent_ai_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    family_code: Mapped[str] = mapped_column(String(10), unique=True)
    user: Mapped[User] = relationship(foreign_keys=[user_id])

    # Structured Clinical Facts
    clinical_facts: Mapped[list["PatientClinicalFact"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class PatientClinicalFact(Base):
    __tablename__ = "patient_clinical_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    fact_type: Mapped[str] = mapped_column(String(50), index=True)  # CONDITION | ALLERGY | MEDICATION | SURGERY | DEVICE | RISK
    fact_code: Mapped[str | None] = mapped_column(String(80))
    fact_value: Mapped[str] = mapped_column(String(255))
    normalized_value: Mapped[str | None] = mapped_column(String(255))
    clinical_status: Mapped[str] = mapped_column(String(30), default="ACTIVE")  # ACTIVE | RESOLVED | INACTIVE | SUSPECTED
    effective_from: Mapped[str | None] = mapped_column(String(20))
    effective_to: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    patient: Mapped["Patient"] = relationship(back_populates="clinical_facts")
    provenance_records: Mapped[list["ClinicalProvenance"]] = relationship(back_populates="clinical_fact", cascade="all, delete-orphan")


class ClinicalProvenance(Base):
    __tablename__ = "clinical_provenance"

    id: Mapped[int] = mapped_column(primary_key=True)
    clinical_fact_id: Mapped[int] = mapped_column(ForeignKey("patient_clinical_facts.id", ondelete="CASCADE"), index=True)
    source_type: Mapped[str] = mapped_column(String(40))  # PATIENT_ENTERED | FAMILY_REPORTED | OCR_EXTRACTED | HOSPITAL_IMPORTED | DOCTOR_VERIFIED | OTHER | LEGACY_IMPORT
    source_report_id: Mapped[int | None] = mapped_column(ForeignKey("medical_reports.id", ondelete="SET NULL"), index=True)
    source_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source_reference: Mapped[str | None] = mapped_column(String(255))
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")  # UNVERIFIED | REVIEWED | VERIFIED | REJECTED | SUPERSEDED
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    clinical_fact: Mapped["PatientClinicalFact"] = relationship(back_populates="provenance_records")
    source_report: Mapped["MedicalReport | None"] = relationship()
    source_user: Mapped["User | None"] = relationship(foreign_keys=[source_user_id])
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])


class MedicalReport(Base):
    __tablename__ = "medical_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    report_type: Mapped[str] = mapped_column(String(40))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    storage_url: Mapped[str | None] = mapped_column(String(500))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    ocr_status: Mapped[str] = mapped_column(String(30), default="ok")
    report_date: Mapped[str | None] = mapped_column(String(10))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class HospitalResource(Base):
    __tablename__ = "hospital_resources"
    __table_args__ = (
        UniqueConstraint("hospital_id", "resource_type", name="uq_hospital_resource_type"),
        CheckConstraint("total >= 0", name="ck_hospital_resource_total_non_negative"),
        CheckConstraint("available >= 0", name="ck_hospital_resource_available_non_negative"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(30))
    total: Mapped[int] = mapped_column(Integer)
    available: Mapped[int] = mapped_column(Integer)

    # Operational status and verification additions
    department_id: Mapped[int | None] = mapped_column(ForeignKey("hospital_departments.id", ondelete="SET NULL"), index=True)
    operational_status: Mapped[str] = mapped_column(String(30), default="FUNCTIONAL")  # FUNCTIONAL | LIMITED | MAINTENANCE | NON_OPERATIONAL | UNSTAFFED | UNKNOWN
    staffed_capacity: Mapped[int | None] = mapped_column(Integer)
    occupied_count: Mapped[int] = mapped_column(Integer, default=0)
    maintenance_count: Mapped[int] = mapped_column(Integer, default=0)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status_source: Mapped[str] = mapped_column(String(40), default="MANUAL")  # MANUAL | INTEGRATION | SENSOR | AUDIT
    freshness_window_minutes: Mapped[int] = mapped_column(Integer, default=60)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    hospital: Mapped[Hospital] = relationship(back_populates="resources")
    department: Mapped["HospitalDepartment | None"] = relationship(back_populates="resources")
    status_history: Mapped[list["ResourceStatusHistory"]] = relationship(back_populates="resource", cascade="all, delete-orphan")
    reservations: Mapped[list["ResourceReservation"]] = relationship(back_populates="hospital_resource")
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])


class ResourceStatusHistory(Base):
    __tablename__ = "resource_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_resource_id: Mapped[int] = mapped_column(ForeignKey("hospital_resources.id", ondelete="CASCADE"), index=True)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30))
    previous_available_count: Mapped[int | None] = mapped_column(Integer)
    new_available_count: Mapped[int] = mapped_column(Integer)
    verification_source: Mapped[str] = mapped_column(String(40), default="MANUAL")
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)

    resource: Mapped["HospitalResource"] = relationship(back_populates="status_history")
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])


class EmergencyCase(Base):
    __tablename__ = "emergency_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    hospital_id: Mapped[int | None] = mapped_column(ForeignKey("hospitals.id"), index=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="CREATED", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)
    emergency_type: Mapped[str] = mapped_column(String(20))
    symptoms: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    current_lat: Mapped[float | None] = mapped_column(Float)
    current_lng: Mapped[float | None] = mapped_column(Float)
    eta_minutes: Mapped[int | None] = mapped_column(Integer)
    initial_eta_minutes: Mapped[int | None] = mapped_column(Integer)
    specialty: Mapped[str | None] = mapped_column(String(80))
    ai_summary: Mapped[dict | None] = mapped_column(JSON)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    reserved_resources: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Prompt 03 Additive Extensions
    origin_type: Mapped[str] = mapped_column(String(40), default="PATIENT_SOS")  # PATIENT_SOS | FAMILY_ASSISTED | BYSTANDER_REPORTED | CLINIC_REFERRAL | AUTHORIZED_EMERGENCY_REFERRAL
    referral_round: Mapped[int] = mapped_column(Integer, default=1)
    case_closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    handover_status: Mapped[str] = mapped_column(String(30), default="PENDING")  # PENDING | IN_TRANSIT | ARRIVED | HANDOVER_COMPLETE | REFERRED_OUT
    handover_signed_by: Mapped[str | None] = mapped_column(String(120))

    patient: Mapped[Patient] = relationship()
    hospital: Mapped[Hospital | None] = relationship()
    doctor: Mapped[Doctor | None] = relationship()

    # Referral & Incident Report Relationships
    referral_requests: Mapped[list["ReferralRequest"]] = relationship(back_populates="emergency_case", cascade="all, delete-orphan")
    incident_reports: Mapped[list["EmergencyIncidentReport"]] = relationship(back_populates="emergency_case", cascade="all, delete-orphan")


class ReferralRequest(Base):
    __tablename__ = "referral_requests"
    __table_args__ = (
        UniqueConstraint("emergency_case_id", "hospital_id", "request_round", name="uq_case_hosp_round"),
        # Enforce that only one referral per emergency case can have status = 'ACCEPTED'
        Index(
            "uq_case_single_active_accepted",
            "emergency_case_id",
            unique=True,
            sqlite_where=text("status = 'ACCEPTED'"),
            postgresql_where=text("status = 'ACCEPTED'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    request_reference: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    request_round: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="SENT", index=True)  # DRAFT | SENT | REVIEWING | ACCEPTED | DECLINED | CLARIFICATION_REQUIRED | EXPIRED | CANCELLED
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    response_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decline_reason_code: Mapped[str | None] = mapped_column(String(60))  # NO_BEDS | NO_SPECIALIST | DIVERT | RESOURCE_UNAVAILABLE | OTHER
    clarification_notes: Mapped[str | None] = mapped_column(Text)
    is_active_acceptance: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="referral_requests")
    hospital: Mapped["Hospital"] = relationship()
    requested_by: Mapped["User | None"] = relationship(foreign_keys=[requested_by_user_id])
    accepted_by: Mapped["User | None"] = relationship(foreign_keys=[accepted_by_user_id])
    responses: Mapped[list["ReferralResponse"]] = relationship(back_populates="referral_request", cascade="all, delete-orphan")
    reservations: Mapped[list["ResourceReservation"]] = relationship(back_populates="referral_request")


class ReferralResponse(Base):
    __tablename__ = "referral_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    referral_request_id: Mapped[int] = mapped_column(ForeignKey("referral_requests.id", ondelete="CASCADE"), index=True)
    responding_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    response_type: Mapped[str] = mapped_column(String(30))  # ACCEPT | DECLINE | REQUEST_CLARIFICATION | CLARIFICATION_PROVIDED | WITHDRAW
    response_notes: Mapped[str | None] = mapped_column(Text)
    reason_code: Mapped[str | None] = mapped_column(String(60))
    responded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    referral_request: Mapped["ReferralRequest"] = relationship(back_populates="responses")
    responding_user: Mapped["User | None"] = relationship(foreign_keys=[responding_user_id])


class ResourceReservation(Base):
    __tablename__ = "resource_reservations"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_reservation_positive_quantity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    referral_request_id: Mapped[int] = mapped_column(ForeignKey("referral_requests.id", ondelete="CASCADE"), index=True)
    hospital_resource_id: Mapped[int] = mapped_column(ForeignKey("hospital_resources.id", ondelete="CASCADE"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    reservation_status: Mapped[str] = mapped_column(String(30), default="HELD")  # HELD | CONFIRMED | RELEASED | EXPIRED | CONSUMED
    held_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_reason: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    referral_request: Mapped["ReferralRequest"] = relationship(back_populates="reservations")
    hospital_resource: Mapped["HospitalResource"] = relationship(back_populates="reservations")
    confirmed_by: Mapped["User | None"] = relationship(foreign_keys=[confirmed_by_user_id])


class EmergencyIncidentReport(Base):
    __tablename__ = "emergency_incident_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    reporter_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reporter_type: Mapped[str] = mapped_column(String(30), default="PATIENT")  # PATIENT | FAMILY | BYSTANDER | AMBULANCE | DISPATCHER | HOSPITAL_STAFF | OTHER
    report_type: Mapped[str] = mapped_column(String(30), default="TEXT")  # TEXT | VOICE_TRANSCRIPTION | VITALS | OBSERVATION | OTHER
    reported_text: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    location_latitude: Mapped[float | None] = mapped_column(Float)
    location_longitude: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")  # UNVERIFIED | REVIEWED | CLINICIAN_CONFIRMED | REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="incident_reports")
    reporter_user: Mapped["User | None"] = relationship(foreign_keys=[reporter_user_id])


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("emergency_cases.id"))
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(20), default="dashboard")  # dashboard | push | sms
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id"), index=True)
    event: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(60), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
