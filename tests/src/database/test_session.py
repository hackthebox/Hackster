import importlib
import logging

from src.core import settings
from src.database import session


def test_creating_the_engine_does_not_log_the_password(caplog, monkeypatch):
    # The alembic migration tests call logging.config.fileConfig, which disables existing loggers.
    monkeypatch.setattr(logging.getLogger("src.database.session"), "disabled", False)
    monkeypatch.setattr(settings.database, "PASSWORD", "not-in-the-logs")

    with caplog.at_level(logging.DEBUG):
        importlib.reload(session)

    assert "not-in-the-logs" not in caplog.text
