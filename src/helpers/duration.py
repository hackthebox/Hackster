import calendar
import logging
import re
import time

logger = logging.getLogger(__name__)


def validate_duration(duration: str, baseline_ts: int = None) -> (int, str):
    """Validate duration string and convert to seconds."""
    if duration.isnumeric():
        return 0, "Malformed duration. Please use duration units, (e.g. 12h, 14d, 5w)."

    dur = parse_duration_str(duration, baseline_ts)
    if dur is None:
        return 0, "Invalid duration: could not parse."
    if dur - calendar.timegm(time.gmtime()) <= 0:
        return 0, "Invalid duration: cannot be in the past."

    return dur, ""


def parse_duration_str(duration: str, baseline_ts: int = None) -> int | None:
    """
    Converts an arbitrary measure of time. Uses baseline_ts instead of the current time, if provided.

    Example: "3w" to a timestamp in seconds since 1970/01/01 (UNIX epoch time).
    """
    dur = re.compile(r"(-?(?:\d+\.?\d*|\d*\.?\d+)(?:e[-+]?\d+)?)\s*([a-z]*)", re.IGNORECASE)
    units = {"s": 1}
    units["m"] = units["min"] = units["mins"] = units["s"] * 60
    units["h"] = units["hr"] = units["hour"] = units["hours"] = units["m"] * 60
    units["d"] = units["day"] = units["days"] = units["h"] * 24
    units["wk"] = units["w"] = units["week"] = units["weeks"] = units["d"] * 7
    units["month"] = units["months"] = units["mo"] = units["d"] * 30
    units["y"] = units["yr"] = units["d"] * 365
    sum_seconds = 0

    while duration:
        m = dur.match(duration)
        if not m:
            return None
        duration = duration[m.end():]
        try:
            sum_seconds += int(m.groups()[0]) * units.get(m.groups()[1], 1)
        except ValueError:
            return None

    if baseline_ts is None:
        epoch_time = calendar.timegm(time.gmtime())
    else:
        epoch_time = baseline_ts
    return epoch_time + sum_seconds
