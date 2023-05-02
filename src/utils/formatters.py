from src.core import constants


def color_level(value: float, low: float = constants.low_latency, high: float = constants.high_latency) -> int:
    """Return the color intensity of a value."""
    if value < low:
        return constants.colours.bright_green
    elif value < high:
        return constants.colours.orange
    else:
        return constants.colours.red
