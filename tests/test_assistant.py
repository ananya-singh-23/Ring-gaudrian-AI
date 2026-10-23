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
