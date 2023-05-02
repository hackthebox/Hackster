from tempfile import NamedTemporaryFile

from src import cmds
from src.utils.extensions import unqualify, walk_extensions


def test_unqualify():
    """Test the `unqualify` function."""
    assert unqualify("bot.cmds.test") == "test"
    assert unqualify("bot.cmds.core.ping") == "ping"


def test_walk_extensions():
    """Test the `walk_extensions` function."""
    for ext in walk_extensions():
        assert ext.startswith(f"{cmds.__name__}.")


def test_walk_extensions_skip_ignored():
    """Extensions starting with _ should be ignored."""
    # Create a temporary file in the format _*.py.
    with NamedTemporaryFile(dir=cmds.__path__[0], prefix="_", suffix=".py", mode="w") as f:
        ext = f"{cmds.__name__}.{f.name.rsplit('/')[-1].removesuffix('.py')}"
        # Make sure the file is skipped.
        assert ext not in walk_extensions()
