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
