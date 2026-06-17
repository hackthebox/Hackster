"""seed initial minor report reviewers

Revision ID: d4e5f6a7b8c9
Revises: c3f1a2b4d5e6, 9aa21aede2ec
Create Date: 2026-06-17 00:00:00.000000

"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = ("c3f1a2b4d5e6", "9aa21aede2ec")
branch_labels = None
depends_on = None

# Initial reviewers for the minor-report review channel (Discord user IDs).
SEED_REVIEWER_IDS = (
    561210274653274133,
    96269737343844352,
    484040243818004491,
)


def upgrade() -> None:
    connection = op.get_bind()
    created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    for user_id in SEED_REVIEWER_IDS:
        connection.execute(
            sa.text(
                "INSERT IGNORE INTO minor_review_reviewer (user_id, added_by, created_at) "
                "VALUES (:user_id, NULL, :created_at)"
            ),
            {"user_id": user_id, "created_at": created_at},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for user_id in SEED_REVIEWER_IDS:
        connection.execute(
            sa.text("DELETE FROM minor_review_reviewer WHERE user_id = :user_id"),
            {"user_id": user_id},
        )
