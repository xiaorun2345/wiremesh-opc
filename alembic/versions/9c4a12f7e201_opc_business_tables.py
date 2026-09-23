"""add OPC business tables

Revision ID: 9c4a12f7e201
Revises: 253b48e23ce5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c4a12f7e201"
down_revision: Union[str, Sequence[str], None] = "253b48e23ce5"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    table_args = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
    op.create_table(
        "opc_customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("region", sa.String(120), nullable=False, server_default=""),
        sa.Column("language", sa.String(16), nullable=False, server_default="zh-CN"), sa.Column("level", sa.String(8), nullable=False, server_default="B"),
        sa.Column("source", sa.String(64), nullable=False, server_default="manual"), sa.Column("contact_name", sa.String(80), nullable=False, server_default=""),
        sa.Column("contact_channel", sa.String(160), nullable=False, server_default=""), sa.Column("notes", sa.Text(), nullable=False),
        *timestamps(), **table_args,
    )
    op.create_index("ix_opc_customers_owner_id", "opc_customers", ["owner_id"])
    op.create_table(
        "opc_factories",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("products_json", sa.Text(), nullable=False), sa.Column("surfaces_json", sa.Text(), nullable=False),
        sa.Column("certifications_json", sa.Text(), nullable=False), sa.Column("lead_days", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("on_time_rate", sa.Float(), nullable=False, server_default="0"), sa.Column("quality_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"), sa.Column("notes", sa.Text(), nullable=False), *timestamps(), **table_args,
    )
    op.create_index("ix_opc_factories_owner_id", "opc_factories", ["owner_id"])
    op.create_table(
        "opc_inquiries",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("opc_customers.id"), nullable=True), sa.Column("source", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("product_type", sa.String(64), nullable=False, server_default=""),
        sa.Column("specs_json", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"), *timestamps(), **table_args,
    )
    op.create_index("ix_opc_inquiries_owner_id", "opc_inquiries", ["owner_id"])
    op.create_index("ix_opc_inquiries_status", "opc_inquiries", ["status"])
    op.create_table(
        "opc_quotes",
        sa.Column("id", sa.String(40), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inquiry_id", sa.String(36), sa.ForeignKey("opc_inquiries.id"), nullable=True), sa.Column("spec_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False), sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("approval_note", sa.Text(), nullable=False), sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        *timestamps(), **table_args,
    )
    op.create_index("ix_opc_quotes_owner_id", "opc_quotes", ["owner_id"])
    op.create_index("ix_opc_quotes_status", "opc_quotes", ["status"])
    op.create_table(
        "opc_orders",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("quote_id", sa.String(40), sa.ForeignKey("opc_quotes.id"), nullable=False), sa.Column("customer_id", sa.String(36), sa.ForeignKey("opc_customers.id"), nullable=True),
        sa.Column("factory_id", sa.String(36), sa.ForeignKey("opc_factories.id"), nullable=True), sa.Column("status", sa.String(32), nullable=False, server_default="CONFIRMED"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"), sa.Column("currency", sa.String(8), nullable=False, server_default="CNY"),
        sa.Column("due_date", sa.DateTime(), nullable=True), sa.Column("quality_status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("logistics_json", sa.Text(), nullable=False), *timestamps(), **table_args,
    )
    op.create_index("ix_opc_orders_owner_id", "opc_orders", ["owner_id"])
    op.create_index("ix_opc_orders_status", "opc_orders", ["status"])
    op.create_table(
        "opc_knowledge_documents",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(240), nullable=False), sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("source_uri", sa.String(512), nullable=False, server_default=""), sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        *timestamps(), **table_args,
    )
    op.create_index("ix_opc_knowledge_owner_id", "opc_knowledge_documents", ["owner_id"])
    op.create_index("ix_opc_knowledge_category", "opc_knowledge_documents", ["category"])


def downgrade() -> None:
    for table in ("opc_knowledge_documents", "opc_orders", "opc_quotes", "opc_inquiries", "opc_factories", "opc_customers"):
        op.drop_table(table)
