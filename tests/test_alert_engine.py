"""
tests/test_alert_engine.py — Unit tests for alert_engine.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone
from simulator import make_event
from alert_engine import (
    check_door_open_too_long,
    check_repeated_motion,
    check_quiet_hours,
    analyse_events,
    DEFAULT_CONFIG,
    load_config,
)

CFG = dict(DEFAULT_CONFIG)  # test config snapshot


# ── check_door_open_too_long ────────────────────────────────────────────────

def test_door_open_triggers_alert():
    """Door opened 10 min ago with no close → alert."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    events = [make_event("front_door", "door_opened", timestamp=ts)]
    alerts = check_door_open_too_long(events, CFG)
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "door_open_too_long"
    assert alerts[0]["device_id"] == "front_door"
    assert alerts[0]["severity"] == "medium"


def test_door_closed_no_alert():
    """Door opened then closed → no alert."""
    t0 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    t1 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=2)
    events = [
        make_event("front_door", "door_opened", timestamp=t0),
        make_event("front_door", "door_closed", timestamp=t1),
    ]
    alerts = check_door_open_too_long(events, CFG)
    assert alerts == []


def test_door_just_opened_no_alert():
    """Door opened only 1 min ago → below threshold, no alert."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    events = [make_event("front_door", "door_opened", timestamp=ts)]
    alerts = check_door_open_too_long(events, CFG)
    assert alerts == []


def test_multiple_doors_independent():
    """Two doors open → two alerts."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    events = [
        make_event("front_door",  "door_opened", timestamp=ts),
        make_event("garage_door", "door_opened", timestamp=ts),
    ]
    alerts = check_door_open_too_long(events, CFG)
    device_ids = {a["device_id"] for a in alerts}
    assert "front_door"  in device_ids
    assert "garage_door" in device_ids


# ── check_repeated_motion ───────────────────────────────────────────────────

def test_repeated_motion_triggers_alert():
    """3 motions within 5 min → alert."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=240)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=150)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=60)),
    ]
    alerts = check_repeated_motion(events, CFG)
    assert len(alerts) == 1
    assert alerts[0]["rule"] == "repeated_motion"
    assert alerts[0]["severity"] == "high"


def test_sparse_motion_no_alert():
    """3 motions spread over 30 min → no alert (window is 5 min)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(minutes=30)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(minutes=15)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(minutes=1)),
    ]
    alerts = check_repeated_motion(events, CFG)
    assert alerts == []


def test_two_motions_below_threshold():
    """Only 2 motion events (threshold is 3) → no alert."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=30)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=10)),
    ]
    alerts = check_repeated_motion(events, CFG)
    assert alerts == []


# ── check_quiet_hours ───────────────────────────────────────────────────────

def test_quiet_hours_alert_at_2am():
    """Event at 02:30 UTC → quiet-hours alert (23:00–06:00)."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=2, minute=30, second=0, microsecond=0)
    events = [make_event("doorbell", "doorbell_pressed", timestamp=ts)]
    alerts = check_quiet_hours(events, CFG)
    assert len(alerts) >= 1
    assert alerts[0]["rule"] == "quiet_hours_activity"


def test_quiet_hours_no_alert_at_noon():
    """Event at 12:00 UTC → no quiet-hours alert."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=12, minute=0, second=0, microsecond=0)
    events = [make_event("doorbell", "doorbell_pressed", timestamp=ts)]
    alerts = check_quiet_hours(events, CFG)
    assert alerts == []


def test_quiet_hours_event_older_than_24h_ignored():
    """Event 25 hours ago → ignored by quiet-hours rule."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=2, minute=0) - timedelta(hours=25)
    events = [make_event("doorbell", "doorbell_pressed", timestamp=ts)]
    alerts = check_quiet_hours(events, CFG)
    assert alerts == []


# ── analyse_events (integration) ───────────────────────────────────────────

def test_analyse_deduplicates():
    """Same rule + same device should appear only once."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=200)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=150)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=100)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=50)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=10)),
    ]
    alerts = analyse_events(events, CFG)
    repeated = [a for a in alerts if a["rule"] == "repeated_motion"]
    assert len(repeated) == 1


def test_analyse_empty_events():
    """No events → no alerts."""
    assert analyse_events([], CFG) == []


def test_analyse_returns_newest_first():
    """Alerts sorted newest generated_at first."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
    events = [make_event("front_door", "door_opened", timestamp=ts)]
    alerts = analyse_events(events, CFG)
    if len(alerts) > 1:
        for i in range(len(alerts) - 1):
            assert alerts[i]["generated_at"] >= alerts[i + 1]["generated_at"]
