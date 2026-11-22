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
    "INITIATED",
    "PATIENT_IDENTIFIED",
    "INTAKE_IN_PROGRESS",
    "SUMMARY_GENERATED",
    "COORDINATION_ACTIVE",
    "DOCTOR_ASSIGNED",
    "ROOM_RESERVED",
    "REFERRAL_IN_PROGRESS",
    "HOSPITAL_ACCEPTED",
    "IN_TRANSIT",
    "PATIENT_ARRIVED",
    "ARRIVED",
    "HANDOVER_COMPLETED",
    "COMPLETED",
    "CLOSED",
    "CANCELLED",
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

    # Prompt 08 Additive Extensions: Idempotency, Location Context & Handover Link
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    location_source: Mapped[str] = mapped_column(String(40), default="DEVICE_GPS")  # DEVICE_GPS | MANUAL_PIN | SIMULATED | COORDINATOR_REPORTED
    location_accuracy_meters: Mapped[float | None] = mapped_column(Float)
    current_handover_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_handovers.id", ondelete="SET NULL"), index=True)

    patient: Mapped[Patient] = relationship()
    hospital: Mapped[Hospital | None] = relationship()
    doctor: Mapped[Doctor | None] = relationship()

    # Referral, Incident Report & Clinical Handover Relationships
    referral_requests: Mapped[list["ReferralRequest"]] = relationship(back_populates="emergency_case", cascade="all, delete-orphan")
    incident_reports: Mapped[list["EmergencyIncidentReport"]] = relationship(back_populates="emergency_case", cascade="all, delete-orphan")
    handovers: Mapped[list["ClinicalHandover"]] = relationship(
        back_populates="emergency_case",
        cascade="all, delete-orphan",
        foreign_keys="ClinicalHandover.emergency_case_id",
    )
    current_handover: Mapped["ClinicalHandover | None"] = relationship(
        foreign_keys=[current_handover_id],
        post_update=True,
    )

    # Prompt 10 Post-Emergency Continuity Relationships
    outcomes: Mapped[list["EmergencyOutcome"]] = relationship(
        back_populates="emergency_case", cascade="all, delete-orphan", foreign_keys="EmergencyOutcome.emergency_case_id"
    )
    discharge_summaries: Mapped[list["DischargeSummary"]] = relationship(
        back_populates="emergency_case", cascade="all, delete-orphan", foreign_keys="DischargeSummary.emergency_case_id"
    )
    medication_reconciliations: Mapped[list["MedicationReconciliation"]] = relationship(
        back_populates="emergency_case", cascade="all, delete-orphan", foreign_keys="MedicationReconciliation.emergency_case_id"
    )
    follow_up_plans: Mapped[list["FollowUpPlan"]] = relationship(
        back_populates="emergency_case", cascade="all, delete-orphan", foreign_keys="FollowUpPlan.emergency_case_id"
    )


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
    requested_resource_type: Mapped[str | None] = mapped_column(String(40))
    priority: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
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

    # Prompt 08 Extensions: Versioning/corrections, Idempotency, Audio & Provenance
    parent_report_id: Mapped[int | None] = mapped_column(ForeignKey("emergency_incident_reports.id", ondelete="SET NULL"), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    reporter_role: Mapped[str | None] = mapped_column(String(40))
    audio_storage_url: Mapped[str | None] = mapped_column(String(500))
    transcription_status: Mapped[str] = mapped_column(String(30), default="NONE")  # NONE | PENDING | TRANSCRIBED | MANUAL_ENTERED | UNAVAILABLE
    location_accuracy_meters: Mapped[float | None] = mapped_column(Float)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="incident_reports")
    reporter_user: Mapped["User | None"] = relationship(foreign_keys=[reporter_user_id])
    parent_report: Mapped["EmergencyIncidentReport | None"] = relationship(remote_side=[id])


class ClinicalHandover(Base):
    __tablename__ = "clinical_handovers"
    __table_args__ = (
        UniqueConstraint("emergency_case_id", "version", name="uq_case_handover_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_REVIEW", index=True)  # DRAFT | GENERATED | PENDING_REVIEW | APPROVED | SUPERSEDED | REJECTED
    handover_data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    is_current_approved: Mapped[bool] = mapped_column(Boolean, default=False)

    emergency_case: Mapped["EmergencyCase"] = relationship(
        back_populates="handovers",
        foreign_keys=[emergency_case_id],
    )
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    acknowledgements: Mapped[list["HandoverAcknowledgement"]] = relationship(back_populates="handover", cascade="all, delete-orphan")


class HandoverAcknowledgement(Base):
    __tablename__ = "handover_acknowledgements"

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    handover_id: Mapped[int] = mapped_column(ForeignKey("clinical_handovers.id", ondelete="CASCADE"), index=True)
    acknowledged_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    status: Mapped[str] = mapped_column(String(30), default="ACKNOWLEDGED")
    operational_remarks: Mapped[str | None] = mapped_column(Text)

    emergency_case: Mapped["EmergencyCase"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
    handover: Mapped["ClinicalHandover"] = relationship(back_populates="acknowledgements")
    acknowledged_by: Mapped["User"] = relationship(foreign_keys=[acknowledged_by_user_id])


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


# ==============================================================================
# Prompt 10: Post-Emergency Continuity, Outcomes, Discharges & Longitudinal Follow-Up
# ==============================================================================

class EmergencyOutcome(Base):
    __tablename__ = "emergency_outcomes"

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    disposition: Mapped[str] = mapped_column(String(40), index=True)  # DISCHARGED | ADMITTED | TRANSFERRED | OBSERVATION | DECEASED | LEFT_AGAINST_ADVICE | OTHER
    disposition_notes: Mapped[str | None] = mapped_column(Text)
    outcome_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED", index=True)  # UNVERIFIED | REVIEWED | CLINICIAN_VERIFIED | AMENDED | SUPERSEDED
    recorded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_outcome_id: Mapped[int | None] = mapped_column(ForeignKey("emergency_outcomes.id", ondelete="SET NULL"), index=True)
    amendment_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="outcomes")
    patient: Mapped["Patient"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
    recorded_by: Mapped["User | None"] = relationship(foreign_keys=[recorded_by_user_id])
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])
    parent_outcome: Mapped["EmergencyOutcome | None"] = relationship(remote_side=[id])


class DischargeSummary(Base):
    __tablename__ = "discharge_summaries"
    __table_args__ = (
        UniqueConstraint("emergency_case_id", "version", name="uq_case_discharge_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    source_report_id: Mapped[int | None] = mapped_column(ForeignKey("medical_reports.id", ondelete="SET NULL"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)  # DRAFT | PENDING_REVIEW | APPROVED | REJECTED | SUPERSEDED | AMENDED
    admission_date: Mapped[str | None] = mapped_column(String(30))
    discharge_date: Mapped[str | None] = mapped_column(String(30))
    primary_diagnosis: Mapped[str | None] = mapped_column(String(255))
    secondary_diagnoses: Mapped[list | None] = mapped_column(JSON, default=list)
    procedures_performed: Mapped[list | None] = mapped_column(JSON, default=list)
    clinical_course: Mapped[str | None] = mapped_column(Text)
    discharge_condition: Mapped[str | None] = mapped_column(String(80))  # STABLE | AMBULATORY | CRITICAL | TRANSFERRED | IMPROVED
    precautions: Mapped[list | None] = mapped_column(JSON, default=list)
    summary_data: Mapped[dict] = mapped_column(JSON)
    author_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approval_notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    amendment_reason: Mapped[str | None] = mapped_column(Text)
    parent_summary_id: Mapped[int | None] = mapped_column(ForeignKey("discharge_summaries.id", ondelete="SET NULL"), index=True)
    is_current_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="discharge_summaries")
    patient: Mapped["Patient"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
    source_report: Mapped["MedicalReport | None"] = relationship()
    author_user: Mapped["User | None"] = relationship(foreign_keys=[author_user_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    parent_summary: Mapped["DischargeSummary | None"] = relationship(remote_side=[id])


class MedicationReconciliation(Base):
    __tablename__ = "medication_reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    discharge_summary_id: Mapped[int | None] = mapped_column(ForeignKey("discharge_summaries.id", ondelete="SET NULL"), index=True)
    medication_name: Mapped[str] = mapped_column(String(160))
    dosage: Mapped[str | None] = mapped_column(String(80))
    route: Mapped[str | None] = mapped_column(String(40))  # ORAL | IV | IM | SUBCUTANEOUS | INHALATION | TOPICAL | OTHER
    frequency: Mapped[str | None] = mapped_column(String(80))  # ONCE_DAILY | TWICE_DAILY | THRICE_DAILY | AS_NEEDED | CONTINUOUS
    reconciliation_status: Mapped[str] = mapped_column(String(30))  # CONTINUE | START | STOP | CHANGE | NOT_RECONCILED
    source_type: Mapped[str] = mapped_column(String(40))  # PATIENT_REPORTED | HISTORICAL_RECORD | DISCHARGE_ORDER | CLINICIAN_ENTERED | OCR_EXTRACTED
    clinical_reason: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(String(30), default="UNVERIFIED")  # UNVERIFIED | REVIEWED | CLINICIAN_VERIFIED | REJECTED
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promoted_fact_id: Mapped[int | None] = mapped_column(ForeignKey("patient_clinical_facts.id", ondelete="SET NULL"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="medication_reconciliations")
    patient: Mapped["Patient"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
    discharge_summary: Mapped["DischargeSummary | None"] = relationship()
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])
    promoted_fact: Mapped["PatientClinicalFact | None"] = relationship()


class FollowUpPlan(Base):
    __tablename__ = "follow_up_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    emergency_case_id: Mapped[int] = mapped_column(ForeignKey("emergency_cases.id", ondelete="CASCADE"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="CASCADE"), index=True)
    discharge_summary_id: Mapped[int | None] = mapped_column(ForeignKey("discharge_summaries.id", ondelete="SET NULL"), index=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("hospital_departments.id", ondelete="SET NULL"), index=True)
    specialty: Mapped[str] = mapped_column(String(80))
    scheduled_date: Mapped[str | None] = mapped_column(String(40))
    instructions: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", index=True)  # PLANNED | SCHEDULED | COMPLETED | CANCELLED | MISSED | RESCHEDULED
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    emergency_case: Mapped["EmergencyCase"] = relationship(back_populates="follow_up_plans")
    patient: Mapped["Patient"] = relationship()
    hospital: Mapped["Hospital"] = relationship()
    department: Mapped["HospitalDepartment | None"] = relationship()
    discharge_summary: Mapped["DischargeSummary | None"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    verified_by: Mapped["User | None"] = relationship(foreign_keys=[verified_by_user_id])
