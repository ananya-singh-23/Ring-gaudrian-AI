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
    layout="wide",
    initial_sidebar_state="expanded",
)

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
            </div>
            """,
            unsafe_allow_html=True,
        )

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
