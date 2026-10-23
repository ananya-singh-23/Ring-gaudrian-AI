<<<<<<< HEAD
"""Deterministic alert rules for simulated events.

These rules are simple, configurable heuristics intended to demonstrate
the alert pipeline for a hackathon. They are NOT a reliable intrusion
detection system and must not be treated as one.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List

from utils import parse_ts, in_quiet_hours, EVENT_TYPE_META

# Display order for alert severity (highest first).
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
SEVERITY_EMOJI = {"critical": "🔴", "warning": "🟠", "info": "🔵"}


def _alert(alert_type: str, severity: str, event: Dict[str, Any],
           message: str, **extra: Any) -> Dict[str, Any]:
    """Build a single alert dictionary tied to the triggering event.

    ``extra`` is merged into the alert so each rule can attach structured,
    machine-readable context (e.g. ``opened_at``, ``duration_min``) alongside
    the human-readable ``message``. Every message must include a timestamp
    and a clear, plain-language reason.
    """
    return {
        "id": uuid.uuid4().hex[:8],
        "type": alert_type,
        "severity": severity,
        "device_id": event.get("device_id"),
        "device_name": event.get("device_name"),
        "message": message,
        # Timestamp of the triggering event (kept for sorting/display).
        "timestamp": event.get("timestamp"),
        "event_id": event.get("id"),
        **extra,
    }


def evaluate(events: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run every configured rule against the event history.

    Returns a list of alerts sorted by severity (most severe first),
    then by timestamp (most recent first).
    """
    ordered = sorted(events, key=lambda e: e.get("timestamp", ""))
    rules = config.get("rules", {})
    quiet = config.get("quiet_hours", {})

    alerts: List[Dict[str, Any]] = []
    alerts += _check_doors_open(ordered, rules)
    alerts += _check_motion_burst(ordered, rules)
    alerts += _check_quiet_hours(ordered, quiet)

    alerts.sort(key=lambda a: (SEVERITY_ORDER.get(a["severity"], 9),
                               a.get("timestamp", "")))
    return alerts


def _check_doors_open(events: List[Dict[str, Any]], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flag doors open longer than the configured threshold.

    A door_open event with no later door_close is treated as "still open"
    (critical). A door_open that is eventually closed after the threshold
    is a warning.
    """
    threshold_min = rules.get("door_open_threshold_minutes", 5)
    alerts: List[Dict[str, Any]] = []

    # Collect close timestamps per device for quick lookup.
    closes: Dict[str, List[datetime]] = {}
    for e in events:
        if e["event_type"] == "door_close":
            ts = parse_ts(e.get("timestamp"))
            if ts:
                closes.setdefault(e["device_id"], []).append(ts)
    for cid in closes:
        closes[cid].sort()

    now = datetime.now()
    for e in events:
        if e["event_type"] != "door_open":
            continue
        open_ts = parse_ts(e.get("timestamp"))
        if not open_ts:
            continue
        later_closes = [c for c in closes.get(e["device_id"], []) if c >= open_ts]
        if later_closes:
            close_ts = later_closes[0]
            duration_min = (close_ts - open_ts).total_seconds() / 60.0
            if duration_min > threshold_min:
                alerts.append(_alert(
                    "door_open_too_long", "warning", e,
                    f"{e['device_name']} was opened at {open_ts.strftime('%H:%M')} on "
                    f"{open_ts.strftime('%Y-%m-%d')} and stayed open for {duration_min:.1f} min "
                    f"until closed at {close_ts.strftime('%H:%M')} — exceeding the "
                    f"{threshold_min}-min threshold.",
                    opened_at=open_ts.isoformat(),
                    closed_at=close_ts.isoformat(),
                    duration_min=round(duration_min, 2),
                    threshold_min=threshold_min,
                ))
        else:
            open_for = (now - open_ts).total_seconds() / 60.0
            if open_for > threshold_min:
                alerts.append(_alert(
                    "door_open_too_long", "critical", e,
                    f"{e['device_name']} was opened at {open_ts.strftime('%H:%M')} on "
                    f"{open_ts.strftime('%Y-%m-%d')} and has been open for {open_for:.1f} min "
                    f"(threshold {threshold_min} min) — the door is still open.",
                    opened_at=open_ts.isoformat(),
                    duration_min=round(open_for, 2),
                    threshold_min=threshold_min,
                    still_open=True,
                ))
    return alerts


def _check_motion_burst(events: List[Dict[str, Any]], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flag repeated motion events within a short sliding window."""
    window_sec = rules.get("motion_burst_window_seconds", 60)
    threshold = rules.get("motion_burst_threshold", 3)
    alerts: List[Dict[str, Any]] = []

    motion = [e for e in events if e["event_type"] == "motion_detected"]
    covered: set = set()  # event ids already counted in a reported burst
    for i, e in enumerate(motion):
        if e["id"] in covered:
            continue
        ts = parse_ts(e.get("timestamp"))
        if not ts:
            continue
        burst = [m for m in motion[i:]
                 if parse_ts(m.get("timestamp"))
                 and (parse_ts(m["timestamp"]) - ts).total_seconds() <= window_sec]
        if len(burst) >= threshold:
            for m in burst:
                covered.add(m["id"])
            last_ts = parse_ts(burst[-1].get("timestamp")) or ts
            alerts.append(_alert(
                "repeated_motion", "warning", e,
                f"{len(burst)} motion events from {e['device_name']} between "
                f"{ts.strftime('%H:%M:%S')} and {last_ts.strftime('%H:%M:%S')} on "
                f"{ts.strftime('%Y-%m-%d')} — {len(burst)} events within {window_sec}s "
                f"(threshold {threshold}). Possible repeated movement.",
                count=len(burst),
                first_at=ts.isoformat(),
                last_at=last_ts.isoformat(),
                window_sec=window_sec,
                threshold=threshold,
            ))
    return alerts


def _check_quiet_hours(events: List[Dict[str, Any]], quiet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flag any activity that occurs inside the configured quiet window."""
    start = quiet.get("start", "01:00")
    end = quiet.get("end", "05:00")
    if not start or not end or start == end:
        return []
    alerts: List[Dict[str, Any]] = []
    for e in events:
        ts = parse_ts(e.get("timestamp"))
        if not ts or not in_quiet_hours(ts, start, end):
            continue
        label = EVENT_TYPE_META.get(e["event_type"], {}).get("label", e["event_type"])
        alerts.append(_alert(
            "quiet_hours_activity", "info", e,
            f"{e['device_name']} ({label}) activity at {ts.strftime('%H:%M')} on "
            f"{ts.strftime('%Y-%m-%d')} — this falls inside the configured quiet "
            f"hours window ({start}-{end}).",
            occurred_at=ts.isoformat(),
            quiet_start=start,
            quiet_end=end,
        ))
    return alerts
=======
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
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
