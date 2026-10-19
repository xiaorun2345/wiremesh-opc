"""add encrypted model provider configs

Revision ID: e8f901234567
Revises: d7e8f9012345
"""
from alembic import op
import sqlalchemy as sa

revision = "e8f901234567"
down_revision = "d7e8f9012345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "opc_model_provider_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("purpose", sa.String(16), nullable=False, server_default="text"),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("base_url", sa.String(512), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_model_provider_owner_purpose", "opc_model_provider_configs", ["owner_id", "purpose"])


def downgrade() -> None:
    op.drop_index("ix_model_provider_owner_purpose", table_name="opc_model_provider_configs")
    op.drop_table("opc_model_provider_configs")
