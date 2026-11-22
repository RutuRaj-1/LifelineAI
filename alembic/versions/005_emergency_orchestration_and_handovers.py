"""Emergency orchestration and clinical handovers: versioning, acknowledgements, incident intake

Revision ID: 005_emergency_orchestration_and_handovers
Revises: 004_referral_engine_extensions
Create Date: 2026-11-22 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "005_emergency_orchestration_and_handovers"
down_revision = "004_referral_engine_extensions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create clinical_handovers table
    op.create_table(
        "clinical_handovers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("handover_data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_current_approved", sa.Boolean(), nullable=False, server_default="0"),
        sa.UniqueConstraint("emergency_case_id", "version", name="uq_case_handover_version"),
    )
    op.create_index("ix_clinical_handovers_status", "clinical_handovers", ["status"])

    # 2. Create handover_acknowledgements table
    op.create_table(
        "handover_acknowledgements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("emergency_case_id", sa.Integer(), sa.ForeignKey("emergency_cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("hospital_id", sa.Integer(), sa.ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("handover_id", sa.Integer(), sa.ForeignKey("clinical_handovers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("acknowledged_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ACKNOWLEDGED"),
        sa.Column("operational_remarks", sa.Text(), nullable=True),
    )

    # 3. Add columns to emergency_cases
    with op.batch_alter_table("emergency_cases") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("location_source", sa.String(length=40), nullable=True, server_default="DEVICE_GPS"))
        batch_op.add_column(sa.Column("location_accuracy_meters", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("current_handover_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_emergency_cases_idempotency_key", ["idempotency_key"], unique=True)
        batch_op.create_index("ix_emergency_cases_current_handover_id", ["current_handover_id"])

    # 4. Add columns to emergency_incident_reports
    with op.batch_alter_table("emergency_incident_reports") as batch_op:
        batch_op.add_column(sa.Column("parent_report_id", sa.Integer(), sa.ForeignKey("emergency_incident_reports.id", ondelete="SET NULL"), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("reporter_role", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("audio_storage_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("transcription_status", sa.String(length=30), nullable=True, server_default="NONE"))
        batch_op.add_column(sa.Column("location_accuracy_meters", sa.Float(), nullable=True))
        batch_op.create_index("ix_emergency_incident_reports_idempotency_key", ["idempotency_key"], unique=True)
        batch_op.create_index("ix_emergency_incident_reports_parent_report_id", ["parent_report_id"])


def downgrade() -> None:
    with op.batch_alter_table("emergency_incident_reports") as batch_op:
        batch_op.drop_index("ix_emergency_incident_reports_parent_report_id")
        batch_op.drop_index("ix_emergency_incident_reports_idempotency_key")
        batch_op.drop_column("location_accuracy_meters")
        batch_op.drop_column("transcription_status")
        batch_op.drop_column("audio_storage_url")
        batch_op.drop_column("reporter_role")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("parent_report_id")

    with op.batch_alter_table("emergency_cases") as batch_op:
        batch_op.drop_index("ix_emergency_cases_current_handover_id")
        batch_op.drop_index("ix_emergency_cases_idempotency_key")
        batch_op.drop_column("current_handover_id")
        batch_op.drop_column("location_accuracy_meters")
        batch_op.drop_column("location_source")
        batch_op.drop_column("idempotency_key")

    op.drop_table("handover_acknowledgements")
    op.drop_index("ix_clinical_handovers_status", table_name="clinical_handovers")
    op.drop_table("clinical_handovers")
