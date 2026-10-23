"""
assistant.py — Deterministic local chat assistant for Ring Guardian AI.

IMPORTANT: This assistant runs entirely on the local machine using rule-based
pattern matching. It is NOT connected to any external LLM, AWS Bedrock, or
any other cloud service. All responses are derived from the application's
own event and alert data.

A future phase will integrate Strands Agents SDK + Amazon Bedrock.
"""

import re
from datetime import datetime, timedelta, timezone

from simulator import get_all_events, get_device_status, DEVICES
from alert_engine import analyse_events, load_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str[:19])


def _count_today(events: list[dict]) -> int:
    """Return number of events that occurred in the last 24 hours."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    return sum(1 for e in events if _parse_ts(e["timestamp"]) >= cutoff)


def _recent_events(events: list[dict], n: int = 5) -> list[dict]:
    """Return the n most-recent events."""
    return sorted(events, key=lambda e: e["timestamp"], reverse=True)[:n]


def _format_ts(ts_str: str) -> str:
    try:
        dt = _parse_ts(ts_str)
        return dt.strftime("%b %d %H:%M UTC")
    except ValueError:
        return ts_str


def _device_name_to_id(query: str) -> str | None:
    """Fuzzy-match a device name from a query string. Returns device_id or None."""
    query_lower = query.lower()
    for device in DEVICES:
        if device["name"].lower() in query_lower or device["id"].replace("_", " ") in query_lower:
            return device["id"]
    # Partial matches
    for device in DEVICES:
        parts = device["name"].lower().split()
        if any(part in query_lower for part in parts):
            return device["id"]
    return None


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _resp_status_all(status_map: dict) -> str:
    lines = ["**Device Status (Simulated)**\n"]
    for did, info in status_map.items():
        icon = {"open": "🔓", "closed": "🔒", "idle": "💤", "unknown": "❓"}.get(info["status"], "❓")
        last = f"Last seen: {_format_ts(info['last_seen'])}" if info["last_seen"] else "No events recorded"
        lines.append(f"{icon} **{info['name']}** — {info['status'].capitalize()}  \n  {last}")
    return "\n\n".join(lines)


def _resp_device_status(device_id: str, status_map: dict) -> str:
    info = status_map.get(device_id)
    if not info:
        return "I couldn't find that device. Try asking about Front Door, Doorbell, Garage Door, or Motion Sensor."
    icon = {"open": "🔓", "closed": "🔒", "idle": "💤", "unknown": "❓"}.get(info["status"], "❓")
    last = f"Last event: **{info['last_event']}** at {_format_ts(info['last_seen'])}" if info["last_seen"] else "No events recorded yet."
    return (
        f"{icon} **{info['name']}** is currently **{info['status']}**.\n\n"
        f"{last}"
    )


def _resp_recent_events(events: list[dict], n: int = 5) -> str:
    recent = _recent_events(events, n)
    if not recent:
        return "No events have been recorded yet. Try running a scenario from the Event Simulator tab."
    lines = [f"**{n} Most Recent Events (Simulated)**\n"]
    for e in recent:
        lines.append(
            f"• `{_format_ts(e['timestamp'])}` — **{e['device_name']}** → {e['event_type'].replace('_', ' ').title()}"
        )
    return "\n".join(lines)


def _resp_event_count(events: list[dict]) -> str:
    total = len(events)
    today = _count_today(events)
    return (
        f"There are **{total}** total simulated events on record.\n"
        f"**{today}** of those occurred in the last 24 hours."
    )


def _resp_alerts(alerts: list[dict]) -> str:
    if not alerts:
        return "✅ No active alerts. Everything looks normal based on the current rules."
    lines = [f"**{len(alerts)} Active Alert(s)**\n"]
    emoji_map = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    for a in alerts:
        em = emoji_map.get(a["severity"], "⚪")
        lines.append(f"{em} **{a['device_name']}** [{a['severity'].upper()}]\n  {a['message']}")
    return "\n\n".join(lines)


def _resp_device_events(device_id: str, events: list[dict], n: int = 5) -> str:
    device_events = [e for e in events if e["device_id"] == device_id]
    if not device_events:
        did_info = next((d for d in DEVICES if d["id"] == device_id), None)
        name = did_info["name"] if did_info else device_id
        return f"No events found for **{name}**."
    recent = sorted(device_events, key=lambda e: e["timestamp"], reverse=True)[:n]
    did_info = next((d for d in DEVICES if d["id"] == device_id), None)
    name = did_info["name"] if did_info else device_id
    lines = [f"**Last {min(n, len(recent))} events for {name}**\n"]
    for e in recent:
        lines.append(f"• `{_format_ts(e['timestamp'])}` → {e['event_type'].replace('_', ' ').title()}")
    return "\n".join(lines)


def _resp_help() -> str:
    return (
        "**Ring Guardian AI Assistant** *(Local / Simulated)*\n\n"
        "I can answer questions about your simulated devices and events. Try:\n\n"
        "- *What is the status of the front door?*\n"
        "- *Show me recent events*\n"
        "- *Are there any alerts?*\n"
        "- *How many events today?*\n"
        "- *What happened at the garage door?*\n"
        "- *Is the motion sensor active?*\n"
        "- *Show all device statuses*\n\n"
        "⚠️ This assistant uses local rule-based matching only — it is not connected to any AI or cloud service."
    )


def _resp_quiet_hours(config: dict) -> str:
    return (
        f"Quiet hours are configured from **{config['quiet_hours_start']:02d}:00** to "
        f"**{config['quiet_hours_end']:02d}:00 UTC**. "
        "Any activity during that window will trigger a quiet-hours alert."
    )


def _resp_unknown() -> str:
    return (
        "I'm not sure how to answer that with the current event data. "
        "Try asking about device status, recent events, or active alerts. "
        "Type **help** for a list of things I can answer."
    )


# ---------------------------------------------------------------------------
# Pattern → intent mapping
# ---------------------------------------------------------------------------

# Each entry: (compiled_regex, intent_label)
_INTENT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bhelp\b|\bwhat can you\b|\bcommands\b", re.I), "help"),
    (re.compile(r"\ball (devices?|status|sensors?)\b|\bdevice status\b|\bstatus of all\b", re.I), "all_status"),
    (re.compile(r"\b(is|what is|check)\b.*(door|doorbell|sensor|garage|motion)\b.*(status|state|open|closed)\b", re.I), "device_status"),
    (re.compile(r"\b(status|state|is|check)\b.*(front door|garage|doorbell|motion sensor)\b", re.I), "device_status"),
    (re.compile(r"\b(front door|garage door|doorbell|motion sensor)\b.*(status|open|closed|active|idle)\b", re.I), "device_status"),
    (re.compile(r"\b(latest|recent|last)\b.*(events?|activity|alerts?)\b", re.I), "recent_events"),
    (re.compile(r"\bshow\b.*(events?|activity)\b", re.I), "recent_events"),
    (re.compile(r"\bhow many\b.*(events?|times)\b", re.I), "event_count"),
    (re.compile(r"\b(events? today|today.{0,10}events?)\b", re.I), "event_count"),
    (re.compile(r"\balerts?\b|\bwarnings?\b|\bissues?\b", re.I), "alerts"),
    (re.compile(r"\bquiet hours?\b|\bunusual hours?\b", re.I), "quiet_hours"),
    (re.compile(r"\b(what happened|history|events?)\b.*(front door|garage|doorbell|motion sensor)\b", re.I), "device_events"),
    (re.compile(r"\b(front door|garage door|doorbell|motion sensor)\b.*(events?|history|activity)\b", re.I), "device_events"),
    # Bare device mentions → device status
    (re.compile(r"\b(front door|garage door|doorbell|motion sensor)\b", re.I), "device_status"),
]


def _classify(query: str) -> str:
    """Return an intent label for the user's query."""
    for pattern, intent in _INTENT_PATTERNS:
        if pattern.search(query):
            return intent
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chat(user_message: str) -> str:
    """
    Process a natural-language query and return a plain-text / markdown response.

    All answers are derived from live event and alert data — no external service
    is called.

    Args:
        user_message: The user's chat input.

    Returns:
        A markdown-formatted response string.
    """
    query = user_message.strip()
    if not query:
        return "Please type a question. Type **help** to see what I can answer."

    events = get_all_events()
    status_map = get_device_status(events)
    config = load_config()
    alerts = analyse_events(events, config)

    intent = _classify(query)

    if intent == "help":
        return _resp_help()

    elif intent == "all_status":
        return _resp_status_all(status_map)

    elif intent == "device_status":
        device_id = _device_name_to_id(query)
        if device_id:
            return _resp_device_status(device_id, status_map)
        return _resp_status_all(status_map)

    elif intent == "recent_events":
        return _resp_recent_events(events)

    elif intent == "event_count":
        return _resp_event_count(events)

    elif intent == "alerts":
        return _resp_alerts(alerts)

    elif intent == "quiet_hours":
        return _resp_quiet_hours(config)

    elif intent == "device_events":
        device_id = _device_name_to_id(query)
        if device_id:
            return _resp_device_events(device_id, events)
        return _resp_recent_events(events)

    else:
        return _resp_unknown()
