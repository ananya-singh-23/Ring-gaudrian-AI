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
