"""Add XP_GRADE to dynamic_role category enum

Revision ID: d4f8c2a6e1b7
Revises: c3e7b1f9d2a4
Create Date: 2026-06-02 00:00:01.000000

"""
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd4f8c2a6e1b7'
down_revision = 'c3e7b1f9d2a4'
branch_labels = None
depends_on = None

_BASE_VALUES = (
    'RANK', 'SEASON', 'SUBSCRIPTION_LABS', 'SUBSCRIPTION_ACADEMY',
    'CREATOR', 'POSITION', 'ACADEMY_CERT', 'JOINABLE', 'XP_RANK',
)


def upgrade() -> None:
    op.alter_column(
        'dynamic_role', 'category',
        existing_type=mysql.ENUM(*_BASE_VALUES, name='rolecategory'),
        type_=mysql.ENUM(*_BASE_VALUES, 'XP_GRADE', name='rolecategory'),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'dynamic_role', 'category',
        existing_type=mysql.ENUM(*_BASE_VALUES, 'XP_GRADE', name='rolecategory'),
        type_=mysql.ENUM(*_BASE_VALUES, name='rolecategory'),
        existing_nullable=False,
    )
