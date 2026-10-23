"""Tests for the event simulator (pure Python, no Streamlit needed)."""
from datetime import datetime, timedelta

import pytest

import simulator
from utils import DEVICE_EVENT_TYPES, parse_ts

DEVICES = [
    {"id": "front_door", "name": "Front Door", "type": "door", "icon": "🚪"},
    {"id": "doorbell", "name": "Doorbell", "type": "doorbell", "icon": "🔔"},
    {"id": "garage_door", "name": "Garage Door", "type": "door", "icon": "🚗"},
    {"id": "motion_sensor", "name": "Motion Sensor", "type": "motion_sensor", "icon": "📡"},
]


def test_make_event_fields():
    e = simulator.make_event("front_door", "Front Door", "door_open")
    assert e["device_id"] == "front_door"
    assert e["device_name"] == "Front Door"
    assert e["event_type"] == "door_open"
    assert e["simulated"] is True
    assert e["id"]
    # Timestamp is a valid ISO string.
    assert parse_ts(e["timestamp"]) is not None


def test_make_event_rejects_unknown_type():
    with pytest.raises(ValueError):
        simulator.make_event("x", "x", "not_a_real_type")


def test_normal_entry_opens_then_closes():
    evs = simulator.scenario_normal_entry(DEVICES, datetime.now())
    assert len(evs) == 2
    assert evs[0]["event_type"] == "door_open"
    assert evs[1]["event_type"] == "door_close"
    assert evs[1]["timestamp"] > evs[0]["timestamp"]


def test_door_left_open_is_single_open_event():
    evs = simulator.scenario_door_left_open(DEVICES, datetime.now())
    assert len(evs) == 1
    assert evs[0]["event_type"] == "door_open"
    assert evs[0]["device_id"] == "garage_door"


def test_motion_burst_count_and_window():
    evs = simulator.scenario_motion_burst(DEVICES, datetime.now())
    assert len(evs) == 5
    times = [parse_ts(e["timestamp"]) for e in evs]
    span = (max(times) - min(times)).total_seconds()
    assert span <= 60
    assert all(e["event_type"] == "motion_detected" for e in evs)


def test_doorbell_scenario():
    evs = simulator.scenario_doorbell(DEVICES, datetime.now())
    assert len(evs) == 1
    assert evs[0]["event_type"] == "doorbell_press"


def test_overnight_motion_is_during_default_quiet_hours():
    evs = simulator.scenario_overnight_motion(DEVICES, datetime.now())
    assert len(evs) == 1
    ts = parse_ts(evs[0]["timestamp"])
    # 02:30 local time falls inside the default 01:00-05:00 quiet window.
    assert ts.hour == 2 and ts.minute == 30


def test_random_event_has_valid_type_for_device():
    import random
    random.seed(42)
    evs = simulator.random_event(DEVICES, datetime.now())
    assert len(evs) == 1
    e = evs[0]
    dev = next(d for d in DEVICES if d["id"] == e["device_id"])
    assert e["event_type"] in DEVICE_EVENT_TYPES[dev["type"]]


def test_scenarios_handle_missing_device():
    # If a device id isn't present, scenarios return an empty list, not an error.
    assert simulator.scenario_normal_entry([]) == []
    assert simulator.random_event([]) == []
