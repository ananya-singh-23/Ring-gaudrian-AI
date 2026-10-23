# 🛡️ Ring Guardian AI

A polished, dark-themed **smart-home security event monitoring dashboard** inspired by Ring devices. Built as a one-day hackathon project.

> ⚠️ **All devices and events are SIMULATED.** This application does **not** connect to real Ring hardware, does **not** use real Ring credentials, and does **not** require an AWS account. The assistant is a deterministic local rules engine. Integration with the Strands Agents SDK and Amazon Bedrock is planned for a later phase.

---

## Features

- **Modern dashboard** — dark UI with device status cards for Front Door, Doorbell, Garage Door, and Motion Sensor, plus live metrics: events today, active alerts, connected devices, and doors left open.
- **Event simulator** — one-click buttons generate example scenarios (normal entry, door left open, motion burst, doorbell press, overnight motion, random event). All events carry a `simulated` flag.
- **Garage-door threshold demo** — a deterministic demo button opens the garage door past the *currently configured* threshold (so it always alerts), with a **Reset** button to clear events and repeat the demonstration.
- **Alert engine** — deterministic, configurable rules that flag:
  - Doors open beyond a configurable threshold (default 5 minutes)
  - Repeated motion events within a short time window
  - Activity during configurable quiet hours

  Every alert carries a clear, plain-language explanation and the relevant timestamps, plus structured fields (e.g. `opened_at`, `duration_min`, `count`) for display/tooling. These are heuristic rules, **not** a reliable intrusion-detection system.
- **Event explorer** — filter by device, event type, and date range. All three filters combine (AND) through a single shared helper that is covered by tests.
- **Assistant chat** — a local, rule-based chat that answers questions about device status, event counts, recent activity, and alerts using real in-app data. No external LLM or AWS service is contacted. The logic lives behind a small `AssistantBackend` interface so it can be swapped for a Strands Agents SDK + Amazon Bedrock backend later without changing call sites.
- **Persistence** — simulated events are saved to `data/events.json` so they survive page reloads.
- **Tests** — basic `pytest` suite for the simulator, alert engine, and assistant.

## Project structure

```
ring_gaudrian_AI/
├── .streamlit/
│   └── config.toml          # Dark theme + server settings
├── app.py                   # Streamlit dashboard (UI + wiring)
├── simulator.py             # Simulated events + scenario generators
├── alert_engine.py          # Deterministic alert rules
├── assistant.py             # Local rule-based chat assistant
├── state.py                 # Session state + JSON persistence
├── utils.py                 # Shared helpers (no third-party deps)
├── conftest.py              # Makes root modules importable to pytest
├── data/
│   ├── devices.json         # Simulated device definitions
│   ├── config.json          # Quiet hours + rule thresholds (configurable)
│   └── events.json          # Persisted simulated events (auto-created)
├── tests/
│   ├── test_simulator.py
│   ├── test_alert_engine.py
│   ├── test_filters.py
│   ├── test_demo.py
│   └── test_assistant.py
├── requirements.txt
└── README.md
```

## Requirements

- Windows 10 / 11
- Python 3.10+ (tested with Python 3.14 via the Windows `py` launcher)
- PowerShell

## Installation (Windows)

Open PowerShell and run:

```powershell
cd C:\Users\DELL\OneDrive\Desktop\ring_gaudrian_AI
py -m pip install -r requirements.txt
```

> If `py` is not recognized, install the Python launcher (bundled with the official python.org installer) or replace `py` with your `python` executable.

## Run the dashboard

```powershell
py -m streamlit run app.py
```

Streamlit will print a local URL (usually <http://localhost:8501>) and open it in your browser automatically.

## Run the tests

```powershell
py -m pytest -q
```

The tests cover the simulator, alert engine, and assistant. They are pure Python and do not require Streamlit.

## Configuration

| What | Where |
|------|-------|
| Simulated devices | `data/devices.json` |
| Quiet hours & rule thresholds | `data/config.json` (also editable live in the sidebar) |
| Persisted events | `data/events.json` (auto-created) |

Adjust the quiet-hours window and the three rule thresholds in the sidebar, then click **Save configuration**. Changes take effect immediately on the next alert evaluation.

## Garage-door threshold demo

In the sidebar, under **🧪 Threshold demo**:

1. Click **▶️ Run demo**. It generates a single garage-door `door_open` event opened `threshold + 3` minutes ago, so it always exceeds the *currently configured* threshold and raises a `door_open_too_long` alert (visible in the Active alerts panel and reflected in the metrics).
2. Click **🔄 Reset** to clear all events so you can run the demo again. This is the same as "Clear all events" but is grouped with the demo for convenience.

The demo is deterministic for a given configuration (no randomness, no clock jitter), which makes it reliable for screenshots and live presentations.

## How it works

1. On startup, `state.py` loads devices and config from JSON and (re)seeds a few sample events if none exist.
2. The sidebar lets you generate simulated scenarios and configure rules.
3. `alert_engine.evaluate()` runs the three deterministic rules over the full event history on every render.
4. The dashboard shows metrics, device cards, an activity timeline, active alerts, a filterable event table, and the chat.
5. The assistant routes a question by keywords and answers using the same in-memory events, device states, and alerts.

## Notes & limitations

- Everything is simulated and labeled as such throughout the UI.
- The alert rules are intentionally simple heuristics for demonstration, not a security product.
- Data is stored as local JSON files; no cloud, database, or network calls are made.

## Roadmap (not in this version)

- Strands Agents SDK + Amazon Bedrock integration: implement a `BedrockAssistant(AssistantBackend)` and return it from `assistant.build_assistant()` (e.g. gated on an environment variable). The call sites in `app.py` already use the `AssistantBackend` interface, so no UI changes will be needed.
- More device types and richer event schemas.
