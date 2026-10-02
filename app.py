import os
import json
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

from agent import WeatherAdvisoryAgent
from sop_engine import SOPEngine
from weather_service import fetch_live_weather

# Page configuration
st.set_page_config(
    page_title="MediBuddy Weather Advisory Support Bot",
    page_icon="🌤️",
    layout="wide"
)

load_dotenv(override=True)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []

if "chat_history_langchain" not in st.session_state:
    st.session_state.chat_history_langchain = []

if "last_location" not in st.session_state:
    st.session_state.last_location = None

if "last_activity" not in st.session_state:
    st.session_state.last_activity = None

# Custom CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .sop-badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        border: 1px solid #FCA5A5;
    }
    .sop-badge-high {
        background-color: #FFEDD5;
        color: #9A3412;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        border: 1px solid #FDBA74;
    }
    .sop-badge-medium {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        border: 1px solid #FDE047;
    }
    .sop-badge-low {
        background-color: #E0E7FF;
        color: #3730A3;
        padding: 0.3rem 0.6rem;
        border-radius: 6px;
        font-weight: 600;
        border: 1px solid #A5B4FC;
    }
    .weather-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Main Title & Description
st.markdown("<div class='main-header'>🌤️ Weather-Advisory Support Bot</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>Grounded Outdoor Safety Guidance Powered by LangGraph & Groq LLM (Strict SOP Policy Enforcement)</div>", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/cloud-lighting.png", width=60)
    st.title("System Control & Policies")
    
    # Groq API Key Check
    groq_key = (os.getenv("GROQ_API_KEY") or "").strip().strip('"').strip("'")
    if not (groq_key and groq_key != "your_groq_api_key_here"):
        st.warning("⚠️ Groq API Key Missing!")
        st.info("Please paste your `GROQ_API_KEY` into the `.env` file in the project root directory.")
    
    st.divider()

    # Session Memory Clear Button
    if st.button("🗑️ Clear Session Memory", use_container_width=True):
        st.session_state.messages = []
        st.session_state.chat_history_langchain = []
        st.session_state.last_location = None
        st.session_state.last_activity = None
        st.rerun()

    st.divider()

    # Sample Quick Queries
    st.subheader("💡 Sample Test Queries")
    sample_queries = [
        "Is it safe to cycle today in Bhopal around 1 PM?",
        "What about this evening instead?",
        "Can I ride my bike in Mumbai right now?",
        "Is it okay to take my toddler to the park in Delhi?",
        "Is it safe to play indoor chess in London?",
        "Can I go for a picnic in Bangalore today?"
    ]
    
    for sq in sample_queries:
        if st.button(f"👉 {sq}", use_container_width=True):
            st.session_state.pending_query = sq
            st.rerun()

    st.divider()

    # Active Policy Rules (SOPs) Inspector
    st.subheader("📜 Active Policy Rules (SOPs)")
    try:
        sop_engine = SOPEngine("sops.json")
        st.caption(f"Loaded {len(sop_engine.sops)} SOP rules from `sops.json`")
        with st.expander("Inspect All Loaded SOP Rules"):
            for sop in sop_engine.sops:
                sev = sop.get("severity", "LOW")
                st.markdown(f"**[{sop['id']}] {sop['title']}** ({sev})")
                st.write(f"*Guidance:* {sop['prescribed_guidance']}")
                st.divider()
    except Exception as e:
        st.error(f"Error loading sops.json: {e}")

# Check if sample query was clicked
user_input = None
if "pending_query" in st.session_state and st.session_state.pending_query:
    user_input = st.session_state.pending_query
    st.session_state.pending_query = None

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "weather_info" in msg and msg["weather_info"]:
            w = msg["weather_info"]
            st.caption(f"📍 Weather Fact-Check: Temp {w.get('temperature_2m')}°C | Wind {w.get('wind_speed_10m')} km/h | Rain {w.get('precipitation')} mm | UV {w.get('uv_index')}")
        if "sop_citation" in msg and msg["sop_citation"]:
            st.info(f"📜 Policy Citation: {msg['sop_citation']}")

# Chat Input Box
chat_input = st.chat_input("Ask about outdoor activity safety (e.g., 'Is it safe to cycle in Bhopal today?')")
if chat_input:
    user_input = chat_input

if user_input:
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.chat_history_langchain.append(HumanMessage(content=user_input))
    
    with st.chat_message("user"):
        st.markdown(user_input)

    # Process with LangGraph Agent
    with st.chat_message("assistant"):
        with st.spinner("Analyzing live weather data & evaluating SOP policies..."):
            try:
                agent = WeatherAdvisoryAgent(sops_file_path="sops.json")
                out = agent.run(
                    user_query=user_input,
                    history=st.session_state.chat_history_langchain,
                    location=st.session_state.last_location,
                    activity=st.session_state.last_activity
                )
                
                # Update session carried state
                if out.get("location"):
                    st.session_state.last_location = out.get("location")
                if out.get("activity"):
                    st.session_state.last_activity = out.get("activity")

                resp_text = out.get("final_response", "No response generated.")
                weather_facts = out.get("weather_data")
                citation = out.get("sop_citation")
                matched_sop = out.get("sop_matched")

                # Display Response
                st.markdown(resp_text)

                if weather_facts:
                    st.caption(
                        f"📍 Verified Weather Data ({weather_facts.get('location_name')}): "
                        f"Temp: {weather_facts.get('temperature_2m')}°C | "
                        f"Wind: {weather_facts.get('wind_speed_10m')} km/h | "
                        f"Rain: {weather_facts.get('precipitation')} mm | "
                        f"UV Index: {weather_facts.get('uv_index')}"
                    )

                # Store assistant response in history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": resp_text,
                    "weather_info": weather_facts,
                    "sop_citation": citation
                })
                st.session_state.chat_history_langchain.append(AIMessage(content=resp_text))

            except Exception as err:
                error_msg = f"⚠️ **Error executing agent**: {str(err)}\n\nPlease ensure your `GROQ_API_KEY` is configured correctly in `.env` file."
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
