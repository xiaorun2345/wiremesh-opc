"""add translated lead fields and review state

Revision ID: d7e8f9012345
Revises: c6d7e8f90123
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e8f9012345"
down_revision = "c6d7e8f90123"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("opc_overseas_leads") as batch:
        batch.add_column(sa.Column("title_zh", sa.String(500), nullable=False, server_default=""))
        batch.add_column(sa.Column("summary_zh", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("translation_status", sa.String(32), nullable=False, server_default="PENDING"))
        batch.add_column(sa.Column("review_status", sa.String(32), nullable=False, server_default="NEEDS_REVIEW"))
        batch.add_column(sa.Column("review_note", sa.Text(), nullable=False, server_default=""))
        batch.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))
        batch.create_index("ix_opc_overseas_leads_review_status", ["review_status"])


def downgrade() -> None:
    with op.batch_alter_table("opc_overseas_leads") as batch:
        batch.drop_index("ix_opc_overseas_leads_review_status")
        batch.drop_column("reviewed_at")
        batch.drop_column("review_note")
        batch.drop_column("review_status")
        batch.drop_column("translation_status")
        batch.drop_column("summary_zh")
        batch.drop_column("title_zh")
