"""initial_tables

Revision ID: 253b48e23ce5
Revises:
Create Date: 2026-05-15 00:26:48.948640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '253b48e23ce5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users 表
    op.create_table(
        'users',
        sa.Column('id',            sa.String(36),  nullable=False),
        sa.Column('username',      sa.String(64),  nullable=False),
        sa.Column('password_hash', sa.String(128), nullable=False),
        sa.Column('is_active',     sa.Boolean(),   nullable=False, server_default='1'),
        sa.Column('created_at',    sa.DateTime(),  nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at',    sa.DateTime(),  nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index('idx_username', 'users', ['username'])

    # tasks 表
    op.create_table(
        'tasks',
        sa.Column('id',           sa.String(36),  nullable=False),
        sa.Column('user_id',      sa.String(36),  nullable=False),
        sa.Column('file_name',    sa.String(256), nullable=False),
        sa.Column('file_type',    sa.String(16),  nullable=False),
        sa.Column('file_id',      sa.String(512), nullable=False),
        sa.Column('file_size',    sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('status',       sa.String(16),  nullable=False, server_default='PENDING'),
        sa.Column('current_step', sa.String(64),  nullable=True),
        sa.Column('progress',     sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('steps_json',   sa.Text(),      nullable=True),
        sa.Column('error_msg',    sa.Text(),      nullable=True),
        sa.Column('created_at',   sa.DateTime(),  nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at',   sa.DateTime(),  nullable=False, server_default=sa.text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_tasks_user'),
        sa.PrimaryKeyConstraint('id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )
    op.create_index('idx_tasks_user_id',    'tasks', ['user_id'])
    op.create_index('idx_tasks_status',     'tasks', ['status'])
    op.create_index('idx_tasks_created_at', 'tasks', ['created_at'])

    # reports 表
    op.create_table(
        'reports',
        sa.Column('id',         sa.String(36),  nullable=False),
        sa.Column('task_id',    sa.String(36),  nullable=False),
        sa.Column('pdf_path',   sa.String(512), nullable=True),
        sa.Column('excel_path', sa.String(512), nullable=True),
        sa.Column('created_at', sa.DateTime(),  nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name='fk_reports_task'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id'),
        mysql_charset='utf8mb4',
        mysql_collate='utf8mb4_unicode_ci',
    )


def downgrade() -> None:
    op.drop_table('reports')
    op.drop_table('tasks')
    op.drop_table('users')
