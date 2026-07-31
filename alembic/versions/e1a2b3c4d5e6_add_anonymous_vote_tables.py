"""Add anonymous vote tables

Revision ID: e1a2b3c4d5e6
Revises: d4f8c2a6e1b7
Create Date: 2026-07-31 13:53:00.000000

"""
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

# revision identifiers, used by Alembic.
revision = "e1a2b3c4d5e6"
down_revision = "d4f8c2a6e1b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anonymous_vote_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("channel_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("message_id", mysql.BIGINT(display_width=18), nullable=True),
        sa.Column("topic", mysql.TEXT(), nullable=True),
        sa.Column("created_by_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("closes_at", mysql.TIMESTAMP(), nullable=False),
        sa.Column("closed", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anonymous_vote_candidate",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("display_name", mysql.TEXT(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["anonymous_vote_session.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "anonymous_vote_ballot",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("voter_id", mysql.BIGINT(display_width=18), nullable=False),
        sa.Column("choice", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["anonymous_vote_candidate.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["anonymous_vote_session.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "candidate_id",
            "voter_id",
            name="uq_anonymous_vote_ballot_session_candidate_voter",
        ),
    )


def downgrade() -> None:
    op.drop_table("anonymous_vote_ballot")
    op.drop_table("anonymous_vote_candidate")
    op.drop_table("anonymous_vote_session")
