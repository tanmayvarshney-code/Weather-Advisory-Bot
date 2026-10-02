# Weather Advisory Bot

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Powered-green)
![Groq LLM](https://img.shields.io/badge/LLM-Groq%20LLaMA--3.3--70B-orange)

A production-grade **Weather Advisory Bot** powered by a **LangGraph agent**, the **Open-Meteo live weather API**, **Groq LLM (LLaMA-3.3 70B)**, and **strictly grounded Standard Operating Procedures (SOPs)**.

The bot never invents weather forecasts or safety advice. Every response is grounded in real-time API data and written policy rules stored in `sops.json`.

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [LangGraph Graph Structure](#langgraph-graph-structure)
- [SOP Rule Set](#sop-rule-set)
- [Setup & Installation](#setup--installation)
- [Running the App](#running-the-app)
- [Evaluation Suite](#evaluation-suite)
- [Adding a New SOP](#adding-a-new-sop)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Live Weather Data** — Fetches real-time conditions (temperature, wind speed, UV index, precipitation, humidity) from the [Open-Meteo API](https://open-meteo.com/) using geocoding for any city worldwide.
- **Deterministic Safety Policies** — 11 SOPs across 5 categories govern all advice. Policies are stored as pure JSON (`sops.json`) — zero code changes needed to add, update, or remove a rule.
- **LangGraph State Graph** — Multi-node graph with conditional branching and session-level conversational memory (follow-up queries like *"What about this evening instead?"* work seamlessly).
- **Honest Failure Modes** — The bot explicitly states when weather data is unavailable or when no SOP applies. It never guesses or hallucinates.
- **Adversarial Prompt Injection Resistance** — Verified in the evaluation suite (Test 6.0).
- **Streamlit Chat UI** — Conversational frontend with live weather data panel and SOP citation display.

---

## Architecture Overview

### Design Principle: Hard Separation of Concerns

| Layer | Responsibility |
|-------|---------------|
| **`sops.json`** | Safety policy data — pure JSON, no code |
| **`sop_engine.py`** | Deterministic rule evaluation and severity ranking |
| **`weather_service.py`** | Open-Meteo geocoding + forecast API wrapper |
| **`agent.py`** | LangGraph state graph — orchestrates intent, weather, and SOP |
| **`app.py`** | Streamlit chat frontend |
| **`eval_suite.py`** | Automated evaluation suite — 8 test cases |

**The LLM's role is constrained:** it only composes natural language output from exact API weather numbers and the prescribed guidance of matched SOPs. It never invents weather forecasts or safety policies.

**SOPs are hot-reloadable:** editing `sops.json` takes effect immediately on the next query — no Python changes, no restart.

---

## LangGraph Graph Structure

```
               +--------------------------+
               |         (START)          |
               +------------+-------------+
                            |
               +------------v-------------+
               |   extract_intent_node    |  <- Parses location & activity
               +------------+-------------+   from conversation history
                            |
               +------------v-------------+
               |   fetch_weather_node     |  <- Open-Meteo Geocoding API
               +------------+-------------+     + Live Forecast API
                            |
              [route_after_weather?]
               /                        \
   (Success) /                           \ (API / Geocoding Error)
            v                             v
 +-------------------+       +------------------------+
 |  match_sop_node   |       |  render_weather_error  | -> [END]
 +--------+----------+       +------------------------+
          |
  [route_after_sop?]
   /               \
(Match)             (No Match)
  v                    v
+------------------------+  +------------------------+
| generate_sop_response  |  |     render_no_sop      | -> [END]
+----------+-------------+  +------------------------+
           |
           v
         [END]
```

### Graph Nodes

| Node | Description |
|------|-------------|
| `extract_intent_node` | Extracts `location` and `activity` from the current query and prior conversation history. Enables session context retention for follow-ups. |
| `fetch_weather_node` | Calls Open-Meteo Geocoding (`/v1/search`) and Forecast (`/v1/forecast`) APIs. Sanitizes city name inputs (strips quotes, punctuation). |
| `match_sop_node` | Evaluates all rules in `sops.json` against weather facts and user intent. Ranks by severity: `CRITICAL > HIGH > MEDIUM > LOW`. |
| `generate_sop_response` | LLM composes a grounded response citing exact weather stats and SOP policy reference. |
| `render_weather_error` | Returns an honest failure message when the API or geocoding fails — no hallucinated forecast. |
| `render_no_sop` | Returns an honest "no policy" message when no SOP matches — never invents generic advice. |

### Conditional Edges

| Edge | Condition | Routes To |
|------|-----------|-----------|
| `route_after_weather` | Weather fetch success | `match_sop_node` |
| `route_after_weather` | Geocoding / API error | `render_weather_error` |
| `route_after_sop` | SOP match found | `generate_sop_response` |
| `route_after_sop` | No SOP matches | `render_no_sop` |

---

## SOP Rule Set

The rule set contains **11 SOPs** across **5 categories**, all stored in [`sops.json`](sops.json):

| Category | SOP ID | Trigger Condition |
|----------|--------|-------------------|
| **System-Wide Override** | `SOP-SYS-001` | Severe low-pressure / cyclonic storm (overrides all activity rules) |
| **Outdoor Exercise** | `SOP-EX-001` | UV Index >= 8 |
| **Outdoor Exercise** | `SOP-EX-002` | Extreme heat >= 38°C |
| **Outdoor Exercise** | `SOP-EX-003` | High wind for cycling / two-wheelers > 40 km/h |
| **Outdoor Exercise** | `SOP-EX-004` | Moderate rain — trail caution |
| **Travel & Commute** | `SOP-TR-001` | High rain probability > 70% |
| **Travel & Commute** | `SOP-TR-002` | Gale gust road travel > 60 km/h |
| **Vulnerable Groups** | `SOP-VG-001` | Cold exposure for children/elderly/pets <= 5°C |
| **Vulnerable Groups** | `SOP-VG-002` | Heat & UV protection for children/elderly >= 35°C |
| **Water & Marine** | `SOP-WS-001` | High wind on open water > 30 km/h |
| **Fuzzy/Non-Numeric** | `SOP-FZ-001` | Outdoor picnic/gathering suitability (composite: rain + cloud + wind) |

---

## Setup & Installation

### Prerequisites

- Python 3.10+
- A free [Groq API key](https://console.groq.com/)

### Step 1 — Clone the Repository

```bash
git clone https://github.com/tanmayvarshney-code/Weather-Advisory-Bot.git
cd Weather-Advisory-Bot
```

### Step 2 — Create the Environment File

Copy the template and add your Groq API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Running the App

### Streamlit Chat Frontend

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

**Example queries:**
- *"Is it safe to go cycling in Mumbai right now?"*
- *"Should I take my toddler for a walk in Delhi today?"*
- *"Is the weather okay for a picnic in Bangalore?"*
- *"Can I go kayaking in Chennai?"*

---

## Evaluation Suite

Run the full automated evaluation suite:

```bash
python eval_suite.py
```

### Test Results

| Test | Description | Result |
|------|-------------|--------|
| **1.1** | Standard SOP match — High UV cycling (UV=9.5, Bhopal) | `PASS` |
| **1.2** | Standard SOP match — High wind cycling (Wind=46 km/h, Mumbai) | `PASS` |
| **2.1** | Paraphrased intent — *"pedal push midday"* | `PASS` |
| **2.2** | Paraphrased intent — Toddler stroll in 37.5°C heat | `PASS` |
| **3.0** | Severe weather system with real API numbers (rain=18.5 mm) | `PASS` |
| **4.0** | No SOP applies — Indoor chess | `PASS` |
| **5.0** | Unreachable API / invalid location | `PASS` |
| **6.0** | Adversarial prompt injection resistance | `PASS` |

> **Note on weather variability:** Regional conditions (e.g. monsoon systems) change daily. The suite uses simulated payload overrides alongside live API calls to guarantee deterministic results for severe-weather SOP verification regardless of actual real-time conditions.

---

## Adding a New SOP

No code changes are required. Simply edit `sops.json`:

1. Open `sops.json`
2. Add a new JSON object to the `"sops"` array following the existing schema
3. Save the file

The `sop_engine.py` reloads `sops.json` dynamically on every query. **Zero restart or code edits required.**

**Example SOP schema:**

```json
{
  "id": "SOP-EX-005",
  "category": "outdoor_exercise",
  "severity": "MEDIUM",
  "title": "High Humidity Warning",
  "description": "Relative humidity above 85% makes outdoor exercise uncomfortable and potentially dangerous.",
  "conditions": {
    "relative_humidity_2m": { "gte": 85 }
  },
  "keywords": ["exercise", "run", "jog", "walk", "outdoor"],
  "advice": "High humidity detected. Take frequent breaks, stay hydrated, and prefer early morning or late evening exercise."
}
```

---

## Project Structure

```
Weather-Advisory-Bot/
├── agent.py            # LangGraph state graph — core agent logic
├── app.py              # Streamlit chat frontend
├── eval_suite.py       # Automated evaluation suite (8 test cases)
├── sop_engine.py       # Deterministic SOP evaluation engine
├── sops.json           # SOP policy data (11 rules, 5 categories)
├── weather_service.py  # Open-Meteo API wrapper (geocoding + forecast)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── CONTRIBUTING.md     # Contribution guide
├── CHANGELOG.md        # Release history
└── LICENSE             # MIT License
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. In short:

1. Fork the repo and create a branch: `git checkout -b feat/your-feature`
2. Install dependencies and copy `.env.example` to `.env`
3. Make your changes
4. Run `python eval_suite.py` — all 8 tests must pass
5. Open a pull request with a clear description

---

## License

This project is licensed under the [MIT License](LICENSE).
