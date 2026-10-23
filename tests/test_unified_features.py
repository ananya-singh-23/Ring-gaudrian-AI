"""Tests for requested deterministic alert details and local assistant intents."""
from datetime import datetime, timedelta

import alert_engine
import assistant
from simulator import make_event

DEVICES = [
    {"id": "front_door", "name": "Front Door", "type": "door", "icon": "🚪"},
    {"id": "doorbell", "name": "Doorbell", "type": "doorbell", "icon": "🔔"},
    {"id": "garage_door", "name": "Garage Door", "type": "door", "icon": "🚗"},
    {"id": "motion_sensor", "name": "Motion Sensor", "type": "motion_sensor", "icon": "📡"},
]
CONFIG = {
    "quiet_hours": {"start": "01:00", "end": "05:00"},
    "rules": {
        "door_open_threshold_minutes": 5,
        "motion_burst_window_seconds": 60,
        "motion_burst_threshold": 3,
        "event_burst_window_seconds": 60,
        "event_burst_threshold": 8,
    },
}


def test_alerts_have_rule_explanation_event_ids_and_timestamp():
    now = datetime.now()
    event = make_event("garage_door", "Garage Door", "door_open", now - timedelta(minutes=12))
    alerts = alert_engine.evaluate([event], CONFIG)
    alert = next(item for item in alerts if item["rule_id"] == "door_open_too_long")
    assert alert["explanation"] == alert["message"]
    assert alert["event_ids"] == [event["id"]]
    assert alert["timestamp"] == event["timestamp"]


def test_general_event_burst_detects_related_mixed_events():
    now = datetime.now()
    events = [make_event("front_door", "Front Door", "door_open" if i % 2 == 0 else "door_close",
                         now + timedelta(seconds=i * 2)) for i in range(8)]
    alerts = alert_engine.evaluate(events, CONFIG)
    burst = next(item for item in alerts if item["rule_id"] == "event_burst")
    assert burst["count"] == 8
    assert set(burst["event_ids"]) == {event["id"] for event in events}


def test_motion_alert_includes_all_related_event_ids():
    now = datetime.now()
    events = [make_event("motion_sensor", "Motion Sensor", "motion_detected",
                         now + timedelta(seconds=i * 4)) for i in range(4)]
    alerts = alert_engine.evaluate(events, CONFIG)
    burst = next(item for item in alerts if item["rule_id"] == "repeated_motion")
    assert set(burst["event_ids"]) == {event["id"] for event in events}


def test_assistant_summarizes_last_five_events_from_current_context():
    now = datetime.now()
    events = [make_event("front_door", "Front Door", "door_open",
                         now + timedelta(seconds=i), f"entry-{i}") for i in range(7)]
    reply = assistant.LocalAssistant().answer("Summarize the last five events",
                                              assistant.AssistantContext(events, DEVICES))
    assert "5 most recent" in reply
    assert "entry-6" in reply and "entry-2" in reply
    assert "entry-1" not in reply


def test_assistant_explains_alert_using_deterministic_result():
    event = make_event("garage_door", "Garage Door", "door_open", datetime.now() - timedelta(minutes=20))
    alerts = alert_engine.evaluate([event], CONFIG)
    reply = assistant.LocalAssistant().answer(
        "Why did the door-open alert trigger?", assistant.AssistantContext([event], DEVICES, alerts, CONFIG)
    )
    assert "deterministic rule engine" in reply
    assert event["id"] in reply
    assert "threshold" in reply


def test_assistant_reports_quiet_hours_activity_from_alerts():
    night = datetime.now().replace(hour=2, minute=30, second=0, microsecond=0)
    event = make_event("motion_sensor", "Motion Sensor", "motion_detected", night, "at night")
    alerts = alert_engine.evaluate([event], CONFIG)
    reply = assistant.LocalAssistant().answer(
        "What happened during quiet hours?", assistant.AssistantContext([event], DEVICES, alerts, CONFIG)
    )
    assert "Motion Sensor" in reply and "motion_detected" in reply


def test_assistant_reports_device_event_leader_and_missing_data():
    event = make_event("doorbell", "Doorbell", "doorbell_press")
    backend = assistant.LocalAssistant()
    reply = backend.answer("Which devices generated the most events?",
                           assistant.AssistantContext([event], DEVICES))
    assert "Doorbell" in reply and "1 event" in reply
    missing = backend.answer("Which devices generated the most events?",
                             assistant.AssistantContext([], DEVICES))
    assert "no events" in missing.lower()


def test_bedrock_backend_missing_configuration_falls_back_to_local(monkeypatch):
    for key in ("ASSISTANT_BACKEND", "BEDROCK_ENABLED", "BEDROCK_MODEL_ID", "AWS_REGION"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ASSISTANT_BACKEND", "bedrock")
    monkeypatch.setenv("BEDROCK_ENABLED", "true")
    assert isinstance(assistant.build_assistant(), assistant.LocalAssistant)
