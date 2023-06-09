"""Add infraction_record table

Revision ID: 49c63ed4411d
Revises: 5bf8bbb7032f
Create Date: 2022-09-01 17:06:19.341659

"""
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision = "49c63ed4411d"
down_revision = "5bf8bbb7032f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "infraction_record",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", mysql.VARCHAR(length=42), nullable=False),
        sa.Column("reason", mysql.TEXT(), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("moderator", mysql.VARCHAR(length=42), nullable=False),
        sa.Column("date", sa.DATE(), server_default=sa.text("curdate()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("infraction_record")
    # ### end Alembic commands ###
