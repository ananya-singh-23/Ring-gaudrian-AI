<<<<<<< HEAD
"""Local, deterministic chat assistant for Ring Guardian AI.

The assistant answers questions about simulated device states and event
history using the application's real in-memory data. It performs keyword
routing only — there is no external LLM and no AWS service contacted.

The logic lives behind a small, pluggable ``AssistantBackend`` interface
so a future Strands Agents SDK implementation backed by Amazon Bedrock can
be dropped in (see ``build_assistant``) without changing any call site.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils import (
    parse_ts, time_ago, EVENT_TYPE_META, compute_device_states,
)

# Keyword aliases used to detect which device a question refers to.
DEVICE_KEYWORDS: Dict[str, List[str]] = {
    "front_door": ["front door"],
    "doorbell": ["doorbell", "door bell"],
    "garage_door": ["garage"],
    "motion_sensor": ["motion sensor"],
}

DEVICE_ID_BY_NAME = {
    "front_door": "Front Door",
    "doorbell": "Doorbell",
    "garage_door": "Garage Door",
    "motion_sensor": "Motion Sensor",
}


# --- Pluggable backend interface -----------------------------------------


@dataclass
class AssistantContext:
    """A snapshot of the data the assistant is allowed to answer from.

    Backends must ground every answer in these records and must not invent
    events or claim to use an external LLM.
    """
    events: List[Dict[str, Any]]
    devices: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]] = field(default_factory=list)
    config: Optional[Dict[str, Any]] = None


class AssistantBackend(ABC):
    """Abstract assistant interface shared by every backend."""

    @abstractmethod
    def answer(self, question: str, context: AssistantContext) -> str:
        """Return a plain-text answer grounded in ``context``."""


class LocalAssistant(AssistantBackend):
    """Deterministic, offline assistant backed by the app's real records."""

    def answer(self, question: str, context: AssistantContext) -> str:
        return _route(question, context.events, context.devices,
                      context.alerts, context.config)


def build_assistant() -> AssistantBackend:
    """Factory returning the active assistant backend.

    Today this returns the local deterministic backend. To add a
    Strands Agents SDK + Amazon Bedrock backend later, implement
    ``AssistantBackend`` and return it here (e.g. gated on an environment
    variable). No call site needs to change.
    """
    return LocalAssistant()


def answer(question: str,
           events: List[Dict[str, Any]],
           devices: List[Dict[str, Any]],
           alerts: List[Dict[str, Any]],
           config: Optional[Dict[str, Any]] = None) -> str:
    """Backward-compatible entry point used by app.py and existing tests."""
    return LocalAssistant().answer(question, AssistantContext(events, devices, alerts, config))


def _route(question: str,
           events: List[Dict[str, Any]],
           devices: List[Dict[str, Any]],
           alerts: List[Dict[str, Any]],
           config: Optional[Dict[str, Any]] = None) -> str:
    """Keyword-routing answer grounded only in the supplied records."""
    q = (question or "").lower().strip()
    if not q:
        return _help()

    if q in ("hi", "hello", "hey", "yo", "sup", "help me"):
        return ("Hi! I'm the Ring Guardian AI assistant (local, simulated data only). "
                "I can tell you about device status, event counts, recent activity, and alerts. "
                "Type 'help' to see examples.")

    if q in ("help", "?", "what can you do", "what can you do?"):
        return _help()

    # Alerts-related questions.
    if "alert" in q:
        return _describe_alerts(alerts, q)

    # "How many" / count questions.
    if ("how many" in q or "count" in q or "number of" in q or "total" in q):
        return _counts(events, devices, alerts, q)

    # Per-device questions (check before generic event-type filters).
    device_id = _match_device(q)
    if device_id:
        return _about_device(events, devices, alerts, device_id, q)

    # Status overview.
    if "status" in q or "state" in q or "devices" in q:
        return _status_overview(events, devices)

    # Recent / last event.
    if any(k in q for k in ("recent", "latest", "last", "history", "what happened", "timeline")):
        return _recent_events(events)

    # Event-type filters.
    if "motion" in q:
        return _by_event_type(events, "motion_detected", "motion")
    if "doorbell" in q:
        return _by_event_type(events, "doorbell_press", "doorbell")
    if "door open" in q:
        return _by_event_type(events, "door_open", "door open")
    if "door close" in q or "closed" in q:
        return _by_event_type(events, "door_close", "door close")

    # Quiet hours config question.
    if "quiet" in q:
        return _quiet_hours(config or {})

    # Today.
    if "today" in q:
        return _today_events(events)

    return ("I'm not sure how to answer that yet. Try asking about: device status, "
            "how many events today, recent activity, or current alerts. Type 'help' for examples.")


# --- Intent handlers ------------------------------------------------------


def _help() -> str:
    lines = [
        "I can answer questions about your SIMULATED Ring Guardian AI data. Examples:",
        "• \"What's the status of my devices?\"",
        "• \"Is the front door open?\"",
        "• \"How many events today?\"",
        "• \"Show recent activity\"",
        "• \"Any alerts?\"",
        "• \"How many alerts?\"",
        "• \"What are the quiet hours?\"",
        "",
        "Note: I'm a local deterministic assistant — no external AI service is connected.",
    ]
    return "\n".join(lines)


def _match_device(q: str) -> Optional[str]:
    """Return the device id mentioned in the question, if any."""
    for did, keywords in DEVICE_KEYWORDS.items():
        for kw in keywords:
            if kw in q:
                return did
    return None


def _status_overview(events: List[Dict[str, Any]], devices: List[Dict[str, Any]]) -> str:
    states = compute_device_states(events, devices)
    lines = ["Here's the current status of your simulated devices:"]
    for d in devices:
        s = states.get(d["id"])
        if not s:
            continue
        last = time_ago(s["last_event_ts"])
        lines.append(f"• {d['icon']} {d['name']}: {s['status']} {s['status_emoji']} "
                     f"(last event: {s['last_event_label']} {last}; {s['events_today']} today)")
    return "\n".join(lines)


def _about_device(events: List[Dict[str, Any]], devices: List[Dict[str, Any]],
                  alerts: List[Dict[str, Any]], device_id: str, q: str) -> str:
    device_name = DEVICE_ID_BY_NAME.get(device_id, device_id)
    dev_events = sorted([e for e in events if e.get("device_id") == device_id],
                        key=lambda e: e.get("timestamp", ""), reverse=True)
    states = compute_device_states(events, devices)
    s = states.get(device_id)

    if "open" in q and any(k in q for k in ("is", "open")):
        if device_id == "front_door" or device_id == "garage_door":
            if s and s["status"] == "Open":
                return f"Yes — {device_name} is currently Open 🔴 (last opened {time_ago(s['last_event_ts'])})."
            return f"No — {device_name} is currently Closed 🟢."

    if not dev_events:
        return f"{device_name} has no recorded events yet."

    today = sum(1 for e in dev_events
                if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == _today_date())
    last = dev_events[0]
    label = EVENT_TYPE_META.get(last["event_type"], {}).get("label", last["event_type"])
    parts = [
        f"{device_name} status: {s['status']} {s['status_emoji']}",
        f"Last event: {label} {time_ago(parse_ts(last.get('timestamp')))}",
        f"Total events: {len(dev_events)} ({today} today)",
        "Recent events:",
    ]
    for e in dev_events[:5]:
        lbl = EVENT_TYPE_META.get(e["event_type"], {}).get("label", e["event_type"])
        ts = parse_ts(e.get("timestamp"))
        parts.append(f"  - {ts.strftime('%H:%M:%S') if ts else '?'} {lbl}: {e.get('details','')}")
    return "\n".join(parts)


def _counts(events: List[Dict[str, Any]], devices: List[Dict[str, Any]],
            alerts: List[Dict[str, Any]], q: str) -> str:
    today = sum(1 for e in events
                if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == _today_date())
    if "alert" in q:
        sev = {}
        for a in alerts:
            sev[a["severity"]] = sev.get(a["severity"], 0) + 1
        detail = ", ".join(f"{k}: {v}" for k, v in sev.items()) or "none"
        return f"There are {len(alerts)} alert(s) right now ({detail})."
    if "device" in q:
        return f"There are {len(devices)} connected simulated devices."
    return (f"Total events: {len(events)}. Events today: {today}. "
            f"Connected devices: {len(devices)}. Alerts: {len(alerts)}.")


def _recent_events(events: List[Dict[str, Any]]) -> str:
    ordered = sorted(events, key=lambda e: e.get("timestamp", ""), reverse=True)
    if not ordered:
        return "There are no events yet. Use the simulator panel to generate some."
    lines = [f"Showing the {min(8, len(ordered))} most recent events:"]
    for e in ordered[:8]:
        lbl = EVENT_TYPE_META.get(e["event_type"], {}).get("label", e["event_type"])
        ts = parse_ts(e.get("timestamp"))
        when = ts.strftime("%Y-%m-%d %H:%M:%S") if ts else "?"
        lines.append(f"• {when} — {e['device_name']} — {lbl}: {e.get('details','')}")
    return "\n".join(lines)


def _by_event_type(events: List[Dict[str, Any]], event_type: str, label: str) -> str:
    filtered = sorted([e for e in events if e.get("event_type") == event_type],
                      key=lambda e: e.get("timestamp", ""), reverse=True)
    if not filtered:
        return f"No {label} events recorded yet."
    today = sum(1 for e in filtered
                if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == _today_date())
    lines = [f"There are {len(filtered)} {label} event(s) ({today} today). Most recent:"]
    for e in filtered[:5]:
        ts = parse_ts(e.get("timestamp"))
        when = ts.strftime("%H:%M:%S") if ts else "?"
        lines.append(f"• {when} — {e['device_name']}: {e.get('details','')}")
    return "\n".join(lines)


def _today_events(events: List[Dict[str, Any]]) -> str:
    today_list = [e for e in events
                  if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == _today_date()]
    if not today_list:
        return "No events recorded today so far."
    lines = [f"There are {len(today_list)} event(s) today:"]
    for e in sorted(today_list, key=lambda e: e.get("timestamp", ""), reverse=True)[:8]:
        lbl = EVENT_TYPE_META.get(e["event_type"], {}).get("label", e["event_type"])
        ts = parse_ts(e.get("timestamp"))
        when = ts.strftime("%H:%M:%S") if ts else "?"
        lines.append(f"• {when} — {e['device_name']} — {lbl}")
    return "\n".join(lines)


def _describe_alerts(alerts: List[Dict[str, Any]], q: str) -> str:
    if not alerts:
        return "No active alerts right now. Everything looks normal."
    lines = [f"There are {len(alerts)} active alert(s):"]
    for a in alerts[:8]:
        emoji = {"critical": "🔴", "warning": "🟠", "info": "🔵"}.get(a["severity"], "⚪")
        lines.append(f"{emoji} [{a['severity'].upper()}] {a['message']}")
    if len(alerts) > 8:
        lines.append(f"...and {len(alerts) - 8} more. See the dashboard for the full list.")
    return "\n".join(lines)


def _quiet_hours(config: Dict[str, Any]) -> str:
    qh = config.get("quiet_hours", {})
    start = qh.get("start", "—")
    end = qh.get("end", "—")
    rules = config.get("rules", {})
    return (f"Quiet hours are {start} to {end}. Rules: door open threshold "
            f"{rules.get('door_open_threshold_minutes',5)} min; motion burst > "
            f"{rules.get('motion_burst_threshold',3)} events in "
            f"{rules.get('motion_burst_window_seconds',60)}s.")


def _today_date():
    from datetime import date
    return date.today()
=======
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
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
