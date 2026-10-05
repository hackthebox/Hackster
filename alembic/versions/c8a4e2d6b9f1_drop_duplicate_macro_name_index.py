"""Drop the duplicate unique index on macro.name

Revision ID: c8a4e2d6b9f1
Revises: 7b3e9f1a2c5d
Create Date: 2026-10-05 12:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c8a4e2d6b9f1'
down_revision = '7b3e9f1a2c5d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 4fc1c39216c9 declared the name uniqueness twice, so MariaDB built `name` and `name_2`.
    op.execute("DROP INDEX name_2 ON macro")


def downgrade() -> None:
    # A unique index on a TEXT column needs USING HASH on MariaDB.
    op.execute("CREATE UNIQUE INDEX name_2 USING HASH ON macro (name)")
