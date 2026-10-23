<<<<<<< HEAD
"""Tests for the deterministic alert engine (pure Python, no Streamlit)."""
from datetime import datetime, timedelta

import alert_engine
from simulator import make_event
from utils import parse_ts

CONFIG = {
    "quiet_hours": {"start": "01:00", "end": "05:00"},
    "rules": {
        "door_open_threshold_minutes": 5,
        "motion_burst_window_seconds": 60,
        "motion_burst_threshold": 3,
    },
}


def _ev(device_id, name, event_type, minutes_ago):
    return make_event(device_id, name, event_type,
                      datetime.now() - timedelta(minutes=minutes_ago), "test")


def test_normal_door_no_door_alert():
    events = [
        _ev("front_door", "Front Door", "door_open", 2),
        _ev("front_door", "Front Door", "door_close", 1),
    ]
    alerts = alert_engine.evaluate(events, CONFIG)
    assert not [a for a in alerts if a["type"] == "door_open_too_long"]


def test_door_open_too_long_then_closed_is_warning():
    events = [
        _ev("garage_door", "Garage Door", "door_open", 12),
        _ev("garage_door", "Garage Door", "door_close", 1),
    ]
    alerts = [a for a in alert_engine.evaluate(events, CONFIG) if a["type"] == "door_open_too_long"]
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "warning"


def test_door_still_open_is_critical():
    events = [_ev("garage_door", "Garage Door", "door_open", 12)]
    alerts = [a for a in alert_engine.evaluate(events, CONFIG) if a["type"] == "door_open_too_long"]
    assert len(alerts) == 1
    assert alerts[0]["severity"] == "critical"


def test_motion_burst_alert():
    now = datetime.now()
    events = [
        make_event("motion_sensor", "Motion Sensor", "motion_detected",
                   now - timedelta(seconds=20 - i * 4), "burst")
        for i in range(4)
    ]
    motion = [a for a in alert_engine.evaluate(events, CONFIG) if a["type"] == "repeated_motion"]
    assert len(motion) == 1


def test_single_motion_no_burst_alert():
    events = [_ev("motion_sensor", "Motion Sensor", "motion_detected", 1)]
    alerts = alert_engine.evaluate(events, CONFIG)
    assert not [a for a in alerts if a["type"] == "repeated_motion"]


def test_quiet_hours_alert():
    t = datetime.now().replace(hour=2, minute=30, second=0, microsecond=0)
    events = [make_event("motion_sensor", "Motion Sensor", "motion_detected", t, "overnight")]
    q = [a for a in alert_engine.evaluate(events, CONFIG) if a["type"] == "quiet_hours_activity"]
    assert len(q) == 1
    assert q[0]["severity"] == "info"


def test_outside_quiet_hours_no_quiet_alert():
    t = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    events = [make_event("motion_sensor", "Motion Sensor", "motion_detected", t, "daytime")]
    alerts = alert_engine.evaluate(events, CONFIG)
    assert not [a for a in alerts if a["type"] == "quiet_hours_activity"]


def test_quiet_hours_crossing_midnight():
    cfg = {"quiet_hours": {"start": "23:00", "end": "06:00"}, "rules": CONFIG["rules"]}
    inside = datetime.now().replace(hour=2, minute=30, second=0, microsecond=0)
    outside = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    assert any(a["type"] == "quiet_hours_activity"
               for a in alert_engine.evaluate([make_event("motion_sensor", "Motion Sensor", "motion_detected", inside, "x")], cfg))
    assert not [a for a in alert_engine.evaluate([make_event("motion_sensor", "Motion Sensor", "motion_detected", outside, "x")], cfg)
               if a["type"] == "quiet_hours_activity"]


def test_alerts_sorted_by_severity():
    events = [
        _ev("garage_door", "Garage Door", "door_open", 12),     # critical door alert
        _ev("motion_sensor", "Motion Sensor", "motion_detected", 1),
    ]
    alerts = alert_engine.evaluate(events, CONFIG)
    severities = [a["severity"] for a in alerts]
    # critical should appear before warning/info.
    if "critical" in severities and "info" in severities:
        assert severities.index("critical") < severities.index("info")



# --- Timestamps + structured fields on every alert -----------------------


def test_door_alert_critical_message_includes_timestamp_and_fields():
    events = [_ev("garage_door", "Garage Door", "door_open", 12)]
    a = [x for x in alert_engine.evaluate(events, CONFIG) if x["type"] == "door_open_too_long"][0]
    assert a["severity"] == "critical"
    assert "opened at" in a["message"]
    assert "still open" in a["message"]
    assert a["still_open"] is True
    assert "opened_at" in a
    assert a["threshold_min"] == 5


def test_door_alert_warning_message_includes_closed_timestamp():
    events = [
        _ev("garage_door", "Garage Door", "door_open", 12),
        _ev("garage_door", "Garage Door", "door_close", 1),
    ]
    a = [x for x in alert_engine.evaluate(events, CONFIG) if x["type"] == "door_open_too_long"][0]
    assert a["severity"] == "warning"
    assert "opened at" in a["message"] and "closed at" in a["message"]
    assert "opened_at" in a and "closed_at" in a
    assert "duration_min" in a


def test_motion_burst_message_includes_time_range_and_fields():
    now = datetime.now()
    events = [
        make_event("motion_sensor", "Motion Sensor", "motion_detected",
                   now - timedelta(seconds=20 - i * 4), "x")
        for i in range(4)
    ]
    a = [x for x in alert_engine.evaluate(events, CONFIG) if x["type"] == "repeated_motion"][0]
    assert "between" in a["message"]
    assert "first_at" in a and "last_at" in a
    assert a["count"] == 4


def test_quiet_hours_message_includes_date_and_fields():
    t = datetime.now().replace(hour=2, minute=30, second=0, microsecond=0)
    events = [make_event("motion_sensor", "Motion Sensor", "motion_detected", t, "overnight")]
    a = [x for x in alert_engine.evaluate(events, CONFIG) if x["type"] == "quiet_hours_activity"][0]
    assert t.strftime("%Y-%m-%d") in a["message"]
    assert "occurred_at" in a
    assert a["quiet_start"] == "01:00" and a["quiet_end"] == "05:00"
=======
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
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
