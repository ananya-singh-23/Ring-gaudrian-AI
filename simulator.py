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
from event_schema import normalize_event


def make_event(device_id: str, device_name: str, event_type: str,
               timestamp: Optional[datetime] = None, details: str = "") -> Dict[str, Any]:
    """Build a single simulated event dictionary.

    Raises ``ValueError`` if an unknown event type is requested, which
    helps catch typos during development.
    """
    if event_type not in EVENT_TYPE_META:
        raise ValueError(f"Unknown event type: {event_type!r}")
    return normalize_event({
        "id": uuid.uuid4().hex[:8],
        "source": "simulated",
        "timestamp": (timestamp or datetime.now()).isoformat(),
        "device_id": device_id,
        "device_name": device_name,
        "event_type": event_type,
        "details": details or "",
        "attributes": {"details": details or ""},
        "simulated": True,
    })


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
