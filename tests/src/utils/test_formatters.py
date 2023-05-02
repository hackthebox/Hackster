from src.core import constants
from src.utils.formatters import color_level


def test_color_level():
    """Test the `color_level` function."""
    low, high = 200, 400

    assert color_level(150, low, high) == constants.colours.bright_green
    assert color_level(200, low, high) == constants.colours.orange
    assert color_level(350, low, high) == constants.colours.orange
    assert color_level(500, low, high) == constants.colours.red
