import io
from pathlib import Path

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
PREVIOUS_HEAD = "7b3e9f1a2c5d"
REVISION = "c8a4e2d6b9f1"


def _offline_sql(revision_range: str, migrate=command.upgrade) -> str:
    buffer = io.StringIO()
    config = Config(str(REPO_ROOT / "alembic.ini"), output_buffer=buffer)
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    migrate(config, revision_range, sql=True)
    return buffer.getvalue()


def test_upgrade_drops_duplicate_name_index_and_keeps_the_original():
    sql = _offline_sql(f"{PREVIOUS_HEAD}:{REVISION}")

    assert "DROP INDEX name_2 ON macro" in sql
    assert "DROP INDEX name ON macro" not in sql


def test_downgrade_recreates_duplicate_name_index_as_a_hash_unique_index():
    sql = _offline_sql(f"{REVISION}:{PREVIOUS_HEAD}", migrate=command.downgrade)

    assert "CREATE UNIQUE INDEX name_2 USING HASH ON macro (name)" in sql
