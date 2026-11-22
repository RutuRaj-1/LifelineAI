"""Initial schema baseline

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-11-22 12:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Hospitals
    op.create_table(
        "hospitals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
    )

    # 2. Users (patients FK created later to avoid circular dependency in table creation)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=30), nullable=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=True),
        sa.Column("linked_patient_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # 3. Patients
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("dob", sa.String(length=10), nullable=True),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("blood_group", sa.String(length=5), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("emergency_contacts", sa.JSON(), nullable=False),
        sa.Column("known_conditions", sa.Text(), nullable=True),
        sa.Column("known_allergies", sa.Text(), nullable=True),
        sa.Column("current_medications", sa.Text(), nullable=True),
        sa.Column("consent_ai_summary", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("family_code", sa.String(length=10), unique=True, nullable=False),
    )

    # Add foreign key constraint for users.linked_patient_id -> patients.id
    with op.batch_alter_table("users") as batch_op:
        batch_op.create_foreign_key("fk_users_patient", "patients", ["linked_patient_id"], ["id"])

    # 4. Doctors
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("specialty", sa.String(length=80), nullable=False),
        sa.Column("qualification", sa.String(length=120), nullable=True),
        sa.Column("is_available", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index("ix_doctors_hospital", "doctors", ["hospital_id"])
    op.create_index("ix_doctors_specialty", "doctors", ["specialty"])

    # 5. Medical Reports
    op.create_table(
        "medical_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("report_type", sa.String(length=40), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("storage_url", sa.String(length=500), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("ocr_status", sa.String(length=30), server_default="ok", nullable=False),
        sa.Column("report_date", sa.String(length=10), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_reports_patient", "medical_reports", ["patient_id"])

    # 6. Hospital Resources
    op.create_table(
        "hospital_resources",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=False),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.UniqueConstraint("hospital_id", "resource_type", name="uq_hospital_resource_type"),
    )
    op.create_index("ix_hospital_resources_hospital_id", "hospital_resources", ["hospital_id"])

    # 7. Emergency Cases
    op.create_table(
        "emergency_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id"), nullable=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id"), nullable=True),
        sa.Column("status", sa.String(length=30), server_default="CREATED", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="3", nullable=False),
        sa.Column("emergency_type", sa.String(length=20), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("current_lat", sa.Float(), nullable=True),
        sa.Column("current_lng", sa.Float(), nullable=True),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("initial_eta_minutes", sa.Integer(), nullable=True),
        sa.Column("specialty", sa.String(length=80), nullable=True),
        sa.Column("ai_summary", sa.JSON(), nullable=True),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("reserved_resources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cases_patient", "emergency_cases", ["patient_id"])
    op.create_index("ix_cases_hospital", "emergency_cases", ["hospital_id"])
    op.create_index("ix_cases_status", "emergency_cases", ["status"])

    # 8. Notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id"), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(length=20), server_default="dashboard", nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"])

    # 9. Activity Logs
    op.create_table(
        "activity_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id"), nullable=False),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=60), server_default="system", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_logs_case", "activity_logs", ["case_id"])


def downgrade() -> None:
    # Drop tables in reverse order of foreign key dependency
    op.drop_table("activity_logs")
    op.drop_table("notifications")
    op.drop_table("emergency_cases")
    op.drop_table("hospital_resources")
    op.drop_table("medical_reports")
    op.drop_table("doctors")

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_constraint("fk_users_patient", type_="foreignkey")

    op.drop_table("patients")
    op.drop_table("users")
    op.drop_table("hospitals")
