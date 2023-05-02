import os

import pytest


@pytest.hookimpl(tryfirst=True)
def pytest_load_initial_conftests():
    os.environ["BOT_TOKEN"] = "ODk3MTVyNDOb50MDAxODE0NTC4.YWRgYg.hqWNRybjyk1j2h3h42vEoc8feoNqR0ubBCYwxo"
    os.environ["GUILD_IDS"] = "[7764771731239076051,8312163095926538351]"
