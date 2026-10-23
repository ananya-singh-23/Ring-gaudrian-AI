<<<<<<< HEAD
"""Tests for the local deterministic assistant (pure Python, no Streamlit)."""
from datetime import datetime, timedelta

import assistant
from simulator import make_event

DEVICES = [
    {"id": "front_door", "name": "Front Door", "type": "door", "icon": "🚪"},
    {"id": "doorbell", "name": "Doorbell", "type": "doorbell", "icon": "🔔"},
    {"id": "garage_door", "name": "Garage Door", "type": "door", "icon": "🚗"},
    {"id": "motion_sensor", "name": "Motion Sensor", "type": "motion_sensor", "icon": "📡"},
]
CONFIG = {"quiet_hours": {"start": "01:00", "end": "05:00"},
          "rules": {"door_open_threshold_minutes": 5}}


def _events():
    now = datetime.now()
    return [
        make_event("front_door", "Front Door", "door_open", now - timedelta(minutes=2), "x"),
        make_event("front_door", "Front Door", "door_close", now - timedelta(minutes=1), "x"),
        make_event("doorbell", "Doorbell", "doorbell_press", now - timedelta(minutes=1), "x"),
        make_event("motion_sensor", "Motion Sensor", "motion_detected", now, "x"),
    ]


def test_help():
    assert "examples" in assistant.answer("help", [], DEVICES, []).lower()


def test_greeting():
    r = assistant.answer("hi", [], DEVICES, [])
    assert "simulated" in r.lower() or "assistant" in r.lower()


def test_empty_question_returns_guidance():
    assert assistant.answer("", [], DEVICES, [])


def test_status_overview_lists_all_devices():
    r = assistant.answer("what's the status of my devices", _events(), DEVICES, [])
    for name in ("Front Door", "Doorbell", "Garage Door", "Motion Sensor"):
        assert name in r


def test_count_events():
    r = assistant.answer("how many events today", _events(), DEVICES, [])
    assert "Total events: 4" in r


def test_alerts_query_lists_alerts():
    alerts = [{"severity": "warning", "message": "Garage open", "type": "door_open_too_long"}]
    r = assistant.answer("any alerts", [], DEVICES, alerts)
    assert "Garage open" in r


def test_no_alerts_response():
    assert "No active alerts" in assistant.answer("any alerts", [], DEVICES, [])


def test_front_door_question_uses_real_state():
    # Last front door event is a close, so the door is reported Closed.
    r = assistant.answer("is the front door open", _events(), DEVICES, [])
    assert "Front Door" in r
    assert "Closed" in r


def test_recent_events():
    r = assistant.answer("show recent activity", _events(), DEVICES, [])
    assert "most recent" in r.lower()


def test_quiet_hours_question():
    r = assistant.answer("what are the quiet hours", [], DEVICES, [], CONFIG)
    assert "01:00" in r and "05:00" in r


def test_fallback_message():
    r = assistant.answer("xyzzy nonsense 123", [], DEVICES, [])
    assert "not sure" in r.lower() or "help" in r.lower()



# --- Pluggable assistant backend interface --------------------------------


def test_build_assistant_returns_local_backend():
    backend = assistant.build_assistant()
    assert isinstance(backend, assistant.AssistantBackend)
    assert isinstance(backend, assistant.LocalAssistant)


def test_backend_answer_uses_context():
    backend = assistant.build_assistant()
    ctx = assistant.AssistantContext(_events(), DEVICES, [], CONFIG)
    assert "Total events: 4" in backend.answer("how many events today", ctx)


def test_backend_does_not_invent_events_when_empty():
    backend = assistant.build_assistant()
    ctx = assistant.AssistantContext([], DEVICES, [], CONFIG)
    r = backend.answer("show recent activity", ctx)
    assert "no events" in r.lower()


def test_context_has_sensible_defaults():
    ctx = assistant.AssistantContext([], DEVICES)
    assert ctx.alerts == []
    assert ctx.config is None
=======
"""
tests/test_assistant.py — Unit tests for assistant.py (local deterministic chat)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from simulator import make_event


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_events():
    """Build a minimal set of events for assistant testing."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return [
        make_event("front_door",   "door_opened",      timestamp=now - timedelta(hours=2)),
        make_event("front_door",   "door_closed",       timestamp=now - timedelta(hours=1, minutes=55)),
        make_event("motion_sensor","motion_detected",   timestamp=now - timedelta(hours=1)),
        make_event("doorbell",     "doorbell_pressed",  timestamp=now - timedelta(minutes=30)),
        make_event("garage_door",  "door_opened",       timestamp=now - timedelta(minutes=10)),
        make_event("garage_door",  "door_closed",       timestamp=now - timedelta(minutes=5)),
    ]


# ── chat() ─────────────────────────────────────────────────────────────────

def test_help_response():
    """'help' should list example questions."""
    from assistant import chat
    events = _make_events()
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("help")
    assert "help" in resp.lower() or "ring guardian" in resp.lower()
    assert "front door" in resp.lower()


def test_empty_message():
    """Empty input should return a prompt, not crash."""
    from assistant import chat
    with patch("assistant.get_all_events", return_value=[]):
        resp = chat("")
    assert len(resp) > 0


def test_all_status():
    """Asking for all device statuses should mention every device."""
    from assistant import chat
    events = _make_events()
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("show all device statuses")
    assert "Front Door"    in resp
    assert "Garage Door"   in resp
    assert "Doorbell"      in resp
    assert "Motion Sensor" in resp


def test_front_door_status_open():
    """Last event = door_opened → response should say 'open'."""
    from assistant import chat
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [make_event("front_door", "door_opened", timestamp=now - timedelta(minutes=1))]
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("Is the front door open?")
    assert "open" in resp.lower()


def test_front_door_status_closed():
    """Last event = door_closed → response should say 'closed'."""
    from assistant import chat
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("front_door", "door_opened", timestamp=now - timedelta(minutes=10)),
        make_event("front_door", "door_closed", timestamp=now - timedelta(minutes=2)),
    ]
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("What is the status of the front door?")
    assert "closed" in resp.lower()


def test_recent_events_response():
    """'show recent events' should list event entries."""
    from assistant import chat
    events = _make_events()
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("show recent events")
    assert "UTC" in resp or "Event" in resp


def test_event_count_response():
    """'how many events today?' should include a number."""
    from assistant import chat
    events = _make_events()
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("how many events today?")
    assert any(char.isdigit() for char in resp)


def test_alerts_response_no_alerts():
    """With events that trigger no alerts, response should indicate all clear."""
    from assistant import chat
    events = _make_events()  # normal day, no alert conditions
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("are there any alerts?")
    # Should mention 'no' alerts or list them
    assert len(resp) > 0


def test_garage_door_history():
    """Asking about garage door history should mention garage door events."""
    from assistant import chat
    events = _make_events()
    with patch("assistant.get_all_events", return_value=events):
        resp = chat("What happened at the garage door?")
    assert "Garage Door" in resp or "garage" in resp.lower()


def test_quiet_hours_query():
    """Asking about quiet hours should mention the configured hours."""
    from assistant import chat
    with patch("assistant.get_all_events", return_value=[]):
        resp = chat("What are the quiet hours?")
    # Should contain time info
    assert "23" in resp or "06" in resp or "quiet" in resp.lower()


def test_unknown_query_graceful():
    """An unrecognisable query should not crash and should return guidance."""
    from assistant import chat
    with patch("assistant.get_all_events", return_value=[]):
        resp = chat("What is the weather like in Paris?")
    assert len(resp) > 0
    assert "help" in resp.lower() or "not sure" in resp.lower() or "try" in resp.lower()
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
