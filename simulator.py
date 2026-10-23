"""
simulator.py — Simulated event generator for Ring Guardian AI.

NOTE: All devices and events are SIMULATED. No real Ring hardware,
real Ring credentials, or AWS account is required.
"""

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Device registry
# ---------------------------------------------------------------------------

DEVICES = [
    {"id": "front_door",     "name": "Front Door",     "type": "door_sensor"},
    {"id": "doorbell",       "name": "Doorbell",        "type": "doorbell"},
    {"id": "garage_door",    "name": "Garage Door",     "type": "door_sensor"},
    {"id": "motion_sensor",  "name": "Motion Sensor",   "type": "motion_sensor"},
]

# Map device type → possible event types
DEVICE_EVENT_MAP = {
    "door_sensor":    ["door_opened", "door_closed"],
    "doorbell":       ["doorbell_pressed", "motion_detected"],
    "motion_sensor":  ["motion_detected"],
}

EVENTS_FILE = Path(__file__).parent / "data" / "events.json"


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _load_events() -> list[dict]:
    """Load persisted events from JSON file, return empty list on any error."""
    try:
        if EVENTS_FILE.exists():
            with EVENTS_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _save_events(events: list[dict]) -> None:
    """Persist event list to JSON file, creating parent dirs as needed."""
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_FILE.open("w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, default=str)
    except OSError as exc:
        print(f"[simulator] Warning: could not save events — {exc}")


# ---------------------------------------------------------------------------
# Event factory
# ---------------------------------------------------------------------------

def make_event(
    device_id: str,
    event_type: str,
    timestamp: datetime | None = None,
    extra: dict | None = None,
) -> dict:
    """
    Build a single structured event dict.

    Args:
        device_id:  Key from DEVICES list (e.g. 'front_door').
        event_type: Event label (e.g. 'door_opened').
        timestamp:  Explicit datetime; defaults to now (UTC).
        extra:      Optional dict merged into the event payload.

    Returns:
        Event dict with id, device_id, device_name, event_type, timestamp, simulated=True.
    """
    device = next((d for d in DEVICES if d["id"] == device_id), None)
    if device is None:
        raise ValueError(f"Unknown device_id: {device_id!r}")

    ts = timestamp or datetime.now(timezone.utc).replace(tzinfo=None)

    event = {
        "id":          str(uuid.uuid4()),
        "device_id":   device_id,
        "device_name": device["name"],
        "device_type": device["type"],
        "event_type":  event_type,
        "timestamp":   ts.isoformat(),
        "simulated":   True,          # Always True — no real hardware
    }
    if extra:
        event.update(extra)
    return event


# ---------------------------------------------------------------------------
# Public API — random events
# ---------------------------------------------------------------------------

def generate_random_event() -> dict:
    """Generate one random event for a randomly chosen device."""
    device = random.choice(DEVICES)
    event_types = DEVICE_EVENT_MAP[device["type"]]
    event_type = random.choice(event_types)
    event = make_event(device["id"], event_type)
    _append_event(event)
    return event


def generate_n_random_events(n: int = 10) -> list[dict]:
    """Generate *n* random events spread across the last 24 hours."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = []
    for _ in range(n):
        device = random.choice(DEVICES)
        event_types = DEVICE_EVENT_MAP[device["type"]]
        event_type = random.choice(event_types)
        # Random offset within the last 24 hours
        offset_seconds = random.randint(0, 86_400)
        ts = now - timedelta(seconds=offset_seconds)
        events.append(make_event(device["id"], event_type, timestamp=ts))

    # Sort chronologically before persisting
    events.sort(key=lambda e: e["timestamp"])
    for evt in events:
        _append_event(evt)
    return events


def _append_event(event: dict) -> None:
    """Append one event to the persistent store."""
    events = _load_events()
    events.append(event)
    _save_events(events)


# ---------------------------------------------------------------------------
# Scenario generators — pre-built stories for the demo
# ---------------------------------------------------------------------------

def scenario_door_left_open() -> list[dict]:
    """
    Front door opened and NOT closed for 10 minutes.
    Should trigger an 'open too long' alert.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("front_door", "door_opened",  timestamp=now - timedelta(minutes=10)),
        # Deliberately no door_closed event
    ]
    for e in events:
        _append_event(e)
    return events


def scenario_repeated_motion() -> list[dict]:
    """
    Five motion detections within 2 minutes.
    Should trigger a 'repeated motion' alert.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=110)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=85)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=60)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=35)),
        make_event("motion_sensor", "motion_detected", timestamp=now - timedelta(seconds=10)),
    ]
    for e in events:
        _append_event(e)
    return events


def scenario_quiet_hours_activity() -> list[dict]:
    """
    Doorbell + front-door open at 02:30 (within typical quiet hours).
    Should trigger an 'unusual hours' alert.
    """
    # Build a timestamp that falls in the quiet window (02:30 today)
    today = datetime.now(timezone.utc).replace(tzinfo=None).replace(hour=2, minute=30, second=0, microsecond=0)
    events = [
        make_event("doorbell",   "doorbell_pressed", timestamp=today),
        make_event("front_door", "door_opened",      timestamp=today + timedelta(seconds=15)),
    ]
    for e in events:
        _append_event(e)
    return events


def scenario_normal_day() -> list[dict]:
    """
    A routine day: door open/close, doorbell, garage, motion — nothing alarming.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        make_event("front_door",  "door_opened",       timestamp=now - timedelta(hours=8)),
        make_event("front_door",  "door_closed",       timestamp=now - timedelta(hours=8, seconds=-30)),
        make_event("doorbell",    "doorbell_pressed",  timestamp=now - timedelta(hours=6)),
        make_event("motion_sensor","motion_detected",  timestamp=now - timedelta(hours=4)),
        make_event("garage_door", "door_opened",       timestamp=now - timedelta(hours=2)),
        make_event("garage_door", "door_closed",       timestamp=now - timedelta(hours=2, seconds=-60)),
        make_event("front_door",  "door_opened",       timestamp=now - timedelta(hours=1)),
        make_event("front_door",  "door_closed",       timestamp=now - timedelta(minutes=55)),
    ]
    for e in events:
        _append_event(e)
    return events


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def get_all_events() -> list[dict]:
    """Return all persisted events, sorted oldest-first."""
    events = _load_events()
    return sorted(events, key=lambda e: e["timestamp"])


def clear_events() -> None:
    """Wipe all persisted events (used by tests and the Reset button)."""
    _save_events([])


def get_device_status(events: list[dict] | None = None) -> dict[str, dict]:
    """
    Derive current device status from the most-recent event per device.

    Returns a dict keyed by device_id:
        {
            "front_door": {
                "name": "Front Door",
                "type": "door_sensor",
                "status": "open" | "closed" | "idle" | "unknown",
                "last_event": "door_opened",
                "last_seen": "2024-01-01T12:00:00",
            },
            ...
        }
    """
    if events is None:
        events = get_all_events()

    # Index latest event per device
    latest: dict[str, dict] = {}
    for evt in events:
        did = evt["device_id"]
        if did not in latest or evt["timestamp"] > latest[did]["timestamp"]:
            latest[did] = evt

    status_map = {}
    for device in DEVICES:
        did = device["id"]
        last = latest.get(did)
        if last is None:
            status = "unknown"
            last_event = None
            last_seen = None
        else:
            et = last["event_type"]
            if et == "door_opened":
                status = "open"
            elif et == "door_closed":
                status = "closed"
            elif et in ("motion_detected", "doorbell_pressed"):
                status = "idle"
            else:
                status = "unknown"
            last_event = et
            last_seen = last["timestamp"]

        status_map[did] = {
            "name":       device["name"],
            "type":       device["type"],
            "status":     status,
            "last_event": last_event,
            "last_seen":  last_seen,
        }

    return status_map
