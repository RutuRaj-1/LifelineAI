"""Domain model evolution: Patient Intelligence, Hospital Readiness and Referral Coordination

Revision ID: 002_domain_model_evolution
Revises: 001_initial_schema
Create Date: 2026-11-22 13:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_domain_model_evolution"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Hospital Departments
    op.create_table(
        "hospital_departments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_name", sa.String(length=120), nullable=False),
        sa.Column("department_code", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("operational_status", sa.String(length=30), server_default="ACTIVE", nullable=False),
        sa.Column("contact_information", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "department_code", name="uq_hospital_dept_code"),
    )
    op.create_index("ix_hospital_departments_hospital_id", "hospital_departments", ["hospital_id"])

    # 2. Hospital Capabilities
    op.create_table(
        "hospital_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("hospital_departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("capability_code", sa.String(length=60), nullable=False),
        sa.Column("capability_name", sa.String(length=120), nullable=False),
        sa.Column("capability_category", sa.String(length=60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("availability_mode", sa.String(length=30), server_default="24_7", nullable=False),
        sa.Column("verification_status", sa.String(length=30), server_default="UNVERIFIED", nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("hospital_id", "capability_code", name="uq_hospital_capability"),
    )
    op.create_index("ix_hospital_capabilities_hospital_id", "hospital_capabilities", ["hospital_id"])
    op.create_index("ix_hospital_capabilities_department_id", "hospital_capabilities", ["department_id"])
    op.create_index("ix_hospital_capabilities_capability_code", "hospital_capabilities", ["capability_code"])
    op.create_index("ix_hospital_capabilities_capability_category", "hospital_capabilities", ["capability_category"])

    # 3. Extend Hospital Resources
    with op.batch_alter_table("hospital_resources") as batch_op:
        batch_op.add_column(sa.Column("department_id", sa.Integer(), sa.ForeignKey("hospital_departments.id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("operational_status", sa.String(length=30), server_default="FUNCTIONAL", nullable=False))
        batch_op.add_column(sa.Column("staffed_capacity", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("occupied_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("maintenance_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
        batch_op.add_column(sa.Column("status_source", sa.String(length=40), server_default="MANUAL", nullable=False))
        batch_op.add_column(sa.Column("freshness_window_minutes", sa.Integer(), server_default="60", nullable=False))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch_op.create_index("ix_hospital_resources_department_id", ["department_id"])
        batch_op.create_check_constraint("ck_hospital_resource_total_non_negative", "total >= 0")
        batch_op.create_check_constraint("ck_hospital_resource_available_non_negative", "available >= 0")

    # 4. Resource Status History
    op.create_table(
        "resource_status_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hospital_resource_id", sa.Integer(), sa.ForeignKey("hospital_resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=True),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("previous_available_count", sa.Integer(), nullable=True),
        sa.Column("new_available_count", sa.Integer(), nullable=False),
        sa.Column("verification_source", sa.String(length=40), server_default="MANUAL", nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_resource_status_history_resource_id", "resource_status_history", ["hospital_resource_id"])
    op.create_index("ix_resource_status_history_created_at", "resource_status_history", ["created_at"])

    # 5. Specialist Availability
    op.create_table(
        "specialist_availabilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("hospital_departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("availability_status", sa.String(length=30), server_default="AVAILABLE", nullable=False),
        sa.Column("shift_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shift_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("on_call", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_specialist_availabilities_doctor_id", "specialist_availabilities", ["doctor_id"])
    op.create_index("ix_specialist_availabilities_hospital_id", "specialist_availabilities", ["hospital_id"])
    op.create_index("ix_specialist_availabilities_department_id", "specialist_availabilities", ["department_id"])
    op.create_index("ix_specialist_avail_lookup", "specialist_availabilities", ["hospital_id", "doctor_id", "availability_status"])

    # 6. Patient Clinical Facts
    op.create_table(
        "patient_clinical_facts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fact_type", sa.String(length=50), nullable=False),
        sa.Column("fact_code", sa.String(length=80), nullable=True),
        sa.Column("fact_value", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=True),
        sa.Column("clinical_status", sa.String(length=30), server_default="ACTIVE", nullable=False),
        sa.Column("effective_from", sa.String(length=20), nullable=True),
        sa.Column("effective_to", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_patient_clinical_facts_patient_id", "patient_clinical_facts", ["patient_id"])
    op.create_index("ix_patient_clinical_facts_fact_type", "patient_clinical_facts", ["fact_type"])

    # 7. Clinical Provenance
    op.create_table(
        "clinical_provenance",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("clinical_fact_id", sa.Integer(), sa.ForeignKey("patient_clinical_facts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_report_id", sa.Integer(), sa.ForeignKey("medical_reports.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("verification_status", sa.String(length=30), server_default="UNVERIFIED", nullable=False),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_clinical_provenance_clinical_fact_id", "clinical_provenance", ["clinical_fact_id"])
    op.create_index("ix_clinical_provenance_source_report_id", "clinical_provenance", ["source_report_id"])

    # 8. Extend Emergency Cases
    with op.batch_alter_table("emergency_cases") as batch_op:
        batch_op.add_column(sa.Column("origin_type", sa.String(length=40), server_default="PATIENT_SOS", nullable=False))
        batch_op.add_column(sa.Column("referral_round", sa.Integer(), server_default="1", nullable=False))
        batch_op.add_column(sa.Column("case_closed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("handover_status", sa.String(length=30), server_default="PENDING", nullable=False))
        batch_op.add_column(sa.Column("handover_signed_by", sa.String(length=120), nullable=True))

    # 9. Referral Requests
    op.create_table(
        "referral_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("request_reference", sa.String(length=60), nullable=False),
        sa.Column("request_round", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="SENT", nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("response_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decline_reason_code", sa.String(length=60), nullable=True),
        sa.Column("clarification_notes", sa.Text(), nullable=True),
        sa.Column("is_active_acceptance", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("emergency_case_id", "hospital_id", "request_round", name="uq_case_hosp_round"),
    )
    op.create_index("ix_referral_requests_emergency_case_id", "referral_requests", ["emergency_case_id"])
    op.create_index("ix_referral_requests_hospital_id", "referral_requests", ["hospital_id"])
    op.create_index("ix_referral_requests_request_reference", "referral_requests", ["request_reference"], unique=True)
    op.create_index("ix_referral_requests_status", "referral_requests", ["status"])

    # Conditional unique index: Only ONE accepted referral per emergency case
    op.create_index(
        "uq_case_single_active_accepted",
        "referral_requests",
        ["emergency_case_id"],
        unique=True,
        sqlite_where=sa.text("status = 'ACCEPTED'"),
        postgresql_where=sa.text("status = 'ACCEPTED'"),
    )

    # 10. Referral Responses
    op.create_table(
        "referral_responses",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("referral_request_id", sa.Integer(), sa.ForeignKey("referral_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("responding_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("response_type", sa.String(length=30), nullable=False),
        sa.Column("response_notes", sa.Text(), nullable=True),
        sa.Column("reason_code", sa.String(length=60), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_referral_responses_referral_request_id", "referral_responses", ["referral_request_id"])
    op.create_index("ix_referral_responses_responded_at", "referral_responses", ["responded_at"])

    # 11. Resource Reservations
    op.create_table(
        "resource_reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("referral_request_id", sa.Integer(), sa.ForeignKey("referral_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hospital_resource_id", sa.Integer(), sa.ForeignKey("hospital_resources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("reservation_status", sa.String(length=30), server_default="HELD", nullable=False),
        sa.Column("held_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(length=120), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_reservation_positive_quantity"),
    )
    op.create_index("ix_resource_reservations_referral_request_id", "resource_reservations", ["referral_request_id"])
    op.create_index("ix_resource_reservations_hospital_resource_id", "resource_reservations", ["hospital_resource_id"])
    op.create_index("ix_resource_reservations_idempotency_key", "resource_reservations", ["idempotency_key"], unique=True)

    # 12. Emergency Incident Reports
    op.create_table(
        "emergency_incident_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reporter_type", sa.String(length=30), server_default="PATIENT", nullable=False),
        sa.Column("report_type", sa.String(length=30), server_default="TEXT", nullable=False),
        sa.Column("reported_text", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("location_latitude", sa.Float(), nullable=True),
        sa.Column("location_longitude", sa.Float(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), server_default="UNVERIFIED", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_emergency_incident_reports_emergency_case_id", "emergency_incident_reports", ["emergency_case_id"])


def downgrade() -> None:
    op.drop_table("emergency_incident_reports")
    op.drop_table("resource_reservations")
    op.drop_table("referral_responses")
    op.drop_index("uq_case_single_active_accepted", table_name="referral_requests")
    op.drop_table("referral_requests")

    with op.batch_alter_table("emergency_cases") as batch_op:
        batch_op.drop_column("handover_signed_by")
        batch_op.drop_column("handover_status")
        batch_op.drop_column("case_closed_at")
        batch_op.drop_column("referral_round")
        batch_op.drop_column("origin_type")

    op.drop_table("clinical_provenance")
    op.drop_table("patient_clinical_facts")
    op.drop_table("specialist_availabilities")
    op.drop_table("resource_status_history")

    with op.batch_alter_table("hospital_resources") as batch_op:
        batch_op.drop_constraint("ck_hospital_resource_available_non_negative", type_="check")
        batch_op.drop_constraint("ck_hospital_resource_total_non_negative", type_="check")
        batch_op.drop_index("ix_hospital_resources_department_id")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("freshness_window_minutes")
        batch_op.drop_column("status_source")
        batch_op.drop_column("verified_by_user_id")
        batch_op.drop_column("last_verified_at")
        batch_op.drop_column("maintenance_count")
        batch_op.drop_column("occupied_count")
        batch_op.drop_column("staffed_capacity")
        batch_op.drop_column("operational_status")
        batch_op.drop_column("department_id")

    op.drop_table("hospital_capabilities")
    op.drop_table("hospital_departments")
