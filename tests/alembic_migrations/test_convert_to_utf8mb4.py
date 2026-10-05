import io
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
PROD_LATIN1_TABLES = ["alembic_version", "ctf", "dynamic_role", "macro"]
PROD_UTF8MB4_TABLES = ["ban", "htb_discord_link", "infraction", "mute", "user_note"]
TABLES = PROD_LATIN1_TABLES + PROD_UTF8MB4_TABLES


def _offline_sql(revision_range: str, migrate=command.upgrade) -> str:
    buffer = io.StringIO()
    config = Config(str(REPO_ROOT / "alembic.ini"), output_buffer=buffer)
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    migrate(config, revision_range, sql=True)
    return buffer.getvalue()


def test_upgrade_sets_database_default_to_utf8mb4():
    sql = _offline_sql("d4f8c2a6e1b7:head")

    assert "ALTER DATABASE CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci" in sql


@pytest.mark.parametrize("table", TABLES)
def test_upgrade_converts_table_to_utf8mb4(table):
    sql = _offline_sql("d4f8c2a6e1b7:head")

    assert f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci" in sql


def test_downgrade_restores_database_default_to_latin1():
    sql = _offline_sql("7b3e9f1a2c5d:d4f8c2a6e1b7", migrate=command.downgrade)

    assert "ALTER DATABASE CHARACTER SET latin1 COLLATE latin1_swedish_ci" in sql


@pytest.mark.parametrize("table", PROD_LATIN1_TABLES)
def test_downgrade_converts_table_back_to_latin1(table):
    sql = _offline_sql("7b3e9f1a2c5d:d4f8c2a6e1b7", migrate=command.downgrade)

    assert f"ALTER TABLE `{table}` CONVERT TO CHARACTER SET latin1 COLLATE latin1_swedish_ci" in sql


@pytest.mark.parametrize("table", PROD_UTF8MB4_TABLES)
def test_downgrade_keeps_table_that_was_already_utf8mb4(table):
    sql = _offline_sql("7b3e9f1a2c5d:d4f8c2a6e1b7", migrate=command.downgrade)

    assert f"ALTER TABLE `{table}`" not in sql
