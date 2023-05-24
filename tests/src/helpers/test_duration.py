import calendar
import time

from src.helpers.duration import validate_duration


def test_validate_duration_numeric():
    duration = "3600"
    result = validate_duration(duration)
    assert result == (0, "Malformed duration. Please use duration units, (e.g. 12h, 14d, 5w).")


def test_validate_duration_invalid_parse():
    duration = "not-to-be-parsed"
    result = validate_duration(duration)
    assert result == (0, "Invalid duration: could not parse.")


def test_validate_duration_past():
    duration = "-1h"
    baseline_ts = calendar.timegm(time.gmtime())
    result = validate_duration(duration, baseline_ts=baseline_ts)
    assert result == (0, "Invalid duration: cannot be in the past.")


def test_validate_duration_valid():
    duration = "1h"
    now = calendar.timegm(time.gmtime())
    result = validate_duration(duration)
    assert result == (now + 3600, "")


def test_validate_duration_valid_with_baseline():
    duration = "1h"
    baseline_ts = calendar.timegm(time.gmtime()) + 3600  # Set baseline in the future
    result = validate_duration(duration, baseline_ts=baseline_ts)
    assert result == (baseline_ts + 3600, "")


def test_validate_duration_zero():
    duration = "0s"
    baseline_ts = calendar.timegm(time.gmtime())
    result = validate_duration(duration, baseline_ts)
    assert result == (0, "Invalid duration: cannot be in the past.")
