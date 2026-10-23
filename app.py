<<<<<<< HEAD
"""Ring Guardian AI — Streamlit dashboard entry point.

A smart-home security *event monitoring* dashboard for SIMULATED devices.
It does not connect to real Ring hardware, real Ring credentials, or AWS.
"""
from __future__ import annotations

from datetime import datetime, time

import pandas as pd
import streamlit as st

import alert_engine
import assistant
import simulator
import state
from utils import (
    EVENT_TYPE_META,
    compute_device_states,
    filter_events,
    parse_ts,
    status_class,
    time_ago,
)

st.set_page_config(
    page_title="Ring Guardian AI",
    page_icon="🛡️",
=======
"""
app.py — Ring Guardian AI  |  Main Streamlit Dashboard

NOTE: All devices and events are SIMULATED. This application does not connect
to real Ring hardware, real Ring credentials, or any AWS service.

Run with:
    streamlit run app.py
"""

import sys
from pathlib import Path

# Ensure project root is on the Python path so imports always resolve
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

from simulator import (
    get_all_events,
    get_device_status,
    generate_random_event,
    generate_n_random_events,
    clear_events,
    scenario_door_left_open,
    scenario_normal_day,
    scenario_quiet_hours_activity,
    scenario_repeated_motion,
    DEVICES,
)
from alert_engine import (
    analyse_events,
    load_config,
    save_config,
    DEFAULT_CONFIG,
    SEVERITY_EMOJI,
    SEVERITY_COLOR,
)
from assistant import chat

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Ring Guardian AI",
    page_icon="🔒",
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
    layout="wide",
    initial_sidebar_state="expanded",
)

<<<<<<< HEAD
# --- Custom styling -------------------------------------------------------

st.markdown(
    """
    <style>
        .rg-badge {
            background-color:#332540; color:#D8B4FE; border:1px solid #7C3AED;
            border-radius:999px; padding:3px 12px; font-size:0.72rem; font-weight:600;
            letter-spacing:0.03em;
        }
        .device-card {
            background-color:#1B1E27; border:1px solid #2A2D38;
            border-left:4px solid #555; border-radius:12px; padding:14px 16px;
            min-height:120px;
        }
        .status-open { border-left-color:#FF4B4B; }
        .status-closed { border-left-color:#21C7A8; }
        .status-motion { border-left-color:#FFB400; }
        .status-idle { border-left-color:#555; }
        .card-icon { font-size:1.4rem; }
        .card-title { font-weight:700; font-size:1.05rem; margin-top:2px; }
        .card-status { font-size:0.82rem; color:#9aa0aa; }
        .card-big { font-size:1.15rem; font-weight:700; margin-top:6px; }
        .timeline-item {
            padding:7px 2px; border-bottom:1px solid #23262F; font-size:0.88rem;
        }
        .alert-item {
            padding:9px 11px; border-radius:9px; margin-bottom:7px;
            background:#15171F; border:1px solid #23262F;
        }
        .section-title { font-size:1.1rem; font-weight:700; margin-bottom:8px; }
        .muted { color:#8A8F98; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --- Initialization -------------------------------------------------------

state.init_state()
events = state.get_events()
devices = state.get_devices()
config = state.get_config()
alerts = alert_engine.evaluate(events, config)
states = compute_device_states(events, devices)

# Build the assistant backend once per session. The local deterministic
# backend is used now; a Strands Agents SDK + Amazon Bedrock backend can be
# returned from assistant.build_assistant() later without touching call sites.
if "assistant_backend" not in st.session_state:
    st.session_state.assistant_backend = assistant.build_assistant()
assistant_backend = st.session_state.assistant_backend


def _to_time(text: str) -> time:
    try:
        return datetime.strptime(text, "%H:%M").time()
    except (ValueError, TypeError):
        return time(1, 0)


def _events_today() -> int:
    today = datetime.now().date()
    return sum(
        1 for e in events
        if parse_ts(e.get("timestamp")) and parse_ts(e["timestamp"]).date() == today
    )


def _open_door_count() -> int:
    return sum(
        1 for d in devices
        if d.get("type") == "door"
        and states.get(d["id"], {}).get("status") == "Open"
    )


# --- Sidebar: configuration + simulation ---------------------------------

with st.sidebar:
    st.markdown("## 🛡️ Ring Guardian AI")
    st.caption("Simulated smart-home security monitoring")
    st.divider()

    st.markdown("### ⚙️ Alert configuration")
    q_start = st.time_input("Quiet hours start", value=_to_time(config["quiet_hours"]["start"]))
    q_end = st.time_input("Quiet hours end", value=_to_time(config["quiet_hours"]["end"]))
    door_min = st.number_input("Door open threshold (minutes)", 1, 120,
                               value=int(config["rules"]["door_open_threshold_minutes"]))
    motion_win = st.number_input("Motion burst window (seconds)", 10, 600,
                                  value=int(config["rules"]["motion_burst_window_seconds"]))
    motion_thresh = st.number_input("Motion burst threshold (events)", 1, 20,
                                     value=int(config["rules"]["motion_burst_threshold"]))
    if st.button("💾 Save configuration", width="stretch"):
        state.update_config({
            "quiet_hours": {"start": q_start.strftime("%H:%M"), "end": q_end.strftime("%H:%M")},
            "rules": {
                "door_open_threshold_minutes": int(door_min),
                "motion_burst_window_seconds": int(motion_win),
                "motion_burst_threshold": int(motion_thresh),
            },
        })
        st.toast("Configuration saved", icon="✅")
        st.rerun()

    st.divider()
    st.markdown("### 🎛️ Event simulator")
    st.caption("Generate example simulated scenarios")
    for label, func_name, help_text in simulator.SCENARIOS:
        if st.button(label, width="stretch", help=help_text):
            fn = getattr(simulator, func_name)
            added = state.add_events(fn(devices))
            st.toast(f"Added {added} simulated event(s)", icon="📡")
            st.rerun()

    st.divider()
    st.markdown("### 🧪 Threshold demo")
    st.caption("Deterministic garage-door event that exceeds the configured threshold")
    demo_c1, demo_c2 = st.columns(2)
    with demo_c1:
        if st.button("▶️ Run demo", width="stretch",
                     help="Open the garage door past the configured threshold (should alert)"):
            added = state.add_events(
                simulator.scenario_garage_threshold_demo(devices, config))
            st.toast(f"Demo: added {added} event(s)", icon="🧪")
            st.rerun()
    with demo_c2:
        if st.button("🔄 Reset", width="stretch",
                     help="Clear all events so the demo can be repeated"):
            state.clear_events()
            st.toast("Events cleared — demo reset", icon="🔄")
            st.rerun()

    st.divider()
    if st.button("🗑️ Clear all events", width="stretch",
                 help="Remove every simulated event from the dashboard"):
        state.clear_events()
        st.toast("All events cleared", icon="🧹")
        st.rerun()


# --- Header ---------------------------------------------------------------

title_col, badge_col = st.columns([8, 3])
with title_col:
    st.markdown("# 🛡️ Ring Guardian AI")
    st.caption("Smart-home security event monitoring — local, simulated dashboard")
with badge_col:
    st.markdown(
        "<div style='text-align:right; margin-top:6px;'>"
        "<span class='rg-badge'>SIMULATED DATA · NO REAL HARDWARE</span>"
        "</div>",
        unsafe_allow_html=True,
    )

st.divider()

# --- Quick action: generate one simulated test event ----------------------
# Event generation also exists in the sidebar "Event simulator" panel; this
# button is surfaced in the main body so it is easy to find. It generates one
# random simulated event, appends it via the existing state layer (so it
# persists to st.session_state AND data/events.json), then reruns so the
# activity feed, event count, device cards, alerts, and explorer all update.
# Generation only happens on a click — ordinary page reruns never add or
# duplicate events (st.button is momentary, and add_events dedupes by id).
if st.button("🎲 Generate Test Event",
             help="Add one random simulated event now"):
    added = state.add_events(simulator.random_event(devices))
    st.toast(f"Added {added} simulated event(s)", icon="🎲")
    st.rerun()
st.caption("Adds one random simulated event. Generation only happens on click — "
           "ordinary page reruns never add or duplicate events.")

st.write("")

# --- Metric row ----------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)
m1.metric("Events today", _events_today())
m2.metric("Active alerts", len(alerts))
m3.metric("Connected devices", len(devices))
m4.metric("Doors left open", _open_door_count())

st.write("")

# --- Device status cards --------------------------------------------------

cards = st.columns(len(devices)) if devices else []
for col, device in zip(cards, devices):
    s = states.get(device["id"], {})
    cls = status_class(s.get("status", "Idle"))
    last = time_ago(s.get("last_event_ts"))
    with col:
        st.markdown(
            f"""
            <div class='device-card {cls}'>
              <div class='card-icon'>{device.get('icon','🏠')}</div>
              <div class='card-title'>{device['name']}</div>
              <div class='card-big'>{s.get('status_emoji','⚪')} {s.get('status','Idle')}</div>
              <div class='card-status'>Last: {s.get('last_event_label','—')} · {last}</div>
              <div class='card-status'>Today: {s.get('events_today',0)} events</div>
=======
# ---------------------------------------------------------------------------
# Custom CSS — dark professional theme
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
/* ── Global background ─────────────────────────────────────────── */
.stApp { background-color: #0e1117; color: #e0e0e0; }

/* ── Metric cards ────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: #1c2333;
    border: 1px solid #2d3748;
    border-radius: 10px;
    padding: 16px 20px;
}
[data-testid="stMetricValue"] { color: #63b3ed; font-size: 2rem !important; }
[data-testid="stMetricLabel"] { color: #a0aec0; }

/* ── Device status cards ─────────────────────────────────────────── */
.device-card {
    background: #1c2333;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 10px;
    transition: border-color 0.2s;
}
.device-card:hover { border-color: #4a90d9; }
.device-card-title { font-size: 1rem; font-weight: 600; color: #e2e8f0; }
.device-card-status { font-size: 0.85rem; color: #a0aec0; margin-top: 4px; }

/* ── Alert cards ─────────────────────────────────────────────────── */
.alert-card {
    background: #1a202c;
    border-left: 4px solid;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
}
.alert-high   { border-color: #FC8181; }
.alert-medium { border-color: #F6AD55; }
.alert-low    { border-color: #68D391; }

/* ── Timeline event rows ─────────────────────────────────────────── */
.event-row {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    border-radius: 8px;
    margin-bottom: 4px;
    background: #1c2333;
    border: 1px solid #2d3748;
    font-size: 0.88rem;
}
.event-time  { color: #718096; min-width: 160px; }
.event-badge {
    background: #2d3748;
    color: #90cdf4;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.78rem;
    margin: 0 8px;
}

/* ── Chat bubbles ────────────────────────────────────────────────── */
.chat-user {
    background: #2b4a7a;
    border-radius: 12px 12px 0 12px;
    padding: 10px 14px;
    margin: 6px 0 6px 40px;
    font-size: 0.9rem;
}
.chat-bot {
    background: #1c2333;
    border: 1px solid #2d3748;
    border-radius: 12px 12px 12px 0;
    padding: 10px 14px;
    margin: 6px 40px 6px 0;
    font-size: 0.9rem;
}

/* ── Section headers ─────────────────────────────────────────────── */
.section-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #90cdf4;
    border-bottom: 1px solid #2d3748;
    padding-bottom: 6px;
    margin-bottom: 14px;
}

/* ── Simulated badge ─────────────────────────────────────────────── */
.sim-badge {
    background: #2d3748;
    color: #f6ad55;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] { background-color: #161b27; }

/* ── Tabs ────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] { color: #a0aec0 !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #63b3ed !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str[:19])


def _fmt_ts(ts_str: str | None) -> str:
    if not ts_str:
        return "—"
    try:
        return _parse_ts(ts_str).strftime("%b %d  %H:%M UTC")
    except ValueError:
        return ts_str


def _events_to_df(events: list[dict]) -> pd.DataFrame:
    """Convert event list to a tidy DataFrame for filtering/display."""
    if not events:
        return pd.DataFrame(
            columns=["timestamp", "device_name", "event_type", "device_id", "id"]
        )
    df = pd.DataFrame(events)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp", ascending=False).reset_index(drop=True)
    return df


DEVICE_ICON = {
    "door_sensor":   "🚪",
    "doorbell":      "🔔",
    "motion_sensor": "👁️",
}

STATUS_ICON = {
    "open":    "🔓",
    "closed":  "🔒",
    "idle":    "💤",
    "unknown": "❓",
}

STATUS_COLOR = {
    "open":    "#FC8181",
    "closed":  "#68D391",
    "idle":    "#90CDF4",
    "unknown": "#718096",
}

EVENT_ICON = {
    "door_opened":       "🔓",
    "door_closed":       "🔒",
    "motion_detected":   "👁️",
    "doorbell_pressed":  "🔔",
}


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(alerts: list[dict], total_events: int) -> None:
    with st.sidebar:
        st.markdown("## 🔒 Ring Guardian AI")
        st.markdown('<span class="sim-badge">⚡ SIMULATED</span>', unsafe_allow_html=True)
        st.markdown("---")

        # Live stats
        alert_count = len(alerts)
        st.markdown("### System Status")
        col1, col2 = st.columns(2)
        col1.metric("Events", total_events)
        col2.metric("Alerts", alert_count, delta=None)

        if alert_count == 0:
            st.success("✅ All clear")
        else:
            high = sum(1 for a in alerts if a["severity"] == "high")
            if high:
                st.error(f"🔴 {high} high-severity alert(s)")
            else:
                st.warning(f"🟡 {alert_count} alert(s) active")

        st.markdown("---")
        st.markdown("### Devices")
        for d in DEVICES:
            st.markdown(f"{DEVICE_ICON.get(d['type'], '📡')} {d['name']}")

        st.markdown("---")
        st.caption(
            "⚠️ This dashboard uses **simulated** data only.  \n"
            "No real Ring hardware or AWS services are connected."
        )


# ---------------------------------------------------------------------------
# Tab 1 — Dashboard Overview
# ---------------------------------------------------------------------------

def render_dashboard(events: list[dict], alerts: list[dict]) -> None:
    st.markdown('<div class="section-header">System Overview</div>', unsafe_allow_html=True)

    # ── Top KPI metrics ────────────────────────────────────────────
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff_24h = now - timedelta(hours=24)
    events_today = sum(1 for e in events if _parse_ts(e["timestamp"]) >= cutoff_24h)
    alert_count  = len(alerts)
    connected    = len(DEVICES)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📋 Total Events",       len(events))
    k2.metric("📅 Events (24 h)",      events_today)
    k3.metric("🚨 Active Alerts",      alert_count)
    k4.metric("📡 Connected Devices",  connected)

    st.markdown("---")

    # ── Device status cards ────────────────────────────────────────
    st.markdown('<div class="section-header">Device Status</div>', unsafe_allow_html=True)
    status_map = get_device_status(events)
    cols = st.columns(len(DEVICES))
    for col, device in zip(cols, DEVICES):
        info = status_map[device["id"]]
        s_icon  = STATUS_ICON.get(info["status"], "❓")
        d_icon  = DEVICE_ICON.get(device["type"], "📡")
        s_color = STATUS_COLOR.get(info["status"], "#718096")
        last    = _fmt_ts(info["last_seen"])
        with col:
            st.markdown(
                f"""
                <div class="device-card">
                    <div class="device-card-title">{d_icon} {info['name']}</div>
                    <div style="font-size:1.6rem; margin:6px 0;">{s_icon}</div>
                    <div style="color:{s_color}; font-weight:600;">{info['status'].capitalize()}</div>
                    <div class="device-card-status">Last: {last}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Active alerts summary ──────────────────────────────────────
    left, right = st.columns([1, 1])

    with left:
        st.markdown('<div class="section-header">Active Alerts</div>', unsafe_allow_html=True)
        if not alerts:
            st.success("✅ No active alerts")
        else:
            for alert in alerts[:5]:
                sev   = alert["severity"]
                emoji = SEVERITY_EMOJI.get(sev, "⚪")
                st.markdown(
                    f"""
                    <div class="alert-card alert-{sev}">
                        <strong>{emoji} {alert['device_name']}</strong>
                        <span style="font-size:0.78rem; color:#718096; margin-left:8px;">
                            [{sev.upper()}]
                        </span>
                        <div style="font-size:0.85rem; color:#a0aec0; margin-top:4px;">
                            {alert['message']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    # ── Recent activity timeline ───────────────────────────────────
    with right:
        st.markdown('<div class="section-header">Recent Activity</div>', unsafe_allow_html=True)
        recent_10 = sorted(events, key=lambda e: e["timestamp"], reverse=True)[:10]
        if not recent_10:
            st.info("No events yet. Go to **Event Simulator** to generate some.")
        else:
            for e in recent_10:
                e_icon = EVENT_ICON.get(e["event_type"], "📌")
                label  = e["event_type"].replace("_", " ").title()
                ts_str = _fmt_ts(e["timestamp"])
                st.markdown(
                    f"""
                    <div class="event-row">
                        <span class="event-time">{ts_str}</span>
                        <span style="font-size:1.1rem;">{e_icon}</span>
                        <span class="event-badge">{e['device_name']}</span>
                        <span>{label}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Tab 2 — Event Simulator
# ---------------------------------------------------------------------------

def render_simulator() -> None:
    st.markdown('<div class="section-header">Event Simulator</div>', unsafe_allow_html=True)
    st.info(
        "⚡ **All events below are simulated.** "
        "No real Ring hardware or network connection is used."
    )

    # ── Scenario buttons ───────────────────────────────────────────
    st.markdown("#### Pre-built Scenarios")
    st.caption("Each scenario injects events designed to showcase specific alert rules.")

    sc1, sc2, sc3, sc4 = st.columns(4)
    with sc1:
        if st.button("🚪 Door Left Open", use_container_width=True, help="Triggers door-open-too-long alert"):
            evts = scenario_door_left_open()
            st.success(f"Added {len(evts)} event(s) — front door opened 10 min ago, never closed.")
            st.rerun()
    with sc2:
        if st.button("👁️ Repeated Motion", use_container_width=True, help="5 motions in 2 minutes"):
            evts = scenario_repeated_motion()
            st.success(f"Added {len(evts)} event(s) — rapid motion cluster on motion sensor.")
            st.rerun()
    with sc3:
        if st.button("🌙 Night Activity", use_container_width=True, help="Quiet-hours alert at 02:30"):
            evts = scenario_quiet_hours_activity()
            st.success(f"Added {len(evts)} event(s) — doorbell + door open at 02:30 UTC.")
            st.rerun()
    with sc4:
        if st.button("☀️ Normal Day", use_container_width=True, help="Routine activity, no alerts"):
            evts = scenario_normal_day()
            st.success(f"Added {len(evts)} event(s) — a typical uneventful day.")
            st.rerun()

    st.markdown("---")

    # ── Manual event generation ────────────────────────────────────
    st.markdown("#### Manual Event Generation")
    m1, m2, m3 = st.columns(3)

    with m1:
        if st.button("🎲 Random Event", use_container_width=True):
            evt = generate_random_event()
            st.success(
                f"Generated: **{evt['device_name']}** → "
                f"{evt['event_type'].replace('_', ' ').title()}"
            )
            st.rerun()

    with m2:
        n = st.number_input("How many random events?", min_value=1, max_value=50, value=10, step=1)

    with m3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(f"🎲 Generate {n} Events", use_container_width=True):
            evts = generate_n_random_events(int(n))
            st.success(f"Generated {len(evts)} random events across the last 24 hours.")
            st.rerun()

    st.markdown("---")

    # ── Danger zone — reset ────────────────────────────────────────
    st.markdown("#### ⚠️ Reset")
    with st.expander("Clear all events (irreversible)"):
        st.warning("This deletes all stored simulated events. The file is local only.")
        if st.button("🗑️ Clear All Events", type="primary"):
            clear_events()
            st.success("All events cleared.")
            st.rerun()


# ---------------------------------------------------------------------------
# Tab 3 — Alert Engine
# ---------------------------------------------------------------------------

def render_alerts(events: list[dict], alerts: list[dict]) -> None:
    st.markdown('<div class="section-header">Alert Engine</div>', unsafe_allow_html=True)
    st.caption(
        "Rules below are **configurable thresholds**, not a reliable intrusion-detection system. "
        "Each alert explains exactly why it fired."
    )

    # ── Config panel ──────────────────────────────────────────────
    config = load_config()
    with st.expander("⚙️ Configure Alert Rules", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            door_thresh = st.slider(
                "Door open threshold (minutes)",
                min_value=1, max_value=60,
                value=int(config["door_open_threshold_minutes"]),
            )
        with c2:
            motion_count = st.slider(
                "Repeated motion count",
                min_value=2, max_value=20,
                value=int(config["motion_repeat_count"]),
            )
            motion_window = st.slider(
                "Motion window (minutes)",
                min_value=1, max_value=30,
                value=int(config["motion_repeat_window_minutes"]),
            )
        with c3:
            quiet_start = st.slider("Quiet hours start (UTC hour)", 0, 23, int(config["quiet_hours_start"]))
            quiet_end   = st.slider("Quiet hours end (UTC hour)",   0, 23, int(config["quiet_hours_end"]))

        if st.button("💾 Save Configuration"):
            new_config = {
                "door_open_threshold_minutes": door_thresh,
                "motion_repeat_count":         motion_count,
                "motion_repeat_window_minutes": motion_window,
                "quiet_hours_start":           quiet_start,
                "quiet_hours_end":             quiet_end,
            }
            save_config(new_config)
            st.success("Configuration saved. Re-analysing…")
            # Re-run to refresh alerts with new config
            st.rerun()

    st.markdown("---")

    # ── Alert list ────────────────────────────────────────────────
    if not alerts:
        st.success("✅ No active alerts based on current rules and events.")
        st.markdown(
            "Try running a scenario from the **Event Simulator** tab to see alerts generated here."
        )
        return

    st.markdown(f"**{len(alerts)} alert(s) found:**")

    for alert in alerts:
        sev   = alert["severity"]
        emoji = SEVERITY_EMOJI.get(sev, "⚪")
        color = SEVERITY_COLOR.get(sev, "#a0aec0")
        fired = alert.get("generated_at", "")[:19].replace("T", " ")

        st.markdown(
            f"""
            <div class="alert-card alert-{sev}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="font-size:1rem;">{emoji} {alert['device_name']}</strong>
                    <span style="color:{color}; font-size:0.8rem; font-weight:600;">
                        {sev.upper()} · {alert['rule'].replace('_', ' ').title()}
                    </span>
                </div>
                <div style="margin-top:6px; font-size:0.87rem; color:#cbd5e0;">
                    {alert['message']}
                </div>
                <div style="margin-top:4px; font-size:0.75rem; color:#718096;">
                    Generated: {fired} UTC
                </div>
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
            </div>
            """,
            unsafe_allow_html=True,
        )

<<<<<<< HEAD
st.write("")

# --- Activity timeline + Alerts ------------------------------------------

left, right = st.columns([3, 2])

with left:
    st.markdown("<div class='section-title'>Recent activity timeline</div>",
                unsafe_allow_html=True)
    ordered = sorted(events, key=lambda e: e.get("timestamp", ""), reverse=True)
    if not ordered:
        st.info("No events yet. Use the simulator panel in the sidebar to generate some.")
    else:
        for e in ordered[:12]:
            meta = EVENT_TYPE_META.get(e["event_type"], {"emoji": "•", "label": e["event_type"]})
            ts = parse_ts(e.get("timestamp"))
            when = ts.strftime("%H:%M:%S") if ts else "?"
            st.markdown(
                f"<div class='timeline-item'>{meta['emoji']} <b>{when}</b> · "
                f"{e['device_name']} — {meta['label']} "
                f"<span class='muted'>({time_ago(ts)})</span><br>"
                f"<span class='muted'>{e.get('details','')}</span></div>",
                unsafe_allow_html=True,
            )

with right:
    st.markdown("<div class='section-title'>Active alerts</div>", unsafe_allow_html=True)
    if not alerts:
        st.success("No active alerts. Everything looks normal.")
    else:
        sev_emoji = {"critical": "🔴", "warning": "🟠", "info": "🔵"}
        counts = {"critical": 0, "warning": 0, "info": 0}
        for a in alerts:
            counts[a["severity"]] = counts.get(a["severity"], 0) + 1
        summary = "   ".join(
            f"{sev_emoji[s]} {counts[s]} {s}"
            for s in ("critical", "warning", "info") if counts.get(s)
        )
        st.caption(summary)
        for a in alerts[:10]:
            st.markdown(
                f"<div class='alert-item'>{sev_emoji.get(a['severity'],'⚪')} "
                f"<b>[{a['severity'].upper()}]</b> {a['message']}</div>",
                unsafe_allow_html=True,
            )
        if len(alerts) > 10:
            st.caption(f"...and {len(alerts) - 10} more alerts")

st.write("")

# --- Event explorer -------------------------------------------------------

st.markdown("<div class='section-title'>Event explorer</div>", unsafe_allow_html=True)
exp_c1, exp_c2, exp_c3 = st.columns([2, 2, 2])
device_names = [d["name"] for d in devices]
with exp_c1:
    sel_devices = st.multiselect("Filter by device", device_names,
                                 key="exp_devices",
                                 help="Leave empty to include all devices")
with exp_c2:
    type_labels = {k: v["label"] for k, v in EVENT_TYPE_META.items()}
    sel_types = st.multiselect("Filter by event type", list(type_labels.values()),
                               key="exp_types",
                               help="Leave empty to include all event types")
with exp_c3:
    date_range = st.radio("Date range", ["All time", "Today", "Last 7 days"],
                          key="exp_range", horizontal=True)

# Filter using the shared helper so the dashboard and tests stay in sync.
# Filters combine with AND: an event must match the selected device, event
# type, and date range (an empty selection means "no filter on that axis").
wanted_type_ids = {tid for tid, lbl in type_labels.items() if lbl in sel_types}
filtered = filter_events(
    events,
    device_names=sel_devices or None,
    event_types=wanted_type_ids or None,
    date_range=date_range,
)

if not filtered:
    st.info("No events match the current filters.")
else:
    df = pd.DataFrame(filtered)
    df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.sort_values("_ts", ascending=False)
    df["Time"] = df["_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["Event"] = df["event_type"].map(lambda t: EVENT_TYPE_META.get(t, {}).get("label", t))
    df["Device"] = df["device_name"]
    df["Details"] = df["details"]
    df["Simulated"] = df["simulated"].map(lambda v: "Yes" if v else "—")
    st.dataframe(
        df[["Time", "Device", "Event", "Details", "Simulated"]],
        width="stretch",
        hide_index=True,
    )
    st.caption(f"{len(filtered)} event(s) shown.")

st.write("")

# --- Assistant chat ------------------------------------------------------

st.markdown("<div class='section-title'>Assistant chat (local)</div>", unsafe_allow_html=True)
st.caption("A deterministic local assistant. No external LLM or AWS service is connected.")

for role, text in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(text)

user_input = st.chat_input("Ask about device status, events, or alerts...")
if user_input:
    st.session_state.chat_history.append(("user", user_input))
    reply = assistant_backend.answer(
        user_input, assistant.AssistantContext(events, devices, alerts, config))
    st.session_state.chat_history.append(("assistant", reply))
    st.rerun()
=======

# ---------------------------------------------------------------------------
# Tab 4 — Event Explorer
# ---------------------------------------------------------------------------

def render_explorer(events: list[dict]) -> None:
    st.markdown('<div class="section-header">Event Explorer</div>', unsafe_allow_html=True)

    df = _events_to_df(events)

    if df.empty:
        st.info("No events to explore. Head to **Event Simulator** to generate some.")
        return

    # ── Filter controls ────────────────────────────────────────────
    st.markdown("#### Filters")
    f1, f2, f3, f4 = st.columns(4)

    with f1:
        device_options = ["All"] + sorted(df["device_name"].unique().tolist())
        selected_device = st.selectbox("Device", device_options)

    with f2:
        type_options = ["All"] + sorted(df["event_type"].unique().tolist())
        selected_type = st.selectbox("Event Type", type_options)

    with f3:
        min_ts = df["timestamp"].min().to_pydatetime()
        max_ts = df["timestamp"].max().to_pydatetime()
        date_from = st.date_input("From", value=min_ts.date())

    with f4:
        date_to = st.date_input("To", value=max_ts.date())

    # Apply filters
    filtered = df.copy()
    if selected_device != "All":
        filtered = filtered[filtered["device_name"] == selected_device]
    if selected_type != "All":
        filtered = filtered[filtered["event_type"] == selected_type]

    try:
        filtered = filtered[
            (filtered["timestamp"].dt.date >= date_from)
            & (filtered["timestamp"].dt.date <= date_to)
        ]
    except Exception:
        pass  # Date parse edge case — show all

    st.markdown("---")

    # ── Results ────────────────────────────────────────────────────
    st.markdown(f"**{len(filtered)} event(s) matched**")

    if filtered.empty:
        st.warning("No events match the current filters.")
        return

    # Display columns
    display_cols = ["timestamp", "device_name", "event_type"]
    display_df = filtered[display_cols].copy()
    display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d  %H:%M:%S")
    display_df.columns = ["Timestamp (UTC)", "Device", "Event Type"]
    display_df["Event Type"] = display_df["Event Type"].str.replace("_", " ").str.title()

    st.dataframe(
        display_df,
        use_container_width=True,
        height=min(600, 60 + len(display_df) * 35),
    )

    # ── Mini chart — events per hour ──────────────────────────────
    st.markdown("#### Events per Hour")
    hourly = (
        filtered.set_index("timestamp")
        .resample("h")
        .size()
        .reset_index()
    )
    hourly.columns = ["Hour", "Count"]
    hourly["Hour"] = hourly["Hour"].dt.strftime("%b %d %H:00")
    if not hourly.empty:
        st.bar_chart(hourly.set_index("Hour")["Count"])


# ---------------------------------------------------------------------------
# Tab 5 — Assistant Chat
# ---------------------------------------------------------------------------

def render_chat() -> None:
    st.markdown('<div class="section-header">Assistant Chat</div>', unsafe_allow_html=True)
    st.info(
        "🤖 **Local deterministic assistant** — answers are derived from your simulated event "
        "data using rule-based matching. No external AI, LLM, or AWS service is connected.  \n"
        "A future phase will integrate **Strands Agents SDK + Amazon Bedrock**."
    )

    # Initialise session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ── Chat display ──────────────────────────────────────────────
    chat_container = st.container()
    with chat_container:
        if not st.session_state.chat_history:
            st.markdown(
                '<div class="chat-bot">👋 Hi! I\'m your Ring Guardian assistant. '
                "Ask me about device status, recent events, or active alerts.  \n"
                "Type **help** for example questions.</div>",
                unsafe_allow_html=True,
            )
        else:
            for msg in st.session_state.chat_history:
                if msg["role"] == "user":
                    st.markdown(
                        f'<div class="chat-user">🧑 {msg["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<div class="chat-bot">🤖 {msg["content"]}</div>',
                        unsafe_allow_html=True,
                    )

    # ── Input area ────────────────────────────────────────────────
    st.markdown("---")
    with st.form("chat_form", clear_on_submit=True):
        col_input, col_send = st.columns([5, 1])
        with col_input:
            user_input = st.text_input(
                "Your message",
                placeholder="e.g. What is the status of the front door?",
                label_visibility="collapsed",
            )
        with col_send:
            submitted = st.form_submit_button("Send ➤", use_container_width=True)

    if submitted and user_input.strip():
        response = chat(user_input.strip())
        st.session_state.chat_history.append({"role": "user",      "content": user_input.strip()})
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

    # ── Quick-question chips ──────────────────────────────────────
    st.markdown("**Quick questions:**")
    chips = [
        "Show recent events",
        "Are there any alerts?",
        "Status of the front door",
        "What happened at the garage door?",
        "How many events today?",
        "Show all device statuses",
    ]
    chip_cols = st.columns(len(chips))
    for col, chip in zip(chip_cols, chips):
        with col:
            if st.button(chip, use_container_width=True, key=f"chip_{chip}"):
                response = chat(chip)
                st.session_state.chat_history.append({"role": "user",      "content": chip})
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()

    # ── Clear chat ────────────────────────────────────────────────
    if st.session_state.chat_history:
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # ── Header ────────────────────────────────────────────────────
    header_col, badge_col = st.columns([5, 1])
    with header_col:
        st.markdown("# 🔒 Ring Guardian AI")
        st.caption("Smart-Home Security Monitoring Dashboard")
    with badge_col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            '<span class="sim-badge">⚡ SIMULATED DATA</span>', unsafe_allow_html=True
        )

    # ── Load data ─────────────────────────────────────────────────
    events = get_all_events()
    config = load_config()
    alerts = analyse_events(events, config)

    # ── Sidebar ───────────────────────────────────────────────────
    render_sidebar(alerts, len(events))

    # ── Main tabs ─────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Dashboard",
        "⚡ Event Simulator",
        "🚨 Alert Engine",
        "🔍 Event Explorer",
        "💬 Assistant",
    ])

    with tab1:
        render_dashboard(events, alerts)

    with tab2:
        render_simulator()

    with tab3:
        render_alerts(events, alerts)

    with tab4:
        render_explorer(events)

    with tab5:
        render_chat()


if __name__ == "__main__":
    main()
>>>>>>> 45dcc4b17f9e0523a38e5e44df2fcbd71c03ad50
