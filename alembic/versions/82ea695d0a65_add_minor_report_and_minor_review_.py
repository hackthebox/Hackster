"""add minor_report and minor_review_reviewer tables

Revision ID: 82ea695d0a65
Revises: 4fc1c39216c9
Create Date: 2026-02-16 12:31:57.651377

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '82ea695d0a65'
down_revision = '4fc1c39216c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "minor_report",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("reporter_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("suspected_age", sa.Integer(), nullable=False),
        sa.Column("evidence", mysql.TEXT(), nullable=False),
        sa.Column("report_message_id", mysql.BIGINT(display_width=20), nullable=False),
        sa.Column("status", mysql.VARCHAR(length=32), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", mysql.BIGINT(display_width=18), nullable=True),
        sa.Column("created_at", mysql.TIMESTAMP(), nullable=False),
        sa.Column("updated_at", mysql.TIMESTAMP(), nullable=False),
        sa.Column("associated_ban_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "minor_review_reviewer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("added_by", mysql.BIGINT(display_width=18), nullable=True),
        sa.Column("created_at", mysql.TIMESTAMP(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("minor_review_reviewer")
    op.drop_table("minor_report")
