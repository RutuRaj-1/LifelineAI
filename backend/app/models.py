from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

STATUS_FLOW = ["CREATED", "PATIENT_IDENTIFIED", "SUMMARY_GENERATED", "DOCTOR_ASSIGNED",
               "ROOM_RESERVED", "PATIENT_ARRIVED", "COMPLETED"]


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
    capabilities: Mapped[list] = mapped_column(JSON, default=list)  # e.g. ["stroke","cardiac","trauma"]
    resources: Mapped[list["HospitalResource"]] = relationship(back_populates="hospital")


class Doctor(Base):
    __tablename__ = "doctors"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    specialty: Mapped[str] = mapped_column(String(80), index=True)
    qualification: Mapped[str | None] = mapped_column(String(120))
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    user: Mapped[User] = relationship()


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
    __table_args__ = (UniqueConstraint("hospital_id", "resource_type"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(30))
    total: Mapped[int] = mapped_column(Integer)
    available: Mapped[int] = mapped_column(Integer)
    hospital: Mapped[Hospital] = relationship(back_populates="resources")


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
    patient: Mapped[Patient] = relationship()
    hospital: Mapped[Hospital | None] = relationship()
    doctor: Mapped[Doctor | None] = relationship()


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
