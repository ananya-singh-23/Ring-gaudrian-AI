<<<<<<< HEAD
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
=======
"""
tests/test_simulator.py — Unit tests for simulator.py
"""

import sys
from pathlib import Path
import tempfile
import json

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timedelta, timezone


# We monkey-patch the events file path before importing simulator
# so tests never touch the real data/events.json
@pytest.fixture(autouse=True)
def patch_events_file(tmp_path, monkeypatch):
    """Redirect EVENTS_FILE to a temp file for each test."""
    import simulator as sim
    temp_file = tmp_path / "events.json"
    temp_file.write_text("[]")
    monkeypatch.setattr(sim, "EVENTS_FILE", temp_file)
    return temp_file


# ── make_event ─────────────────────────────────────────────────────────────

def test_make_event_valid():
    from simulator import make_event
    ts = datetime(2024, 6, 1, 12, 0, 0)
    evt = make_event("front_door", "door_opened", timestamp=ts)
    assert evt["device_id"]   == "front_door"
    assert evt["device_name"] == "Front Door"
    assert evt["event_type"]  == "door_opened"
    assert evt["simulated"]   is True
    assert "id" in evt
    assert evt["timestamp"]   == ts.isoformat()


def test_make_event_unknown_device():
    from simulator import make_event
    with pytest.raises(ValueError, match="Unknown device_id"):
        make_event("nonexistent_device", "door_opened")


def test_make_event_extra_fields():
    from simulator import make_event
    evt = make_event("doorbell", "doorbell_pressed", extra={"note": "test"})
    assert evt["note"] == "test"


# ── persistence round-trip ──────────────────────────────────────────────────

def test_clear_and_save(patch_events_file):
    from simulator import clear_events, get_all_events, generate_random_event
    clear_events()
    assert get_all_events() == []
    generate_random_event()
    events = get_all_events()
    assert len(events) == 1
    assert events[0]["simulated"] is True


def test_generate_n_events(patch_events_file):
    from simulator import generate_n_random_events, get_all_events, clear_events
    clear_events()
    generate_n_random_events(5)
    assert len(get_all_events()) == 5


# ── get_device_status ───────────────────────────────────────────────────────

def test_device_status_open():
    from simulator import make_event, get_device_status
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=2)
    events = [make_event("front_door", "door_opened", timestamp=ts)]
    status = get_device_status(events)
    assert status["front_door"]["status"] == "open"


def test_device_status_closed():
    from simulator import make_event, get_device_status
    t0 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
    t1 = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    events = [
        make_event("front_door", "door_opened", timestamp=t0),
        make_event("front_door", "door_closed", timestamp=t1),
    ]
    status = get_device_status(events)
    assert status["front_door"]["status"] == "closed"


def test_device_status_unknown_when_no_events():
    from simulator import get_device_status
    status = get_device_status([])
    assert status["front_door"]["status"] == "unknown"


def test_device_status_motion_idle():
    from simulator import make_event, get_device_status
    events = [make_event("motion_sensor", "motion_detected")]
    status = get_device_status(events)
    assert status["motion_sensor"]["status"] == "idle"


# ── scenarios smoke-tests ───────────────────────────────────────────────────

def test_scenario_door_left_open(patch_events_file):
    from simulator import scenario_door_left_open, get_all_events, clear_events
    clear_events()
    evts = scenario_door_left_open()
    assert len(evts) >= 1
    assert any(e["event_type"] == "door_opened" for e in evts)


def test_scenario_repeated_motion(patch_events_file):
    from simulator import scenario_repeated_motion, clear_events
    clear_events()
    evts = scenario_repeated_motion()
    assert all(e["event_type"] == "motion_detected" for e in evts)
    assert len(evts) == 5


def test_scenario_normal_day(patch_events_file):
    from simulator import scenario_normal_day, clear_events
    clear_events()
    evts = scenario_normal_day()
    assert len(evts) == 8


def test_scenario_quiet_hours(patch_events_file):
    from simulator import scenario_quiet_hours_activity, clear_events
    clear_events()
    evts = scenario_quiet_hours_activity()
    assert len(evts) == 2
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
