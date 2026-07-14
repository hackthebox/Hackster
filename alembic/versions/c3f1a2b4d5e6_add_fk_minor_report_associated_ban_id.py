"""add FK constraint on minor_report.associated_ban_id

Revision ID: c3f1a2b4d5e6
Revises: 82ea695d0a65
Create Date: 2026-04-25 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c3f1a2b4d5e6'
down_revision = '82ea695d0a65'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_minor_report_associated_ban_id",
        "minor_report",
        "ban",
        ["associated_ban_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_minor_report_associated_ban_id",
        "minor_report",
        type_="foreignkey",
    )
