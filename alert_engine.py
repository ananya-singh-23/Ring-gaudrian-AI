"""
alert_engine.py — Deterministic rule-based alert engine for Ring Guardian AI.

Rules are configurable thresholds, not a reliable intrusion-detection system.
All events processed here are SIMULATED.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

# ---------------------------------------------------------------------------
# Default configuration (can be overridden via data/config.json)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    # How long (minutes) a door can remain open before alerting
    "door_open_threshold_minutes": 5,
    # How many motion events within the window trigger a repeated-motion alert
    "motion_repeat_count": 3,
    # Time window (minutes) for the repeated-motion check
    "motion_repeat_window_minutes": 5,
    # Quiet hours: activity during this range triggers an unusual-hours alert
    "quiet_hours_start": 23,   # 11 PM (inclusive)
    "quiet_hours_end":   6,    # 6 AM  (exclusive)
}

CONFIG_FILE = Path(__file__).parent / "data" / "config.json"


def load_config() -> dict:
    """
    Load alert thresholds from data/config.json.
    Falls back to DEFAULT_CONFIG for any missing keys.
    """
    config = dict(DEFAULT_CONFIG)
    try:
        if CONFIG_FILE.exists():
            with CONFIG_FILE.open("r", encoding="utf-8") as f:
                user_config = json.load(f)
                config.update(user_config)
    except (json.JSONDecodeError, OSError):
        pass
    return config


def save_config(config: dict) -> None:
    """Persist updated config to data/config.json."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except OSError as exc:
        print(f"[alert_engine] Warning: could not save config — {exc}")


# ---------------------------------------------------------------------------
# Alert data structure
# ---------------------------------------------------------------------------

def make_alert(
    rule: str,
    severity: str,
    device_id: str,
    device_name: str,
    message: str,
    related_event_ids: list[str] | None = None,
) -> dict:
    """
    Create a structured alert dict.

    Args:
        rule:               Short rule identifier (e.g. 'door_open_too_long').
        severity:           'low' | 'medium' | 'high'.
        device_id:          Device that triggered the alert.
        device_name:        Human-readable device label.
        message:            Plain-English explanation of why the alert fired.
        related_event_ids:  IDs of the events that caused this alert.

    Returns:
        Alert dict with a generated_at timestamp.
    """
    return {
        "rule":               rule,
        "severity":           severity,
        "device_id":          device_id,
        "device_name":        device_name,
        "message":            message,
        "related_event_ids":  related_event_ids or [],
        "generated_at":       datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    }


# ---------------------------------------------------------------------------
# Individual rule implementations
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: str) -> datetime:
    """Parse an ISO-8601 timestamp string, stripping sub-second precision."""
    # Handle both '2024-01-01T12:00:00' and '2024-01-01T12:00:00.123456'
    return datetime.fromisoformat(ts_str[:19])


def check_door_open_too_long(events: list[dict], config: dict) -> list[dict]:
    """
    Rule: A door sensor that has been 'door_opened' for longer than
    door_open_threshold_minutes without a subsequent 'door_closed' event.

    Checks all door_sensor devices independently.
    """
    alerts = []
    threshold = timedelta(minutes=config["door_open_threshold_minutes"])
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Collect door-sensor events, grouped by device
    door_devices: dict[str, list[dict]] = {}
    for evt in events:
        if evt.get("device_type") == "door_sensor":
            door_devices.setdefault(evt["device_id"], []).append(evt)

    for device_id, device_events in door_devices.items():
        # Sort chronologically
        device_events.sort(key=lambda e: e["timestamp"])

        # Walk events; track whether the door is currently open
        open_event: dict | None = None
        for evt in device_events:
            if evt["event_type"] == "door_opened":
                open_event = evt
            elif evt["event_type"] == "door_closed":
                open_event = None  # Closed — reset

        # If the last state is 'opened', check elapsed time
        if open_event is not None:
            opened_at = _parse_ts(open_event["timestamp"])
            elapsed = now - opened_at
            if elapsed > threshold:
                minutes_open = int(elapsed.total_seconds() // 60)
                alerts.append(make_alert(
                    rule="door_open_too_long",
                    severity="medium",
                    device_id=device_id,
                    device_name=open_event["device_name"],
                    message=(
                        f"{open_event['device_name']} has been open for "
                        f"{minutes_open} minute(s) — threshold is "
                        f"{config['door_open_threshold_minutes']} minute(s). "
                        "Consider closing it or verifying the sensor."
                    ),
                    related_event_ids=[open_event["id"]],
                ))

    return alerts


def check_repeated_motion(events: list[dict], config: dict) -> list[dict]:
    """
    Rule: More than motion_repeat_count motion events from the same device
    within motion_repeat_window_minutes triggers an alert.
    """
    alerts = []
    window = timedelta(minutes=config["motion_repeat_window_minutes"])
    threshold_count = config["motion_repeat_count"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Only motion events
    motion_events = [e for e in events if e["event_type"] == "motion_detected"]

    # Group by device
    by_device: dict[str, list[dict]] = {}
    for evt in motion_events:
        by_device.setdefault(evt["device_id"], []).append(evt)

    for device_id, device_events in by_device.items():
        device_events.sort(key=lambda e: e["timestamp"])

        # Sliding-window scan
        for i, anchor in enumerate(device_events):
            anchor_ts = _parse_ts(anchor["timestamp"])
            # Only check windows that end within the look-back period
            if now - anchor_ts > timedelta(hours=24):
                continue
            window_end = anchor_ts + window
            cluster = [
                e for e in device_events[i:]
                if anchor_ts <= _parse_ts(e["timestamp"]) <= window_end
            ]
            if len(cluster) >= threshold_count:
                alerts.append(make_alert(
                    rule="repeated_motion",
                    severity="high",
                    device_id=device_id,
                    device_name=anchor["device_name"],
                    message=(
                        f"{anchor['device_name']} detected {len(cluster)} motion event(s) "
                        f"within {config['motion_repeat_window_minutes']} minute(s) "
                        f"(threshold: {threshold_count}). "
                        "This pattern may indicate repeated activity near the sensor."
                    ),
                    related_event_ids=[e["id"] for e in cluster],
                ))
                break  # One alert per device per analysis run

    return alerts


def check_quiet_hours(events: list[dict], config: dict) -> list[dict]:
    """
    Rule: Any activity during configured quiet hours generates an alert.

    Quiet hours span [quiet_hours_start, midnight) ∪ [midnight, quiet_hours_end).
    Example: start=23, end=6  →  11 PM to 5:59 AM.
    """
    alerts = []
    start_h: int = config["quiet_hours_start"]
    end_h: int   = config["quiet_hours_end"]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for evt in events:
        ts = _parse_ts(evt["timestamp"])

        # Only alert on events from the last 24 hours
        if now - ts > timedelta(hours=24):
            continue

        hour = ts.hour
        in_quiet = (
            (start_h > end_h and (hour >= start_h or hour < end_h))   # wraps midnight
            or (start_h < end_h and start_h <= hour < end_h)           # same day
        )

        if in_quiet:
            alerts.append(make_alert(
                rule="quiet_hours_activity",
                severity="medium",
                device_id=evt["device_id"],
                device_name=evt["device_name"],
                message=(
                    f"{evt['device_name']} recorded a '{evt['event_type']}' event "
                    f"at {ts.strftime('%H:%M')} UTC — inside quiet hours "
                    f"({start_h:02d}:00–{end_h:02d}:00 UTC). "
                    "Verify this was expected activity."
                ),
                related_event_ids=[evt["id"]],
            ))

    return alerts


# ---------------------------------------------------------------------------
# Master analysis function
# ---------------------------------------------------------------------------

def analyse_events(events: list[dict], config: dict | None = None) -> list[dict]:
    """
    Run all rules against *events* and return a combined, deduplicated alert list.

    Args:
        events: List of event dicts (from simulator.get_all_events()).
        config: Optional config override; loads from file if None.

    Returns:
        List of alert dicts, sorted newest-first.
    """
    if config is None:
        config = load_config()

    alerts: list[dict] = []
    alerts.extend(check_door_open_too_long(events, config))
    alerts.extend(check_repeated_motion(events, config))
    alerts.extend(check_quiet_hours(events, config))

    # Deduplicate: same rule + same device should only appear once
    seen: set[tuple] = set()
    unique_alerts: list[dict] = []
    for alert in alerts:
        key = (alert["rule"], alert["device_id"])
        if key not in seen:
            seen.add(key)
            unique_alerts.append(alert)

    # Newest first
    unique_alerts.sort(key=lambda a: a["generated_at"], reverse=True)
    return unique_alerts


# ---------------------------------------------------------------------------
# Severity helpers used by the UI
# ---------------------------------------------------------------------------

SEVERITY_EMOJI = {
    "high":   "🔴",
    "medium": "🟡",
    "low":    "🟢",
}

SEVERITY_COLOR = {
    "high":   "#FF4B4B",
    "medium": "#FFA500",
    "low":    "#00C853",
}
