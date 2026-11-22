"""Post-emergency continuity, clinical outcomes, discharge summaries, medication reconciliation & follow-ups

Revision ID: 006_post_emergency_continuity_and_outcomes
Revises: 005_emergency_orchestration_and_handovers
Create Date: 2026-11-22 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006_post_emergency_continuity_and_outcomes"
down_revision = "005_emergency_orchestration_and_handovers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create emergency_outcomes table
    op.create_table(
        "emergency_outcomes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("disposition", sa.String(length=40), nullable=False, index=True),
        sa.Column("disposition_notes", sa.Text(), nullable=True),
        sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="UNVERIFIED", index=True),
        sa.Column("recorded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("parent_outcome_id", sa.Integer(), sa.ForeignKey("emergency_outcomes.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("amendment_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. Create discharge_summaries table
    op.create_table(
        "discharge_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("source_report_id", sa.Integer(), sa.ForeignKey("medical_reports.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="DRAFT", index=True),
        sa.Column("admission_date", sa.String(length=30), nullable=True),
        sa.Column("discharge_date", sa.String(length=30), nullable=True),
        sa.Column("primary_diagnosis", sa.String(length=255), nullable=True),
        sa.Column("secondary_diagnoses", sa.JSON(), nullable=True),
        sa.Column("procedures_performed", sa.JSON(), nullable=True),
        sa.Column("clinical_course", sa.Text(), nullable=True),
        sa.Column("discharge_condition", sa.String(length=80), nullable=True),
        sa.Column("precautions", sa.JSON(), nullable=True),
        sa.Column("summary_data", sa.JSON(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("amendment_reason", sa.Text(), nullable=True),
        sa.Column("parent_summary_id", sa.Integer(), sa.ForeignKey("discharge_summaries.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("is_current_approved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("emergency_case_id", "version", name="uq_case_discharge_version"),
    )

    # 3. Create medication_reconciliations table
    op.create_table(
        "medication_reconciliations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("discharge_summary_id", sa.Integer(), sa.ForeignKey("discharge_summaries.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("medication_name", sa.String(length=160), nullable=False),
        sa.Column("dosage", sa.String(length=80), nullable=True),
        sa.Column("route", sa.String(length=40), nullable=True),
        sa.Column("frequency", sa.String(length=80), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=30), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("clinical_reason", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.String(length=30), nullable=False, server_default="UNVERIFIED"),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("promoted_fact_id", sa.Integer(), sa.ForeignKey("patient_clinical_facts.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. Create follow_up_plans table
    op.create_table(
        "follow_up_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("discharge_summary_id", sa.Integer(), sa.ForeignKey("discharge_summaries.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("hospital_departments.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("specialty", sa.String(length=80), nullable=False),
        sa.Column("scheduled_date", sa.String(length=40), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PLANNED", index=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("follow_up_plans")
    op.drop_table("medication_reconciliations")
    op.drop_table("discharge_summaries")
    op.drop_table("emergency_outcomes")
