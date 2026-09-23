"""add OPC automation tables

Revision ID: b7e31f0d4a02
Revises: 9c4a12f7e201
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e31f0d4a02"
down_revision: Union[str, Sequence[str], None] = "9c4a12f7e201"
branch_labels = None
depends_on = None


def upgrade() -> None:
    opts = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}
    op.add_column("opc_quotes", sa.Column("pdf_path", sa.String(512), nullable=True))
    op.add_column("opc_quotes", sa.Column("excel_path", sa.String(512), nullable=True))
    op.add_column("opc_orders", sa.Column("payment_status", sa.String(32), nullable=False, server_default="DEPOSIT_PENDING"))
    op.add_column("opc_orders", sa.Column("contract_no", sa.String(80), nullable=False, server_default=""))
    op.add_column("opc_orders", sa.Column("invoice_status", sa.String(32), nullable=False, server_default="NOT_REQUESTED"))
    op.create_table("opc_price_rules",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("category",sa.String(64),nullable=False),sa.Column("item_key",sa.String(80),nullable=False),sa.Column("unit",sa.String(24),nullable=False,server_default=""),
        sa.Column("unit_price",sa.Float(),nullable=False,server_default="0"),sa.Column("currency",sa.String(8),nullable=False,server_default="CNY"),
        sa.Column("version",sa.Integer(),nullable=False,server_default="1"),sa.Column("is_active",sa.Integer(),nullable=False,server_default="1"),
        sa.Column("extra_json",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),
        sa.Column("updated_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),**opts)
    op.create_index("ix_opc_price_owner", "opc_price_rules", ["owner_id"])
    op.create_index("ix_opc_price_lookup", "opc_price_rules", ["category","item_key"])
    op.create_table("opc_customer_followups",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("customer_id",sa.String(36),sa.ForeignKey("opc_customers.id"),nullable=False),sa.Column("channel",sa.String(32),nullable=False,server_default="note"),
        sa.Column("content",sa.Text(),nullable=False),sa.Column("next_at",sa.DateTime(),nullable=True),sa.Column("status",sa.String(24),nullable=False,server_default="OPEN"),
        sa.Column("created_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),**opts)
    op.create_index("ix_opc_followup_customer", "opc_customer_followups", ["customer_id"])
    op.create_table("opc_order_events",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("order_id",sa.String(36),sa.ForeignKey("opc_orders.id"),nullable=False),sa.Column("event_type",sa.String(40),nullable=False),
        sa.Column("from_status",sa.String(32),nullable=False,server_default=""),sa.Column("to_status",sa.String(32),nullable=False,server_default=""),
        sa.Column("data_json",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),**opts)
    op.create_index("ix_opc_order_event_order", "opc_order_events", ["order_id"])
    op.create_table("opc_inbound_messages",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_id",sa.String(36),sa.ForeignKey("users.id"),nullable=True),
        sa.Column("source",sa.String(32),nullable=False),sa.Column("external_id",sa.String(160),nullable=False,server_default=""),
        sa.Column("sender",sa.String(160),nullable=False,server_default=""),sa.Column("raw_text",sa.Text(),nullable=False),
        sa.Column("attachments_json",sa.Text(),nullable=False),sa.Column("status",sa.String(24),nullable=False,server_default="RECEIVED"),
        sa.Column("inquiry_id",sa.String(36),sa.ForeignKey("opc_inquiries.id"),nullable=True),sa.Column("created_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),**opts)
    op.create_index("ix_opc_inbound_source", "opc_inbound_messages", ["source","external_id"])
    op.create_table("opc_audit_logs",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("action",sa.String(80),nullable=False),sa.Column("entity_type",sa.String(40),nullable=False),sa.Column("entity_id",sa.String(64),nullable=False,server_default=""),
        sa.Column("data_json",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),**opts)
    op.create_index("ix_opc_audit_owner", "opc_audit_logs", ["owner_id","created_at"])
    op.create_table("opc_order_attachments",
        sa.Column("id",sa.String(36),primary_key=True),sa.Column("owner_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),
        sa.Column("order_id",sa.String(36),sa.ForeignKey("opc_orders.id"),nullable=False),sa.Column("kind",sa.String(32),nullable=False),
        sa.Column("file_name",sa.String(256),nullable=False),sa.Column("object_path",sa.String(512),nullable=False),
        sa.Column("content_type",sa.String(120),nullable=False,server_default="application/octet-stream"),
        sa.Column("created_at",sa.DateTime(),server_default=sa.text("CURRENT_TIMESTAMP"),nullable=False),**opts)
    op.create_index("ix_opc_order_attachment_order", "opc_order_attachments", ["order_id"])


def downgrade() -> None:
    for table in ("opc_order_attachments","opc_audit_logs","opc_inbound_messages","opc_order_events","opc_customer_followups","opc_price_rules"):
        op.drop_table(table)
    op.drop_column("opc_orders", "invoice_status")
    op.drop_column("opc_orders", "contract_no")
    op.drop_column("opc_orders", "payment_status")
    op.drop_column("opc_quotes", "excel_path")
    op.drop_column("opc_quotes", "pdf_path")
