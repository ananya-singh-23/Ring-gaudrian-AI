"""Tests for the shared event filter (verifies device + type + date filters combine)."""
from datetime import datetime, timedelta

from simulator import make_event
from utils import filter_events

NOW = datetime(2026, 10, 23, 12, 0, 0)


def _events():
    return [
        make_event("front_door", "Front Door", "door_open", NOW - timedelta(hours=1), "a"),
        make_event("front_door", "Front Door", "door_close", NOW - timedelta(minutes=30), "b"),
        make_event("motion_sensor", "Motion Sensor", "motion_detected", NOW - timedelta(minutes=10), "c"),
        make_event("doorbell", "Doorbell", "doorbell_press", NOW - timedelta(minutes=5), "d"),
        make_event("garage_door", "Garage Door", "door_open", NOW - timedelta(days=8), "e"),
        make_event("garage_door", "Garage Door", "door_close", NOW - timedelta(hours=2), "f"),
    ]


def test_no_filters_returns_all():
    assert len(filter_events(_events(), now=NOW)) == 6


def test_filter_by_device():
    r = filter_events(_events(), device_names=["Front Door"], now=NOW)
    assert len(r) == 2
    assert all(e["device_name"] == "Front Door" for e in r)


def test_filter_by_event_type():
    r = filter_events(_events(), event_types=["motion_detected"], now=NOW)
    assert len(r) == 1
    assert r[0]["event_type"] == "motion_detected"


def test_device_and_type_together():
    r = filter_events(_events(), device_names=["Front Door"],
                      event_types=["door_open"], now=NOW)
    assert len(r) == 1
    assert r[0]["event_type"] == "door_open"


def test_date_range_today_excludes_old():
    r = filter_events(_events(), date_range="Today", now=NOW)
    assert len(r) == 5  # everything except the 8-day-old event
    assert all(e["details"] != "e" for e in r)


def test_date_range_last_7_days_excludes_old():
    r = filter_events(_events(), date_range="Last 7 days", now=NOW)
    assert len(r) == 5  # excludes the 8-day-old event


def test_all_three_filters_combined():
    r = filter_events(_events(),
                      device_names=["Front Door"],
                      event_types=["door_open"],
                      date_range="Today",
                      now=NOW)
    assert len(r) == 1
    assert r[0]["device_name"] == "Front Door"
    assert r[0]["event_type"] == "door_open"


def test_multiple_devices_and_types_with_date():
    r = filter_events(_events(),
                      device_names=["Front Door", "Garage Door"],
                      event_types=["door_open"],
                      date_range="Last 7 days",
                      now=NOW)
    # Only the front-door open (1h ago) qualifies; the garage open is 8 days old.
    assert len(r) == 1
    assert r[0]["device_name"] == "Front Door"
