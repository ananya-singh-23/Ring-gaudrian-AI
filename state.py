"""Shared application state and JSON persistence helpers.

This module is the single source of truth for the dashboard's data.
Devices and rule configuration live in JSON files under ``data/``. Events
are kept in Streamlit's session state and persisted to ``data/events.json``
so they survive page reloads.

Everything here is SIMULATED — the app never contacts real Ring hardware.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DEVICES_FILE = DATA_DIR / "devices.json"
CONFIG_FILE = DATA_DIR / "config.json"
EVENTS_FILE = DATA_DIR / "events.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "quiet_hours": {"start": "01:00", "end": "05:00"},
    "rules": {
        "door_open_threshold_minutes": 5,
        "motion_burst_window_seconds": 60,
        "motion_burst_threshold": 3,
    },
}


# --- Low-level JSON IO ----------------------------------------------------


def _load_json(path: Path, fallback: Any) -> Any:
    """Load JSON from a file, returning fallback if missing or invalid."""
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        # Keep the app running even if a data file is corrupt.
        print(f"[state] Could not load {path.name}: {exc}")
    return fallback


def _save_json(path: Path, data: Any) -> None:
    """Persist data as pretty-printed JSON."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    except OSError as exc:
        print(f"[state] Could not save {path.name}: {exc}")


def _merge_config(loaded: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure all expected keys exist without dropping user values."""
    merged = json.loads(json.dumps(defaults))  # deep copy of defaults
    merged["quiet_hours"].update(loaded.get("quiet_hours", {}))
    merged["rules"].update(loaded.get("rules", {}))
    return merged


# --- Seed data ------------------------------------------------------------


def _seed_events() -> List[Dict[str, Any]]:
    """A few realistic-looking events so the dashboard isn't empty on first run."""
    now = datetime.now()
    return [
        {"id": "seed1", "timestamp": (now - timedelta(minutes=38)).isoformat(),
         "device_id": "front_door", "device_name": "Front Door",
         "event_type": "door_open", "details": "Opened from inside (simulated seed)", "simulated": True},
        {"id": "seed2", "timestamp": (now - timedelta(minutes=37)).isoformat(),
         "device_id": "front_door", "device_name": "Front Door",
         "event_type": "door_close", "details": "Closed normally (simulated seed)", "simulated": True},
        {"id": "seed3", "timestamp": (now - timedelta(minutes=15)).isoformat(),
         "device_id": "motion_sensor", "device_name": "Motion Sensor",
         "event_type": "motion_detected", "details": "Movement near the entry (simulated seed)", "simulated": True},
        {"id": "seed4", "timestamp": (now - timedelta(minutes=5)).isoformat(),
         "device_id": "doorbell", "device_name": "Doorbell",
         "event_type": "doorbell_press", "details": "Doorbell pressed (simulated seed)", "simulated": True},
    ]


# --- Public API -----------------------------------------------------------


def init_state() -> None:
    """Initialize session state from JSON files (runs once per session)."""
    if "devices" not in st.session_state:
        st.session_state.devices = _load_json(DEVICES_FILE, [])
    if "config" not in st.session_state:
        st.session_state.config = _merge_config(_load_json(CONFIG_FILE, DEFAULT_CONFIG), DEFAULT_CONFIG)
    if "events" not in st.session_state:
        loaded = _load_json(EVENTS_FILE, [])
        st.session_state.events = loaded if loaded else _seed_events()
        if not loaded:
            _save_json(EVENTS_FILE, st.session_state.events)
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []


def get_events() -> List[Dict[str, Any]]:
    return st.session_state.events


def get_devices() -> List[Dict[str, Any]]:
    return st.session_state.devices


def get_config() -> Dict[str, Any]:
    return st.session_state.config


def add_events(new_events: List[Dict[str, Any]]) -> int:
    """Append new events (deduping by id) and persist. Returns how many were added."""
    existing_ids = {e["id"] for e in st.session_state.events}
    added = 0
    for e in new_events:
        if e.get("id") not in existing_ids:
            st.session_state.events.append(e)
            existing_ids.add(e["id"])
            added += 1
    _save_json(EVENTS_FILE, st.session_state.events)
    return added


def clear_events() -> None:
    """Remove all simulated events and persist the empty list."""
    st.session_state.events = []
    _save_json(EVENTS_FILE, st.session_state.events)


def update_config(new_config: Dict[str, Any]) -> None:
    """Update the in-memory config and persist it to config.json."""
    st.session_state.config = _merge_config(new_config, DEFAULT_CONFIG)
    _save_json(CONFIG_FILE, st.session_state.config)
