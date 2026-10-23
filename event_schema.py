"""Canonical event normalization shared by simulations and Ring webhook input."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Mapping

from utils import parse_ts

VALID_SOURCES = {"simulated", "ring"}
REQUIRED_FIELDS = ("id", "source", "device_id", "device_name", "event_type", "timestamp", "attributes")


def normalize_event(event: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a validated canonical event while preserving legacy display fields."""
    event_id = event.get("id")
    device_id = event.get("device_id")
    device_name = event.get("device_name")
    event_type = event.get("event_type")
    source = event.get("source", "simulated" if event.get("simulated", True) else "ring")
    timestamp = event.get("timestamp")
    if isinstance(timestamp, (int, float)):
        timestamp = datetime.fromtimestamp(timestamp / 1000).isoformat()
    parsed = parse_ts(timestamp)
    if not all((event_id, device_id, device_name, event_type)):
        raise ValueError("Event requires id, device_id, device_name, and event_type")
    if source not in VALID_SOURCES:
        raise ValueError(f"Unsupported event source: {source!r}")
    if parsed is None:
        raise ValueError("Event timestamp must be a valid ISO-8601 timestamp")
    attributes = dict(event.get("attributes") or {})
    details = str(event.get("details", attributes.get("details", "")))
    attributes.setdefault("details", details)
    normalized = dict(event)
    normalized.update({
        "id": str(event_id),
        "source": source,
        "device_id": str(device_id),
        "device_name": str(device_name),
        "event_type": str(event_type),
        "timestamp": parsed.isoformat(),
        "attributes": attributes,
        "details": details,
        "simulated": source == "simulated",
    })
    return normalized


def validate_event(event: Mapping[str, Any]) -> bool:
    """Return True when an event conforms to the normalized schema."""
    try:
        normalized = normalize_event(event)
    except (TypeError, ValueError):
        return False
    return all(key in normalized for key in REQUIRED_FIELDS)


def ring_webhook_to_event(payload: Mapping[str, Any], device_name: str) -> Dict[str, Any]:
    """Map documented Ring device notifications to the local canonical event shape."""
    data = payload.get("data") or {}
    meta = payload.get("meta") or {}
    attrs = data.get("attributes") or {}
    event_type = data.get("type")
    device_id = attrs.get("source")
    if not event_type or not device_id or not data.get("id"):
        raise ValueError("Webhook event is missing documented event/device identifiers")
    timestamp = attrs.get("timestamp") or meta.get("time")
    if timestamp is None:
        raise ValueError("Webhook event is missing its timestamp")
    event_attributes = dict(attrs)
    if data.get("subType") is not None:
        event_attributes["subType"] = data["subType"]
    event_attributes.update({
        "request_id": meta.get("request_id"),
        "ring_event_id": data["id"],
    })
    return normalize_event({
        "id": str(data["id"]),
        "source": "ring",
        "device_id": str(device_id),
        "device_name": device_name,
        "event_type": str(event_type),
        "timestamp": timestamp,
        "attributes": event_attributes,
        "details": f"Verified Ring event: {event_type}",
        "simulated": False,
    })
