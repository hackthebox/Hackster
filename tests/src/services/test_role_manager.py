import logging
from unittest.mock import patch

import pytest

from src.services.role_manager import RoleManager


@pytest.fixture(autouse=True)
def enabled_role_manager_logger(monkeypatch):
    # The alembic migration tests call logging.config.fileConfig, which disables existing loggers.
    monkeypatch.setattr(logging.getLogger("src.services.role_manager"), "disabled", False)


class TestLoad:
    @pytest.mark.asyncio
    async def test_failed_reload_keeps_cache_and_logs_the_cause_without_traceback(self, caplog):
        manager = RoleManager()
        manager._loaded = True
        with (
            patch("src.services.role_manager.AsyncSessionLocal", side_effect=RuntimeError("database is down")),
            caplog.at_level(logging.DEBUG, logger="src.services.role_manager"),
        ):
            await manager.load()

        records = [r for r in caplog.records if r.name == "src.services.role_manager"]
        assert len(records) == 1
        assert records[0].levelno == logging.WARNING
        assert records[0].getMessage() == (
            "Failed to reload dynamic roles from DB, keeping previous cache: database is down"
        )
        assert records[0].exc_info is None
