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
    layout="wide",
    initial_sidebar_state="expanded",
)

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
            </div>
            """,
            unsafe_allow_html=True,
        )


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
