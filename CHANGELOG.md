# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2024-10-01

### Added
- LangGraph state graph (gent.py) with 5 nodes and 2 conditional edges
- Open-Meteo geocoding + live forecast API wrapper (weather_service.py)
- Deterministic SOP evaluation engine (sop_engine.py) with severity ranking
- 11 production SOPs across 5 categories in declarative JSON format (sops.json)
- Streamlit chat frontend (pp.py) with session memory and weather data panel
- Evaluation suite (eval_suite.py) with 8 test cases — 100% pass rate
- MIT License
- CONTRIBUTING guide
- .env.example template for easy onboarding
- Comprehensive README with architecture diagrams, setup guide, and SOP documentation

### Design Decisions
- SOPs are stored as pure JSON data, fully decoupled from Python control flow
- LLM role is constrained: compose language only, never invent weather data or policies
- Honest failure modes: bot explicitly states when data is unavailable or no SOP matches
- Adversarial prompt injection resistance verified in eval suite (Test 6.0)
