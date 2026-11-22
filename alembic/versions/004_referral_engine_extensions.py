"""Referral engine extensions: idempotency_key, requested_resource_type, priority, notes

Revision ID: 004_referral_engine_extensions
Revises: 003_hospital_registry_lifecycle
Create Date: 2026-11-22 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_referral_engine_extensions"
down_revision = "003_hospital_registry_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("referral_requests") as batch_op:
        batch_op.add_column(sa.Column("requested_resource_type", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("priority", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))
        batch_op.create_index("ix_referral_requests_idempotency_key", ["idempotency_key"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("referral_requests") as batch_op:
        batch_op.drop_index("ix_referral_requests_idempotency_key")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("notes")
        batch_op.drop_column("priority")
        batch_op.drop_column("requested_resource_type")
