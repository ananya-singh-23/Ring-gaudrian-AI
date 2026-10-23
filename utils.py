"""Small shared helpers with no third-party dependencies.

Keeping these dependency-free means the unit tests for the simulator,
alert engine, and assistant can import this module without pulling in
Streamlit.

IMPORTANT: All devices and events handled by this app are SIMULATED.
The application does not connect to real Ring hardware.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Optional, Sequence

# Human-readable labels and emojis for each simulated event type.
EVENT_TYPE_META: Dict[str, Dict[str, str]] = {
    "door_open": {"label": "Door Opened", "emoji": "🔓"},
    "door_close": {"label": "Door Closed", "emoji": "🔒"},
    "motion_detected": {"label": "Motion Detected", "emoji": "📡"},
    "doorbell_press": {"label": "Doorbell Press", "emoji": "🔔"},
}

# Convenience mapping from a device type to the event types it can emit.
DEVICE_EVENT_TYPES: Dict[str, List[str]] = {
    "door": ["door_open", "door_close"],
    "doorbell": ["doorbell_press"],
    "motion_sensor": ["motion_detected"],
}


def parse_ts(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp string into a naive ``datetime``.

    Events are stored as naive local time to keep the single-machine
    hackathon app simple. A trailing ``Z`` (UTC marker) is stripped
    before parsing. Returns ``None`` if the value cannot be parsed.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1]
    try:
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def time_ago(dt: Optional[datetime]) -> str:
    """Return a friendly relative-time string such as '5m ago'."""
    if dt is None:
        return "never"
    delta = datetime.now() - dt
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 60:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def in_quiet_hours(dt: Optional[datetime], start_str: str, end_str: str) -> bool:
    """Return True if ``dt`` falls within the configured quiet window.

    Supports windows that cross midnight (e.g. 23:00 -> 06:00). An empty
    or identical start/end is treated as "no quiet hours".
    """
    if dt is None or not start_str or not end_str or start_str == end_str:
        return False
    try:
        t = dt.time()
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
    except (ValueError, TypeError):
        return False
    if start < end:
        return start <= t < end
    # Crosses midnight.
    return t >= start or t < end


def _state_obj(device: Dict[str, Any], status: str, emoji: str,
               last_ts: Optional[datetime], events_today: int,
               last_event_type: Optional[str]) -> Dict[str, Any]:
    return {
        "device": device,
        "status": status,
        "status_emoji": emoji,
        "last_event_ts": last_ts,
        "events_today": events_today,
        "last_event_type": last_event_type,
        "last_event_label": EVENT_TYPE_META.get(last_event_type or "", {}).get("label", "—"),
    }


def compute_device_states(events: List[Dict[str, Any]],
                           devices: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Derive the current state of each simulated device from event history.

    - Doors: "Open" if the most recent event is a door_open, else "Closed".
    - Doorbell: "Ringing" if pressed within the last 5 minutes, else "Idle".
    - Motion sensor: "Motion" if motion was detected within 3 minutes,
      otherwise "Idle".
    """
    now = datetime.now()
    states: Dict[str, Dict[str, Any]] = {}
    for device in devices:
        did = device["id"]
        dev_events = [e for e in events if e.get("device_id") == did]
        if not dev_events:
            states[did] = _state_obj(device, "Idle", "⚪", None, 0, None)
            continue

        # Most recent event wins (fall back to min if a timestamp is bad).
        last = max(dev_events, key=lambda e: parse_ts(e.get("timestamp")) or datetime.min)
        last_ts = parse_ts(last.get("timestamp"))
        events_today = sum(
            1 for e in dev_events
            if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == now.date()
        )

        dtype = device.get("type")
        if dtype == "door":
            if last["event_type"] == "door_open":
                status, emoji = "Open", "🔴"
            else:
                status, emoji = "Closed", "🟢"
        elif dtype == "doorbell":
            recent = last_ts is not None and (now - last_ts).total_seconds() < 300
            status, emoji = ("Ringing", "🔔") if recent else ("Idle", "⚪")
        elif dtype == "motion_sensor":
            recent = (last["event_type"] == "motion_detected"
                      and last_ts is not None
                      and (now - last_ts).total_seconds() < 180)
            status, emoji = ("Motion", "🟡") if recent else ("Idle", "⚪")
        else:
            status, emoji = "Idle", "⚪"

        states[did] = _state_obj(device, status, emoji, last_ts, events_today, last["event_type"])
    return states


def status_class(status: str) -> str:
    """Map a status label to a CSS class name for card styling."""
    mapping = {
        "Open": "status-open",
        "Closed": "status-closed",
        "Motion": "status-motion",
        "Ringing": "status-motion",
        "Idle": "status-idle",
    }
    return mapping.get(status, "status-idle")


def filter_events(events: List[Dict[str, Any]],
                  device_names: Optional[Sequence[str]] = None,
                  event_types: Optional[Sequence[str]] = None,
                  date_range: str = "All time",
                  now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Return the subset of events matching ALL of the given filters.

    This is the single place that defines the event-explorer filtering so the
    dashboard and tests stay in sync. A ``None``/empty ``device_names`` or
    ``event_types`` means "no filter on that axis". ``date_range`` is one of
    ``"All time"`` (default), ``"Today"``, or ``"Last 7 days"``.

    ``now`` may be injected for deterministic tests.
    """
    now = now or datetime.now()
    result = list(events)

    if device_names:
        names = set(device_names)
        result = [e for e in result if e.get("device_name") in names]
    if event_types:
        types = set(event_types)
        result = [e for e in result if e.get("event_type") in types]
    if date_range == "Today":
        today = now.date()
        result = [e for e in result
                  if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == today]
    elif date_range == "Last 7 days":
        cutoff = now - timedelta(days=7)
        result = [e for e in result
                  if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]) >= cutoff]
    # "All time" (or any unrecognized value) applies no date filter.
    return result
