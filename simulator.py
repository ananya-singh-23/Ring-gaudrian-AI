<<<<<<< HEAD
"""Simulated event generation for the Ring Guardian AI dashboard.

Every event produced here is synthetic. Nothing in this module talks to
real Ring hardware, real network APIs, or real credentials.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from utils import EVENT_TYPE_META, DEVICE_EVENT_TYPES


def make_event(device_id: str, device_name: str, event_type: str,
               timestamp: Optional[datetime] = None, details: str = "") -> Dict[str, Any]:
    """Build a single simulated event dictionary.

    Raises ``ValueError`` if an unknown event type is requested, which
    helps catch typos during development.
    """
    if event_type not in EVENT_TYPE_META:
        raise ValueError(f"Unknown event type: {event_type!r}")
    return {
        "id": uuid.uuid4().hex[:8],
        "timestamp": (timestamp or datetime.now()).isoformat(),
        "device_id": device_id,
        "device_name": device_name,
        "event_type": event_type,
        "details": details or "",
        "simulated": True,
    }


def _find(devices: List[Dict[str, Any]], device_id: str) -> Optional[Dict[str, Any]]:
    for d in devices:
        if d.get("id") == device_id:
            return d
    return None


def _random_event_type(device: Dict[str, Any]) -> str:
    types = DEVICE_EVENT_TYPES.get(device.get("type", ""), ["motion_detected"])
    return random.choice(types)


# --- Scenario generators -------------------------------------------------
# Each returns a list of timestamped events. Timestamps are placed relative
# to "now" so generated events are always recent and clearly demonstrate
# the corresponding alert rule.


def scenario_normal_entry(devices: List[Dict[str, Any]], base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Front door opened then closed ~45s later. No alert expected."""
    d = _find(devices, "front_door")
    if not d:
        return []
    t = base or datetime.now()
    return [
        make_event(d["id"], d["name"], "door_open", t - timedelta(seconds=45), "Opened from inside"),
        make_event(d["id"], d["name"], "door_close", t, "Closed normally"),
    ]


def scenario_door_left_open(devices: List[Dict[str, Any]], base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Garage door opened 12 minutes ago and never closed. Should alert."""
    d = _find(devices, "garage_door")
    if not d:
        return []
    t = base or datetime.now()
    return [
        make_event(d["id"], d["name"], "door_open", t - timedelta(minutes=12), "Opened — no close event received"),
    ]


def scenario_garage_threshold_demo(devices: List[Dict[str, Any]],
                                   config: Optional[Dict[str, Any]] = None,
                                   base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Deterministic demo: garage door opened *past the configured threshold*.

    The open duration is set to ``threshold + 3`` minutes (never less than one
    minute over), so this always trips the door-open rule regardless of the
    current configuration. Deterministic given ``config``: no randomness, no
    clock jitter. Pair with "Reset" (clearing events) to repeat the demo.
    """
    d = _find(devices, "garage_door")
    if not d:
        return []
    rules = (config or {}).get("rules", {})
    threshold = int(rules.get("door_open_threshold_minutes", 5))
    minutes_open = max(threshold + 3, threshold + 1)
    t = base or datetime.now()
    return [
        make_event(d["id"], d["name"], "door_open",
                   t - timedelta(minutes=minutes_open),
                   f"DEMO: garage door opened {minutes_open} min ago "
                   f"(configured threshold {threshold} min)"),
    ]


def scenario_motion_burst(devices: List[Dict[str, Any]], base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Five motion events within 30 seconds. Should trigger a burst alert."""
    d = _find(devices, "motion_sensor")
    if not d:
        return []
    t = base or datetime.now()
    events = []
    for i in range(5):
        events.append(
            make_event(d["id"], d["name"], "motion_detected",
                       t - timedelta(seconds=30) + timedelta(seconds=i * 5),
                       f"Repeated movement {i + 1}/5")
        )
    return events


def scenario_doorbell(devices: List[Dict[str, Any]], base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """A single doorbell press. No alert expected."""
    d = _find(devices, "doorbell")
    if not d:
        return []
    t = base or datetime.now()
    return [make_event(d["id"], d["name"], "doorbell_press", t, "Doorbell pressed at the front step")]


def scenario_overnight_motion(devices: List[Dict[str, Any]], base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Motion detected at 02:30 today, inside the default quiet hours."""
    d = _find(devices, "motion_sensor")
    if not d:
        return []
    now = base or datetime.now()
    overnight = now.replace(hour=2, minute=30, second=0, microsecond=0)
    if overnight > now:
        overnight -= timedelta(days=1)
    return [make_event(d["id"], d["name"], "motion_detected", overnight, "Unexpected movement during quiet hours")]


def random_event(devices: List[Dict[str, Any]], base: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Generate one random event from a random simulated device."""
    if not devices:
        return []
    d = random.choice(devices)
    return [make_event(d["id"], d["name"], _random_event_type(d),
                       base or datetime.now(), "Random simulated event")]


SCENARIOS = [
    ("🚪 Normal entry", "scenario_normal_entry", "Front door opened and closed — no alert."),
    ("🚗 Door left open", "scenario_door_left_open", "Garage door left open past the threshold — should alert."),
    ("📡 Motion burst", "scenario_motion_burst", "Several motion events in 30s — should alert."),
    ("🔔 Doorbell press", "scenario_doorbell", "A single doorbell press — no alert."),
    ("🌙 Overnight motion", "scenario_overnight_motion", "Motion during quiet hours — should alert."),
    ("🎲 Random event", "random_event", "One random simulated event."),
]
=======
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
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
