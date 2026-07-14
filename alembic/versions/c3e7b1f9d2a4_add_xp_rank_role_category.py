"""Add XP_RANK to dynamic_role category enum

Revision ID: c3e7b1f9d2a4
Revises: 9aa21aede2ec
Create Date: 2026-06-02 00:00:00.000000

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'c3e7b1f9d2a4'
down_revision = '9aa21aede2ec'
branch_labels = None
depends_on = None

_BASE_VALUES = (
    'RANK', 'SEASON', 'SUBSCRIPTION_LABS', 'SUBSCRIPTION_ACADEMY',
    'CREATOR', 'POSITION', 'ACADEMY_CERT', 'JOINABLE',
)


def upgrade() -> None:
    op.alter_column(
        'dynamic_role', 'category',
        existing_type=mysql.ENUM(*_BASE_VALUES, name='rolecategory'),
        type_=mysql.ENUM(*_BASE_VALUES, 'XP_RANK', name='rolecategory'),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'dynamic_role', 'category',
        existing_type=mysql.ENUM(*_BASE_VALUES, 'XP_RANK', name='rolecategory'),
        type_=mysql.ENUM(*_BASE_VALUES, name='rolecategory'),
        existing_nullable=False,
    )
