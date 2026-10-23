# 🛡️ Ring Guardian AI

### **See the signal. Understand the event.**

A polished, dark-mode **Streamlit security-event dashboard** built for a hackathon demo. Generate realistic *synthetic* smart-home activity, watch deterministic rules raise explainable alerts, and ask the local assistant what happened — all without paid services.

<p align="center">
  <strong>🎭 Local-first</strong> &nbsp; • &nbsp;
  <strong>🧪 Fully simulated</strong> &nbsp; • &nbsp;
  <strong>🔒 No secrets required</strong> &nbsp; • &nbsp;
  <strong>☁️ No AWS required</strong>
</p>

> [!IMPORTANT]
> **Demo status:** Local simulation is the default. This project does **not** claim a live Ring API, Ring device, or Bedrock connection. The Ring adapter is opt-in and requires an approved Ring Partner application and valid server-side credentials. The local dashboard works without those prerequisites.

---

## ✨ What you can do

| | Feature | What it does |
|:--:|---|---|
| 📊 | **Live dashboard** | See device status cards, event counts, active alerts, and doors left open. |
| 🎛️ | **Scenario simulator** | Generate normal entry, a door left open, motion bursts, doorbell presses, overnight activity, or random events. |
| 🎲 | **Random event button** | Add a single synthetic event on demand; normal Streamlit reruns do not create duplicates. |
| 🚨 | **Explainable alert rules** | Detect long-open doors, repeated motion, quiet-hours activity, and general event bursts. Alerts include rule IDs, explanations, timestamps, and related event IDs. |
| 🔎 | **Event explorer** | Combine device, event-type, and date filters to inspect activity. |
| 💬 | **Local assistant** | Ask about the last five events, triggered alerts, quiet-hours activity, repeated motion, or the busiest devices. It uses current app data, not an external AI model. |
| 💾 | **Local persistence** | Keep simulated events in `data/events.json` between page refreshes. |
| 🔌 | **Optional integration adapters** | Prepare for documented Ring Partner APIs and an optional Strands + Bedrock assistant. Both stay disabled unless deliberately configured. |

### 🚀 Quick start — Windows PowerShell

```powershell
Set-Location C:\Users\DELL\OneDrive\Desktop\ring_gaudrian_AI
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL Streamlit prints (usually <http://localhost:8501>). If `python` is not on `PATH`, use the full path to your Python executable, for example `& "C:\Python314\python.exe" -m streamlit run app.py`.

### 🧪 Run the tests

```powershell
python -m pytest -q
```

The test suite is offline and needs no Ring credentials, AWS credentials, or hardware.

---

## 🎬 Hackathon demo: a 60-second walkthrough

1. Start the app and point out **SIMULATED DATA · NO REAL HARDWARE**.
2. In **🧪 Threshold demo**, click **🔄 Reset**, then **▶️ Run demo**. Show the deterministic garage-door alert and its explanation.
3. Click **📡 Motion burst**, then ask the assistant: **“Were there repeated motion events?”**
4. Use **🎲 Generate Test Event** and the event explorer to show changing counts and filters.
5. Click **🔄 Reset** to clear the event history and start fresh.

Everything in this walkthrough is synthetic; nothing contacts Ring or Bedrock.

---

## 🧠 How the app works

1. The event store loads local device/configuration JSON and seeds sample events on first run.
2. Scenario controls and random generation create canonical records with `id`, `source`, device, event type, timestamp, and attributes. Existing display fields are retained for compatibility.
3. Deterministic alert rules evaluate the current event history. An LLM never decides whether an alert triggers.
4. The dashboard, filters, and local assistant all read the same event and alert data.
5. Adding an event is tied to a user action and duplicate IDs are ignored, avoiding rerun-generated duplicates.

### 🚨 Alert rules

- **Door open too long** — severity reflects whether the door remains open or was closed after exceeding the threshold.
- **Repeated motion** — detects a configurable number of motion events within a time window.
- **Quiet-hours activity** — flags events inside the configured quiet-hours window.
- **General event burst** — detects unusually high event volume from one device in a configurable interval.

These are transparent demo heuristics—not a reliable intrusion-detection or life-safety system.

### 💬 Assistant examples

- “Summarize the last five events.”
- “Why did the door-open alert trigger?”
- “Were there repeated motion events?”
- “What happened during quiet hours?”
- “Which devices generated the most events?”

The default assistant is deterministic and local. It clearly reports when event or alert data is missing.

---

## 🧰 Project map

```
ring_gaudrian_AI/
├── .streamlit/
│   └── config.toml          # Dark theme + server settings
├── app.py                   # Streamlit dashboard (UI + wiring)
├── event_schema.py          # Shared event normalization and validation
├── simulator.py             # Simulated events + scenario generators
├── alert_engine.py          # Deterministic alert rules
├── assistant.py             # Local assistant + optional provider interface
├── ring_connector.py        # Disabled-by-default Ring Partner API adapter
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
├── requirements-bedrock.txt # Optional Strands/Bedrock dependencies
├── .env.example             # Placeholder configuration only
└── README.md
```

---

## ⚙️ Configuration

| Setting | Location |
|---|---|
| Simulated devices | `data/devices.json` |
| Quiet hours and alert thresholds | `data/config.json` or the dashboard sidebar |
| Persisted simulated events | `data/events.json` (created automatically) |
| Placeholder environment variable names | `.env.example` |

Change the quiet-hours window or alert thresholds in the sidebar and select **💾 Save configuration**. Local environment variables should be set in PowerShell or a secrets manager; the project does not automatically load `.env`.

### 🔐 Secrets stay private

`.env`, token files, and credential-like files are ignored by Git. Never paste credentials into chat/Kiro prompts, commit them, or expose them in frontend code. The `.env.example` file contains placeholders only.

---

## 🧩 Optional integrations — prerequisites apply

### Ring Partner API

The separate server-side adapter is **disabled by default**. It contains documented client operations for the Users API, device discovery, OAuth token exchange/refresh, account-link helper calls, and signature verification for documented webhook events. This is not a complete hosted integration: the local Streamlit app is not a public HTTPS webhook endpoint, and account-linking UI/token storage still need deployment work.

Real Ring access requires developer registration, an approved/created Ring application, Ring-issued credentials, customer consent and an authorized user token, correct scopes/URLs in the Developer Portal, and a publicly reachable HTTPS webhook service for deliveries. Public Appstore distribution additionally requires certification. The dashboard status is informational; configured variables do not prove that Ring access works.

Supported server-side variable names are listed in `.env.example`: `RING_APP_APPROVED`, `RING_CLIENT_ID`, `RING_CLIENT_SECRET`, `RING_HMAC_SIGNING_KEY`, and `RING_ACCESS_TOKEN`. Set approval to `true` only after approval is confirmed. Do not log or display secret values.

### Strands + Amazon Bedrock

The local assistant remains the default. To install the optional provider dependencies:

```powershell
python -m pip install -r requirements-bedrock.txt
```

Then explicitly configure `ASSISTANT_BACKEND=bedrock`, `BEDROCK_ENABLED=true`, `BEDROCK_MODEL_ID`, `AWS_REGION`, and valid AWS credentials with access to the selected Bedrock model. The model ID is intentionally not guessed. Missing dependencies/credentials or provider errors fall back gracefully to local mode. Alert decisions always remain deterministic.

---

## 📋 Requirements

- Windows 10 / 11
- Python 3.10+
- PowerShell
