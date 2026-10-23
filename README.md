# 🛡️ Ring Guardian AI

A dark-themed Streamlit event-monitoring dashboard and hackathon demo. Local simulation is the default: synthetic device events flow through a canonical event store, deterministic alert rules, filters, and a grounded local assistant.

> **Honest status:** The local demo works without Ring hardware, Ring credentials, AWS credentials, or paid services. No real Ring account/API or Bedrock model is connected by default. The Ring adapter is opt-in scaffolding for an approved Ring Partner application; its status is not reported as verified merely because environment variables exist.

---

## Features

- **Modern dashboard** — dark UI with device status cards for Front Door, Doorbell, Garage Door, and Motion Sensor, plus live metrics: events today, active alerts, connected devices, and doors left open.
- **Event simulator** — one-click buttons generate example scenarios (normal entry, door left open, motion burst, doorbell press, overnight motion, random event). All events carry a `simulated` flag.
- **Unified event records** — synthetic events use a shared schema (`id`, `source`, device, type, timestamp, and attributes), while retaining compatibility fields used by the dashboard. Duplicate event IDs are ignored.
- **Garage-door threshold demo** — a deterministic demo button opens the garage door past the *currently configured* threshold (so it always alerts), with a **Reset** button to clear events and repeat the demonstration.
- **Alert engine** — deterministic, configurable rules that flag:
  - Doors open beyond a configurable threshold (default 5 minutes)
  - Repeated motion events within a short time window
  - Activity during configurable quiet hours

  Every alert carries a clear, plain-language explanation and the relevant timestamps, plus structured fields (e.g. `opened_at`, `duration_min`, `count`) for display/tooling. These are heuristic rules, **not** a reliable intrusion-detection system.
- **Event explorer** — filter by device, event type, and date range. All three filters combine (AND) through a single shared helper that is covered by tests.
- **Assistant chat** — a local, rule-based chat that answers questions about device status, event counts, recent activity, and alerts using real in-app data. No external LLM or AWS service is contacted. The logic lives behind a small `AssistantBackend` interface so it can be swapped for a Strands Agents SDK + Amazon Bedrock backend later without changing call sites.
- **Optional Ring Partner adapter** — server-side, opt-in client for the documented Users API (`GET /v1/users/me`) and device discovery (`GET /v1/devices`), OAuth authorization-code exchange/refresh, one-way nonce generation and required POST→PATCH account-link confirmation, partner-initiated PATCH completion, and signed webhook validation against the raw request body for documented event types. Live Ring mode remains disabled until app approval and required server-side settings are supplied. Login/account-claiming screens and a public HTTPS webhook service still require portal setup and deployment; this local dashboard is not a Ring-accessible webhook host.
- **Optional Strands + Bedrock provider** — loaded only when deliberately selected, optional dependencies are installed, an explicit model ID and region are set, and AWS credentials are available. The local assistant remains the fallback and alert decisions always stay deterministic.
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
Set-Location C:\Users\DELL\OneDrive\Desktop\ring_gaudrian_AI
python -m pip install -r requirements.txt
```

If `python` is not on `PATH`, use the full path to your installed Python executable in place of `python`.

## Run the dashboard

```powershell
python -m streamlit run app.py
```

Streamlit will print a local URL (usually <http://localhost:8501>) and open it in your browser automatically.

## Run the tests

```powershell
python -m pytest -q
```

The tests cover the simulator, alert engine, and assistant. They are pure Python and do not require Streamlit.

## Configuration

| What | Where |
|------|-------|
| Simulated devices | `data/devices.json` |
| Quiet hours & rule thresholds | `data/config.json` (also editable live in the sidebar) |
| Persisted events | `data/events.json` (auto-created) |

Adjust the quiet-hours window and the three rule thresholds in the sidebar, then click **Save configuration**. Changes take effect immediately on the next alert evaluation.

## Working now vs. external prerequisites

**Works locally now:** Streamlit dashboard; seeded and simulated events; random event generation; scenario controls and reset; canonical normalization; event persistence/filtering; deterministic door-open, repeated-motion, quiet-hours, and general-burst alerts; local assistant answers; offline tests.

**Requires Ring Partner access:** Developer registration and an approved/created Ring application, Ring-issued client ID/secret/HMAC key, Ring user consent and an access token, scopes and app URLs configured in the Developer Portal, plus a publicly reachable HTTPS webhook endpoint for actual deliveries. Public Appstore publication additionally requires Ring certification and approval. The adapter implements limited documented client calls and signature parsing, not the full account-linking portal workflow or deployed webhook service. Do not put credentials in chat, source control, or frontend code.

**Requires AWS/Bedrock access:** AWS account/credentials with Bedrock model permissions, an available model in the selected region, and the optional Strands dependencies. Install the optional packages only when needed:

```powershell
python -m pip install -r requirements-bedrock.txt
```

Set `ASSISTANT_BACKEND=bedrock`, `BEDROCK_ENABLED=true`, `BEDROCK_MODEL_ID` and `AWS_REGION` in the process environment after confirming model availability and AWS access. Missing setup falls back to the local assistant. The exact supported model IDs and authorization depend on your AWS account/region; the project intentionally does not invent a default model.

## Environment configuration and secrets

`.env.example` documents configuration names only. The project does not automatically load `.env`; set environment variables in PowerShell, your deployment environment, or a secrets manager. `.env` and token/credential files are ignored by Git. Never paste Ring or AWS secrets into Kiro prompts or the dashboard.

Ring settings: `RING_APP_APPROVED` (must be `true` to opt in), `RING_CLIENT_ID`, `RING_CLIENT_SECRET`, `RING_HMAC_SIGNING_KEY`, and `RING_ACCESS_TOKEN`. Approval is a deliberate operator assertion, not an API verification. The UI reports configuration status honestly and never prints values.

## Repeatable hackathon demo

1. Start locally with `python -m streamlit run app.py`.
2. Show the `SIMULATED DATA · NO REAL HARDWARE` label and Ring-disabled status.
3. Click **Reset** in Threshold demo, then **Run demo**; show the garage door alert and explanation.
4. Click **Motion burst** and ask “Were there repeated motion events?” in the local assistant.
5. Click **Generate Test Event** a few times, show the event explorer filters and device counts, then click **Reset** to demonstrate an empty clean state.

All generated demo activity is synthetic; no Ring or Bedrock connection is implied.

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
