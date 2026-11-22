"""Hospital registry, department hierarchy and clinical capability lifecycle

Revision ID: 003_hospital_registry_lifecycle
Revises: 002_domain_model_evolution
Create Date: 2026-11-22 13:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003_hospital_registry_lifecycle"
down_revision: Union[str, None] = "002_domain_model_evolution"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend hospitals table with registry lifecycle and verification metadata
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=30), server_default="VERIFIED", nullable=False))
        batch_op.add_column(sa.Column("hospital_type", sa.String(length=50), server_default="GENERAL", nullable=False))
        batch_op.add_column(sa.Column("contact_email", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("verification_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("verified_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        batch_op.create_index("ix_hospitals_status", ["status"])

    # 2. Extend hospital_capabilities table with verification notes and verification source
    with op.batch_alter_table("hospital_capabilities") as batch_op:
        batch_op.add_column(sa.Column("verification_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("verification_source", sa.String(length=100), nullable=True))


def downgrade() -> None:
    # 1. Revert hospital_capabilities extensions
    with op.batch_alter_table("hospital_capabilities") as batch_op:
        batch_op.drop_column("verification_source")
        batch_op.drop_column("verification_notes")

    # 2. Revert hospitals extensions
    with op.batch_alter_table("hospitals") as batch_op:
        batch_op.drop_index("ix_hospitals_status")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("created_at")
        batch_op.drop_column("verified_at")
        batch_op.drop_column("verified_by_user_id")
        batch_op.drop_column("verification_notes")
        batch_op.drop_column("contact_email")
        batch_op.drop_column("hospital_type")
        batch_op.drop_column("status")
