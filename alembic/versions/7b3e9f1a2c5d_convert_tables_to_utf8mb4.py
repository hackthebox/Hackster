"""Convert all tables and the database default to utf8mb4

Revision ID: 7b3e9f1a2c5d
Revises: d4f8c2a6e1b7
Create Date: 2026-10-05 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '7b3e9f1a2c5d'
down_revision = 'd4f8c2a6e1b7'
branch_labels = None
depends_on = None

# Tables alembic creates inherit the database default, and that default was
# latin1. Production had these four in latin1; a database built from scratch
# by alembic has every table in latin1.
_LATIN1_TABLES = ('alembic_version', 'ctf', 'dynamic_role', 'macro')
_UTF8MB4_TABLES = ('ban', 'htb_discord_link', 'infraction', 'mute', 'user_note')


def upgrade() -> None:
    op.execute("ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")
    for table in _LATIN1_TABLES + _UTF8MB4_TABLES:
        op.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci")


def downgrade() -> None:
    # The other tables were utf8mb4 in production and can hold characters
    # latin1 cannot store, so they stay as they are.
    for table in _LATIN1_TABLES:
        op.execute(f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET latin1 COLLATE latin1_swedish_ci")
    op.execute("ALTER DATABASE CHARACTER SET latin1 COLLATE latin1_swedish_ci")
