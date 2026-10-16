"""add overseas lead radar

Revision ID: c6d7e8f90123
Revises: b7e31f0d4a02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c6d7e8f90123"
down_revision: Union[str, Sequence[str], None] = "b7e31f0d4a02"
branch_labels = None
depends_on = None


def _options():
    return {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def upgrade() -> None:
    opt = _options()
    op.create_table(
        "opc_lead_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(32), nullable=False, server_default="NEVER"),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        **opt,
    )
    op.create_index("ix_opc_lead_sources_owner", "opc_lead_sources", ["owner_id"])
    op.create_table(
        "opc_overseas_leads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("opc_lead_sources.id"), nullable=True),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("dedupe_key", sa.String(280), nullable=False, unique=True),
        sa.Column("source_url", sa.String(1024), nullable=False, server_default=""),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("buyer", sa.String(240), nullable=False, server_default=""),
        sa.Column("country", sa.String(80), nullable=False, server_default=""),
        sa.Column("language", sa.String(16), nullable=False, server_default="en"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("deadline_at", sa.DateTime(), nullable=True),
        sa.Column("budget", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default=""),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("extracted_json", sa.Text(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("score_reasons_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("inquiry_id", sa.String(36), sa.ForeignKey("opc_inquiries.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        **opt,
    )
    op.create_index("ix_opc_overseas_owner", "opc_overseas_leads", ["owner_id"])
    op.create_index("ix_opc_overseas_status", "opc_overseas_leads", ["status"])
    op.create_index("ix_opc_overseas_score", "opc_overseas_leads", ["score"])
    op.create_table(
        "opc_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False, server_default=""),
        sa.Column("entity_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("priority", sa.String(16), nullable=False, server_default="NORMAL"),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("channel_status_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        **opt,
    )
    op.create_index("ix_opc_notifications_owner", "opc_notifications", ["owner_id", "read_at"])


def downgrade() -> None:
    op.drop_table("opc_notifications")
    op.drop_table("opc_overseas_leads")
    op.drop_table("opc_lead_sources")
