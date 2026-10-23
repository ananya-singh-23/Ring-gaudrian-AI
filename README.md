# 🔒 Ring Guardian AI

A polished smart-home security event monitoring dashboard inspired by Ring devices,
built with Python and Streamlit.

> ⚠️ **All devices and events are simulated.** This application does not connect to
> real Ring hardware, real Ring credentials, or any AWS service.
> A future phase will integrate the Strands Agents SDK and Amazon Bedrock.

---

## Features

| Tab | What it does |
|---|---|
| 📊 **Dashboard** | Device status cards, KPI metrics, alert summary, activity timeline |
| ⚡ **Event Simulator** | Pre-built scenarios and random event generation |
| 🚨 **Alert Engine** | Configurable rule-based alerts with plain-English explanations |
| 🔍 **Event Explorer** | Filter events by device, type, and date range; hourly chart |
| 💬 **Assistant** | Local deterministic chat assistant backed by live event data |

### Alert Rules

| Rule | Description |
|---|---|
| Door open too long | Door sensor left open beyond the configured threshold (default 5 min) |
| Repeated motion | More than N motion events within a rolling time window |
| Quiet-hours activity | Any event during configured quiet hours (default 23:00–06:00 UTC) |

All thresholds are adjustable inside the **Alert Engine** tab — no code changes needed.

---

## Requirements

- **Python 3.11 or later** (3.10 works if you replace `X | Y` union hints with `Optional[X]`)
- Windows 10 / 11 (also works on macOS and Linux)
- No AWS account, no Ring account, no physical devices needed

---

## Installation (Windows)

### 1 — Clone or download the project

```powershell
# If you have Git:
git clone https://github.com/your-repo/ring-guardian-ai.git
cd ring-guardian-ai

# Or just unzip the folder and open a terminal inside it.
```

### 2 — Create and activate a virtual environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If you see a script-execution policy error, run this first (once):

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 3 — Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Running the Application

```powershell
streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`).
Open it in your browser. The dashboard loads instantly with no data — head to
**Event Simulator** and click a scenario button to get started.

---

## Running the Tests

```powershell
# From the project root, with the venv active:
python -m pytest tests/ -v
```

Expected output:

```
tests/test_alert_engine.py::test_door_open_triggers_alert       PASSED
tests/test_alert_engine.py::test_door_closed_no_alert           PASSED
...
tests/test_simulator.py::test_make_event_valid                  PASSED
...
tests/test_assistant.py::test_help_response                     PASSED
...
============= N passed in X.XXs =============
```

---

## Project Structure

```
ring-guardian-ai/
│
├── app.py              # Streamlit dashboard — entry point
├── simulator.py        # Event generator, scenarios, persistence
├── alert_engine.py     # Deterministic rule-based alert engine
├── assistant.py        # Local deterministic chat assistant
├── requirements.txt
├── README.md
│
├── data/
│   ├── events.json     # Persisted simulated events (auto-created)
│   └── config.json     # Alert rule thresholds
│
└── tests/
    ├── test_simulator.py
    ├── test_alert_engine.py
    └── test_assistant.py
```

### Module responsibilities

**`simulator.py`**
- Maintains the list of four simulated devices (Front Door, Doorbell, Garage Door, Motion Sensor)
- Provides `make_event()`, `generate_random_event()`, `generate_n_random_events()`
- Four pre-built scenarios: `scenario_door_left_open`, `scenario_repeated_motion`,
  `scenario_quiet_hours_activity`, `scenario_normal_day`
- `get_device_status()` derives current state from event history

**`alert_engine.py`**
- Three independent rule functions: `check_door_open_too_long`, `check_repeated_motion`,
  `check_quiet_hours`
- `analyse_events()` runs all rules, deduplicates, and returns alerts sorted newest-first
- Thresholds are read from `data/config.json` (editable in the UI)

**`assistant.py`**
- Pattern-matching intent classifier (`_classify()`)
- Response builders keyed to each intent (status, events, alerts, quiet hours, help)
- `chat(message)` is the single public entry point
- Zero external dependencies — works fully offline

**`app.py`**
- Streamlit page config, custom CSS dark theme
- Five tabs rendered by dedicated `render_*()` functions
- Reads events and alerts fresh on every page interaction

---

## Simulated Devices

| Device ID | Display Name | Type |
|---|---|---|
| `front_door` | Front Door | Door sensor |
| `doorbell` | Doorbell | Doorbell / motion |
| `garage_door` | Garage Door | Door sensor |
| `motion_sensor` | Motion Sensor | Motion sensor |

---

## Quick Start (demo in 60 seconds)

1. `streamlit run app.py`
2. Open `http://localhost:8501` in your browser
3. Click **⚡ Event Simulator** → **🚪 Door Left Open**
4. Click **☀️ Normal Day** to add background events
5. Go to **🚨 Alert Engine** — you should see a medium-severity alert
6. Open **💬 Assistant** → type *"are there any alerts?"*
7. Switch to **🔍 Event Explorer** and filter by device or date

---

## Roadmap (Phase 2 — Strands Agents SDK + Bedrock)

- Replace the deterministic assistant with an LLM-powered agent via Strands Agents SDK
- Connect to Amazon Bedrock (Claude or Titan) for natural-language event summaries
- Add a Bedrock-powered anomaly scoring layer on top of the rule engine
- Optionally stream real Ring events via the Ring API (requires account + OAuth)

---

## Disclaimer

Ring Guardian AI is a hackathon demo project built by two CS undergraduates.
It is **not** affiliated with Ring LLC, Amazon.com, or any of their subsidiaries.
All device names, events, and alerts are entirely fictional and generated locally.
Do not use this application as a real security system.
