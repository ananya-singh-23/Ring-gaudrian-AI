"""Tests for the deterministic garage-door threshold demo scenario."""
from datetime import datetime

import alert_engine
import simulator
from utils import parse_ts

DEVICES = [
    {"id": "front_door", "name": "Front Door", "type": "door", "icon": "🚪"},
    {"id": "doorbell", "name": "Doorbell", "type": "doorbell", "icon": "🔔"},
    {"id": "garage_door", "name": "Garage Door", "type": "door", "icon": "🚗"},
    {"id": "motion_sensor", "name": "Motion Sensor", "type": "motion_sensor", "icon": "📡"},
]


def test_demo_generates_single_garage_open_event():
    cfg = {"rules": {"door_open_threshold_minutes": 5}}
    evs = simulator.scenario_garage_threshold_demo(DEVICES, cfg, datetime.now())
    assert len(evs) == 1
    assert evs[0]["device_id"] == "garage_door"
    assert evs[0]["event_type"] == "door_open"


def test_demo_exceeds_default_threshold_and_alerts():
    cfg = {"quiet_hours": {"start": "01:00", "end": "05:00"},
           "rules": {"door_open_threshold_minutes": 5}}
    evs = simulator.scenario_garage_threshold_demo(DEVICES, cfg, datetime.now())
    alerts = alert_engine.evaluate(evs, cfg)
    assert any(a["type"] == "door_open_too_long" for a in alerts)


def test_demo_adapts_to_a_raised_threshold():
    # With a 20-minute threshold the demo must still exceed it and still alert.
    cfg = {"rules": {"door_open_threshold_minutes": 20}}
    evs = simulator.scenario_garage_threshold_demo(DEVICES, cfg, datetime.now())
    open_for = (datetime.now() - parse_ts(evs[0]["timestamp"])).total_seconds() / 60
    assert open_for > 20
    assert any(a["type"] == "door_open_too_long" for a in alert_engine.evaluate(evs, cfg))


def test_demo_is_deterministic_for_same_base():
    cfg = {"rules": {"door_open_threshold_minutes": 5}}
    base = datetime(2026, 1, 1, 12, 0, 0)
    a = simulator.scenario_garage_threshold_demo(DEVICES, cfg, base)
    b = simulator.scenario_garage_threshold_demo(DEVICES, cfg, base)
    # Same base -> identical timestamp (ids differ by design).
    assert a[0]["timestamp"] == b[0]["timestamp"]
    # Details mention the configured threshold for traceability.
    assert "threshold 5 min" in a[0]["details"]


def test_demo_missing_device_returns_empty():
    assert simulator.scenario_garage_threshold_demo([], {"rules": {}}) == []
