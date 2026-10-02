"""
app.py
------
Streamlit chat frontend for the Weather Advisory Bot.
Modern UI with glassmorphism, animated gradients, rich weather cards,
SOP severity badges, and a premium dark-mode design system.
"""
import os
import json
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

from agent import WeatherAdvisoryAgent
from sop_engine import SOPEngine
from weather_service import fetch_live_weather

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weather Advisory Bot",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv(override=True)

# ── Session state ───────────────────────────────────────────────────────────────
for key, default in {
    "messages": [],
    "chat_history_langchain": [],
    "last_location": None,
    "last_activity": None,
    "pending_query": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Design System / CSS ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Global reset & base ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background: linear-gradient(135deg, #0f0c29 0%, #1a1a2e 40%, #16213e 70%, #0f3460 100%);
    min-height: 100vh;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* ── Hero Header ── */
.hero-wrapper {
    background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(14,165,233,0.10) 100%);
    border: 1px solid rgba(99,102,241,0.25);
    border-radius: 20px;
    padding: 2rem 2.5rem 1.5rem;
    margin-bottom: 1.8rem;
    backdrop-filter: blur(16px);
    position: relative;
    overflow: hidden;
}
.hero-wrapper::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 220px; height: 220px;
    background: radial-gradient(circle, rgba(99,102,241,0.25) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-title {
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #e0e7ff 0%, #818cf8 50%, #38bdf8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 0.4rem 0;
    line-height: 1.2;
}
.hero-subtitle {
    font-size: 0.95rem;
    color: rgba(148,163,184,0.9);
    margin: 0;
    font-weight: 400;
    letter-spacing: 0.02em;
}
.hero-pills {
    display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 1.1rem;
}
.hero-pill {
    background: rgba(99,102,241,0.15);
    border: 1px solid rgba(99,102,241,0.3);
    color: #a5b4fc;
    padding: 0.25rem 0.75rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 500;
}

/* ── Chat message bubbles ── */
[data-testid="stChatMessage"] {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 16px !important;
    margin-bottom: 0.75rem !important;
    backdrop-filter: blur(8px);
    padding: 0.25rem 0.5rem !important;
}
[data-testid="stChatMessage"][data-testid*="user"] {
    background: rgba(99,102,241,0.12) !important;
    border-color: rgba(99,102,241,0.25) !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] textarea {
    background: rgba(255,255,255,0.06) !important;
    border: 1.5px solid rgba(99,102,241,0.35) !important;
    border-radius: 14px !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.95rem !important;
    padding: 0.9rem 1.1rem !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(99,102,241,0.7) !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.15) !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: rgba(148,163,184,0.6) !important; }

/* ── Weather info card ── */
.weather-fact-card {
    background: linear-gradient(135deg, rgba(14,165,233,0.12) 0%, rgba(56,189,248,0.08) 100%);
    border: 1px solid rgba(56,189,248,0.25);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    margin-top: 0.8rem;
    display: flex; flex-wrap: wrap; gap: 1rem; align-items: center;
}
.weather-fact-title {
    font-size: 0.7rem; font-weight: 700; letter-spacing: 0.1em;
    text-transform: uppercase; color: #38bdf8; margin-bottom: 0.5rem;
    width: 100%;
}
.weather-stat {
    display: flex; flex-direction: column; align-items: center;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 0.5rem 0.9rem;
    min-width: 80px;
}
.weather-stat-icon { font-size: 1.3rem; margin-bottom: 0.1rem; }
.weather-stat-value { font-size: 1.0rem; font-weight: 700; color: #e2e8f0; }
.weather-stat-label { font-size: 0.65rem; color: rgba(148,163,184,0.7); text-transform: uppercase; letter-spacing: 0.05em; }

/* ── SOP citation banner ── */
.sop-citation {
    background: linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(139,92,246,0.08) 100%);
    border: 1px solid rgba(139,92,246,0.3);
    border-left: 4px solid #8b5cf6;
    border-radius: 10px;
    padding: 0.65rem 1rem;
    margin-top: 0.6rem;
    font-size: 0.8rem;
    color: #c4b5fd;
    font-weight: 500;
}

/* ── Severity badges ── */
.badge-critical {
    display: inline-flex; align-items: center; gap: 0.3rem;
    background: rgba(239,68,68,0.15); color: #fca5a5;
    border: 1px solid rgba(239,68,68,0.35);
    padding: 0.25rem 0.7rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
}
.badge-high {
    display: inline-flex; align-items: center; gap: 0.3rem;
    background: rgba(249,115,22,0.15); color: #fdba74;
    border: 1px solid rgba(249,115,22,0.35);
    padding: 0.25rem 0.7rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
}
.badge-medium {
    display: inline-flex; align-items: center; gap: 0.3rem;
    background: rgba(234,179,8,0.15); color: #fde047;
    border: 1px solid rgba(234,179,8,0.35);
    padding: 0.25rem 0.7rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
}
.badge-low {
    display: inline-flex; align-items: center; gap: 0.3rem;
    background: rgba(59,130,246,0.15); color: #93c5fd;
    border: 1px solid rgba(59,130,246,0.35);
    padding: 0.25rem 0.7rem; border-radius: 999px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15,12,41,0.98) 0%, rgba(22,33,62,0.98) 100%) !important;
    border-right: 1px solid rgba(99,102,241,0.2) !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: rgba(99,102,241,0.12) !important;
    border: 1px solid rgba(99,102,241,0.3) !important;
    color: #a5b4fc !important;
    border-radius: 10px !important;
    font-size: 0.8rem !important;
    font-family: 'Inter', sans-serif !important;
    text-align: left !important;
    transition: all 0.2s ease;
    padding: 0.5rem 0.75rem !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(99,102,241,0.25) !important;
    border-color: rgba(99,102,241,0.55) !important;
    color: #e0e7ff !important;
    transform: translateX(3px);
}

/* clear button special */
.clear-btn > button {
    background: rgba(239,68,68,0.12) !important;
    border-color: rgba(239,68,68,0.3) !important;
    color: #fca5a5 !important;
}
.clear-btn > button:hover {
    background: rgba(239,68,68,0.22) !important;
    border-color: rgba(239,68,68,0.55) !important;
    color: #fecaca !important;
    transform: none !important;
}

/* Sidebar text colors */
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stSubheader {
    color: #e2e8f0 !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label, [data-testid="stSidebar"] .stCaption {
    color: rgba(148,163,184,0.85) !important;
}
[data-testid="stSidebar"] .stDivider { border-color: rgba(99,102,241,0.2) !important; }

/* sidebar logo card */
.sidebar-logo {
    background: linear-gradient(135deg, rgba(99,102,241,0.2), rgba(56,189,248,0.15));
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 16px;
    padding: 1.2rem;
    text-align: center;
    margin-bottom: 1rem;
}
.sidebar-logo-icon { font-size: 2.8rem; }
.sidebar-logo-title {
    font-size: 1.0rem; font-weight: 700;
    color: #e0e7ff; margin-top: 0.4rem;
}
.sidebar-logo-sub { font-size: 0.72rem; color: rgba(148,163,184,0.7); margin-top: 0.15rem; }

/* ── SOP rule cards in sidebar ── */
.sop-rule-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    padding: 0.6rem 0.8rem;
    margin-bottom: 0.5rem;
}
.sop-rule-id { font-size: 0.65rem; font-weight: 700; color: #818cf8; letter-spacing: 0.08em; text-transform: uppercase; }
.sop-rule-title { font-size: 0.8rem; font-weight: 600; color: #e2e8f0; margin-top: 0.1rem; }

/* ── Spinner text ── */
[data-testid="stSpinner"] p { color: #a5b4fc !important; font-size: 0.85rem !important; }

/* ── General text ── */
.stMarkdown p, .stMarkdown li { color: #cbd5e1 !important; line-height: 1.7; }
.stMarkdown strong { color: #e2e8f0 !important; }
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #e2e8f0 !important; }

/* ── Alert/info boxes ── */
[data-testid="stAlert"] { border-radius: 12px !important; }

/* ── Expander ── */
[data-testid="stExpander"] {
    background: rgba(255,255,255,0.03) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary { color: #a5b4fc !important; font-size: 0.85rem !important; }

/* ── Status dot ── */
.status-dot-online {
    display: inline-block; width: 8px; height: 8px;
    background: #22c55e; border-radius: 50%;
    box-shadow: 0 0 6px #22c55e;
    margin-right: 0.4rem;
    animation: pulse-green 2s infinite;
}
@keyframes pulse-green {
    0%, 100% { opacity: 1; } 50% { opacity: 0.5; }
}

/* ── Empty state ── */
.empty-state {
    text-align: center; padding: 3.5rem 1rem;
    opacity: 0.7;
}
.empty-state-icon { font-size: 4rem; margin-bottom: 1rem; }
.empty-state-title { font-size: 1.2rem; font-weight: 600; color: #94a3b8; }
.empty-state-sub { font-size: 0.85rem; color: rgba(148,163,184,0.6); margin-top: 0.4rem; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.4); border-radius: 999px; }
</style>
""", unsafe_allow_html=True)

# ── Hero Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-wrapper">
  <div class="hero-title">🌤️ Weather Advisory Bot</div>
  <div class="hero-subtitle">
    Real-time outdoor safety guidance &mdash; grounded in live weather data and strict SOP policies.
    Powered by LangGraph &amp; Groq LLaMA-3.3 70B.
  </div>
  <div class="hero-pills">
    <span class="hero-pill">⚡ Live Open-Meteo API</span>
    <span class="hero-pill">🧠 LangGraph Agent</span>
    <span class="hero-pill">📜 11 SOP Rules</span>
    <span class="hero-pill">🔒 Prompt-Injection Resistant</span>
    <span class="hero-pill">💬 Session Memory</span>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo card
    st.markdown("""
    <div class="sidebar-logo">
      <div class="sidebar-logo-icon">🌦️</div>
      <div class="sidebar-logo-title">Weather Advisory Bot</div>
      <div class="sidebar-logo-sub">LangGraph · Groq · Open-Meteo</div>
    </div>
    """, unsafe_allow_html=True)

    # API Key Status
    groq_key = (os.getenv("GROQ_API_KEY") or "").strip().strip('"').strip("'")
    api_ok = groq_key and groq_key != "your_groq_api_key_here"
    if api_ok:
        st.markdown('<span class="status-dot-online"></span> **Groq API** connected', unsafe_allow_html=True)
    else:
        st.error("⚠️ Groq API Key missing! Add `GROQ_API_KEY` to your `.env` file.")

    st.divider()

    # Clear session
    st.markdown("**Session**")
    col_clear, col_count = st.columns([2, 1])
    with col_clear:
        with st.container():
            st.markdown('<div class="clear-btn">', unsafe_allow_html=True)
            if st.button("🗑️ Clear Chat", use_container_width=True):
                st.session_state.messages = []
                st.session_state.chat_history_langchain = []
                st.session_state.last_location = None
                st.session_state.last_activity = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    with col_count:
        n = len(st.session_state.messages)
        st.markdown(f"<div style='text-align:center;padding-top:0.45rem;font-size:0.75rem;color:#64748b'>{n} msg{'s' if n!=1 else ''}</div>", unsafe_allow_html=True)

    # Session context
    if st.session_state.last_location or st.session_state.last_activity:
        st.caption("**Active context**")
        if st.session_state.last_location:
            st.caption(f"📍 Location: `{st.session_state.last_location}`")
        if st.session_state.last_activity:
            st.caption(f"🏃 Activity: `{st.session_state.last_activity}`")

    st.divider()

    # Quick queries
    st.markdown("**💡 Try These Queries**")
    sample_queries = [
        "Is it safe to cycle today in Bhopal around 1 PM?",
        "Can I ride my bike in Mumbai right now?",
        "Should I take my toddler to the park in Delhi?",
        "Is it safe for a picnic in Bangalore today?",
        "Can I go kayaking in Chennai?",
        "Is indoor chess in London weather-safe?",
    ]
    for sq in sample_queries:
        if st.button(f"↗  {sq}", use_container_width=True):
            st.session_state.pending_query = sq
            st.rerun()

    st.divider()

    # SOP inspector
    st.markdown("**📜 Loaded SOP Policies**")
    try:
        sop_engine_sidebar = SOPEngine("sops.json")
        n_sops = len(sop_engine_sidebar.sops)
        st.caption(f"<span class='status-dot-online'></span> {n_sops} rules active from `sops.json`", unsafe_allow_html=True)

        severity_colors = {
            "CRITICAL": "#ef4444", "HIGH": "#f97316",
            "MEDIUM": "#eab308", "LOW": "#3b82f6"
        }
        with st.expander(f"Inspect all {n_sops} SOP rules"):
            for sop in sop_engine_sidebar.sops:
                sev = sop.get("severity", "LOW")
                color = severity_colors.get(sev, "#6366f1")
                st.markdown(f"""
                <div class="sop-rule-card">
                  <div class="sop-rule-id">{sop['id']} &nbsp;·&nbsp; <span style="color:{color}">{sev}</span></div>
                  <div class="sop-rule-title">{sop['title']}</div>
                </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"SOP load error: {e}")

# ── Handle pending query from sidebar buttons ──────────────────────────────────
user_input = None
if st.session_state.pending_query:
    user_input = st.session_state.pending_query
    st.session_state.pending_query = None

# ── Render existing chat history ───────────────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="empty-state">
      <div class="empty-state-icon">💬</div>
      <div class="empty-state-title">Ask about outdoor safety</div>
      <div class="empty-state-sub">
        e.g. "Is it safe to cycle in Mumbai today?" or pick a query from the sidebar.
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Weather fact card
            w = msg.get("weather_info")
            if w:
                loc = w.get("location_name", "")
                st.markdown(f"""
                <div class="weather-fact-card">
                  <div class="weather-fact-title">📡 Verified Live Weather · {loc}</div>
                  <div class="weather-stat">
                    <span class="weather-stat-icon">🌡️</span>
                    <span class="weather-stat-value">{w.get('temperature_2m', '--')}°C</span>
                    <span class="weather-stat-label">Temp</span>
                  </div>
                  <div class="weather-stat">
                    <span class="weather-stat-icon">💨</span>
                    <span class="weather-stat-value">{w.get('wind_speed_10m', '--')}</span>
                    <span class="weather-stat-label">Wind km/h</span>
                  </div>
                  <div class="weather-stat">
                    <span class="weather-stat-icon">🌧️</span>
                    <span class="weather-stat-value">{w.get('precipitation', '--')} mm</span>
                    <span class="weather-stat-label">Rain</span>
                  </div>
                  <div class="weather-stat">
                    <span class="weather-stat-icon">☀️</span>
                    <span class="weather-stat-value">{w.get('uv_index', '--')}</span>
                    <span class="weather-stat-label">UV Index</span>
                  </div>
                  <div class="weather-stat">
                    <span class="weather-stat-icon">💧</span>
                    <span class="weather-stat-value">{w.get('relative_humidity_2m', '--')}%</span>
                    <span class="weather-stat-label">Humidity</span>
                  </div>
                  <div class="weather-stat">
                    <span class="weather-stat-icon">🌬️</span>
                    <span class="weather-stat-value">{w.get('wind_gusts_10m', '--')}</span>
                    <span class="weather-stat-label">Gusts km/h</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            # SOP citation
            citation = msg.get("sop_citation")
            if citation:
                st.markdown(f'<div class="sop-citation">📜 Policy Reference &nbsp;·&nbsp; {citation}</div>',
                            unsafe_allow_html=True)

# ── Chat input ─────────────────────────────────────────────────────────────────
chat_input = st.chat_input("Ask about outdoor safety (e.g. 'Is it safe to go running in Delhi today?')")
if chat_input:
    user_input = chat_input

# ── Process user input ─────────────────────────────────────────────────────────
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.chat_history_langchain.append(HumanMessage(content=user_input))

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Fetching live weather & evaluating SOP policies..."):
            try:
                agent = WeatherAdvisoryAgent(sops_file_path="sops.json")
                out = agent.run(
                    user_query=user_input,
                    history=st.session_state.chat_history_langchain,
                    location=st.session_state.last_location,
                    activity=st.session_state.last_activity,
                )

                if out.get("location"):
                    st.session_state.last_location = out["location"]
                if out.get("activity"):
                    st.session_state.last_activity = out["activity"]

                resp_text    = out.get("final_response", "No response generated.")
                weather_facts = out.get("weather_data")
                citation     = out.get("sop_citation")
                matched_sop  = out.get("sop_matched")

                # Response text
                st.markdown(resp_text)

                # Severity badge for matched SOP
                if matched_sop:
                    sev = matched_sop.get("severity", "LOW").upper()
                    badge_map = {
                        "CRITICAL": ("badge-critical", "🔴"),
                        "HIGH":     ("badge-high",     "🟠"),
                        "MEDIUM":   ("badge-medium",   "🟡"),
                        "LOW":      ("badge-low",      "🔵"),
                    }
                    cls, icon = badge_map.get(sev, ("badge-low", "🔵"))
                    sop_id = matched_sop.get("id", "")
                    st.markdown(
                        f'<span class="{cls}">{icon} {sev} &nbsp;·&nbsp; {sop_id}</span>',
                        unsafe_allow_html=True
                    )

                # Rich weather card
                if weather_facts:
                    loc = weather_facts.get("location_name", "")
                    st.markdown(f"""
                    <div class="weather-fact-card">
                      <div class="weather-fact-title">📡 Verified Live Weather · {loc}</div>
                      <div class="weather-stat">
                        <span class="weather-stat-icon">🌡️</span>
                        <span class="weather-stat-value">{weather_facts.get('temperature_2m', '--')}°C</span>
                        <span class="weather-stat-label">Temp</span>
                      </div>
                      <div class="weather-stat">
                        <span class="weather-stat-icon">💨</span>
                        <span class="weather-stat-value">{weather_facts.get('wind_speed_10m', '--')}</span>
                        <span class="weather-stat-label">Wind km/h</span>
                      </div>
                      <div class="weather-stat">
                        <span class="weather-stat-icon">🌧️</span>
                        <span class="weather-stat-value">{weather_facts.get('precipitation', '--')} mm</span>
                        <span class="weather-stat-label">Rain</span>
                      </div>
                      <div class="weather-stat">
                        <span class="weather-stat-icon">☀️</span>
                        <span class="weather-stat-value">{weather_facts.get('uv_index', '--')}</span>
                        <span class="weather-stat-label">UV Index</span>
                      </div>
                      <div class="weather-stat">
                        <span class="weather-stat-icon">💧</span>
                        <span class="weather-stat-value">{weather_facts.get('relative_humidity_2m', '--')}%</span>
                        <span class="weather-stat-label">Humidity</span>
                      </div>
                      <div class="weather-stat">
                        <span class="weather-stat-icon">🌬️</span>
                        <span class="weather-stat-value">{weather_facts.get('wind_gusts_10m', '--')}</span>
                        <span class="weather-stat-label">Gusts km/h</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                # SOP citation banner
                if citation:
                    st.markdown(
                        f'<div class="sop-citation">📜 Policy Reference &nbsp;·&nbsp; {citation}</div>',
                        unsafe_allow_html=True
                    )

                # Persist to session
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": resp_text,
                    "weather_info": weather_facts,
                    "sop_citation": citation,
                })
                st.session_state.chat_history_langchain.append(AIMessage(content=resp_text))

            except Exception as err:
                error_msg = f"⚠️ **Agent error:** {str(err)}\n\nCheck that `GROQ_API_KEY` is set correctly in your `.env` file."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
