import os
import json
from typing import Dict, Any, List, Optional, TypedDict
from dotenv import load_dotenv

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END, START

from weather_service import fetch_live_weather, WeatherData, WeatherFetchResult
from sop_engine import SOPEngine

load_dotenv()

# Define LangGraph Agent State
class AgentState(TypedDict):
    messages: List[BaseMessage]
    user_query: str
    location: Optional[str]
    activity: Optional[str]
    weather_data: Optional[Dict[str, Any]]
    weather_error: Optional[str]
    sop_matched: Optional[Dict[str, Any]]
    secondary_sops: List[Dict[str, Any]]
    sop_citation: Optional[str]
    final_response: Optional[str]
    mock_weather_failure: bool
    mock_weather_override: Optional[Dict[str, Any]]


def get_groq_llm():
    """Helper to get ChatGroq instance safely."""
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        api_key = api_key.strip().strip('"').strip("'")
    if not api_key or api_key.strip() == "" or api_key == "your_groq_api_key_here":
        raise ValueError(
            "GROQ_API_KEY is not set in your .env file! Please set GROQ_API_KEY in .env."
        )
    # Using llama-3.3-70b-versatile or llama-3.1-8b-instant
    return ChatGroq(
        model_name="llama-3.3-70b-versatile",
        groq_api_key=api_key,
        temperature=0.1
    )


class WeatherAdvisoryAgent:
    def __init__(self, sops_file_path: str = "sops.json"):
        self.sop_engine = SOPEngine(sops_file_path)
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(AgentState)

        # Add Nodes
        builder.add_node("extract_intent", self.extract_intent_node)
        builder.add_node("fetch_weather", self.fetch_weather_node)
        builder.add_node("match_sop", self.match_sop_node)
        builder.add_node("generate_sop_response", self.generate_sop_response_node)
        builder.add_node("render_no_sop", self.render_no_sop_node)
        builder.add_node("render_weather_error", self.render_weather_error_node)

        # Set Entry Point
        builder.add_edge(START, "extract_intent")

        # Edge from extract_intent to fetch_weather
        builder.add_edge("extract_intent", "fetch_weather")

        # Conditional Edge after fetch_weather
        builder.add_conditional_edges(
            "fetch_weather",
            self.route_after_weather,
            {
                "weather_error": "render_weather_error",
                "weather_success": "match_sop"
            }
        )

        # Conditional Edge after match_sop
        builder.add_conditional_edges(
            "match_sop",
            self.route_after_sop,
            {
                "sop_found": "generate_sop_response",
                "no_sop_found": "render_no_sop"
            }
        )

        # Final nodes connect to END
        builder.add_edge("generate_sop_response", END)
        builder.add_edge("render_no_sop", END)
        builder.add_edge("render_weather_error", END)

        return builder.compile()

    # --- NODE IMPLEMENTATIONS ---

    def extract_intent_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Extract location and activity from user query and conversation history context.
        """
        user_query = state.get("user_query", "")
        history = state.get("messages", [])

        # Check if state already has location/activity carried over from prior turn
        prev_location = state.get("location")
        prev_activity = state.get("activity")

        extracted_loc = None
        extracted_act = None

        prompt = f"""You are a precise NLU extractor for a weather safety bot.
Given the conversation history and the latest user query, extract:
1. "location": City or region mentioned (e.g., "Bhopal", "Mumbai", "Delhi", "London", "Paris"). If not mentioned in the latest query, check conversation history. If still unknown, return null.
2. "activity": Outdoor activity or event mentioned (e.g., "cycling", "biking", "running", "hiking", "picnic", "travel", "commute", "walking", "going out", "kids park"). If follow-up question, infer activity from history.

Conversation History:
{[f"{m.type}: {m.content}" for m in history[-6:]]}

Latest Query: "{user_query}"

Respond in STRICT JSON format:
{{"location": "city_name or null", "activity": "activity_name or null"}}
"""
        try:
            llm = get_groq_llm()
            resp = llm.invoke([SystemMessage(content=prompt)])
            text = resp.content.strip()

            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                extracted_loc = parsed.get("location")
                extracted_act = parsed.get("activity")

                if extracted_loc and str(extracted_loc).lower() in ["null", "none", ""]:
                    extracted_loc = None
                if extracted_act and str(extracted_act).lower() in ["null", "none", ""]:
                    extracted_act = None
        except Exception:
            pass

        # Fallback Heuristic Extractor if LLM didn't return a valid location
        if not extracted_loc:
            words = user_query.split()
            for i, w in enumerate(words):
                if w.lower() in ["in", "at", "for", "near", "around", "visit"] and i + 1 < len(words):
                    potential_city = words[i+1].strip("?,.!")
                    if len(potential_city) > 2 and potential_city.lower() not in ["the", "a", "an", "this", "today"]:
                        extracted_loc = potential_city.capitalize()
                        break

        # Fallback activity extraction
        if not extracted_act:
            q_lower = user_query.lower()
            if any(k in q_lower for k in ["cycle", "cycling", "bike", "biking"]):
                extracted_act = "cycling"
            elif any(k in q_lower for k in ["walk", "stroll", "jog", "run", "go out", "going out"]):
                extracted_act = "outdoor exercise"
            elif any(k in q_lower for k in ["drive", "travel", "commute"]):
                extracted_act = "travel"

        # Apply carried-over state if still None
        final_loc = extracted_loc or prev_location
        if final_loc:
            final_loc = str(final_loc).strip().strip('"\'`').strip("?,.!")

        final_act = extracted_act or prev_activity or "outdoor activity"

        return {
            "location": final_loc,
            "activity": final_act
        }

    def fetch_weather_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Fetch live weather data from Open-Meteo API or use mock override if set in state.
        """
        # Check if mock override is provided in state (for eval suite severe weather test)
        mock_override = state.get("mock_weather_override")
        if mock_override:
            w_obj = WeatherData(**mock_override)
            return {
                "weather_data": w_obj.dict(),
                "weather_error": None
            }

        location = state.get("location")
        mock_failure = state.get("mock_weather_failure", False)

        if not location:
            return {
                "weather_data": None,
                "weather_error": "No location specified in prompt or conversation context."
            }

        result = fetch_live_weather(location, mock_failure=mock_failure)

        if result.success and result.data:
            return {
                "weather_data": result.data.dict(),
                "weather_error": None
            }
        else:
            return {
                "weather_data": None,
                "weather_error": result.error_message or f"Unable to retrieve weather for location '{location}'."
            }

    def route_after_weather(self, state: AgentState) -> str:
        """Branching decision after weather fetch."""
        if state.get("weather_error") or not state.get("weather_data"):
            return "weather_error"
        return "weather_success"

    def match_sop_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Evaluate weather facts & query against SOP rules.
        """
        user_query = state.get("user_query", "")
        activity = state.get("activity") or ""
        weather_dict = state.get("weather_data")

        if not weather_dict:
            return {
                "sop_matched": None,
                "secondary_sops": []
            }

        weather_obj = WeatherData(**weather_dict)
        eval_result = self.sop_engine.evaluate_sops(user_query, activity, weather_obj)

        return {
            "sop_matched": eval_result.get("sop_matched"),
            "secondary_sops": eval_result.get("secondary_sops", [])
        }

    def route_after_sop(self, state: AgentState) -> str:
        """Branching decision after SOP evaluation."""
        if state.get("sop_matched"):
            return "sop_found"
        return "no_sop_found"

    def generate_sop_response_node(self, state: AgentState) -> Dict[str, Any]:
        """
        LLM composes response grounded strictly in matched SOP and exact API numbers.
        """
        user_query = state.get("user_query", "")
        weather = state.get("weather_data", {})
        sop = state.get("sop_matched", {})
        secondary = state.get("secondary_sops", [])

        location_name = weather.get("location_name", "your location")
        temp = weather.get("temperature_2m")
        wind = weather.get("wind_speed_10m")
        gusts = weather.get("wind_gusts_10m")
        precip = weather.get("precipitation")
        precip_prob = weather.get("precipitation_probability")
        uv = weather.get("uv_index")

        sop_title = sop.get("title")
        sop_guidance = sop.get("prescribed_guidance")
        sop_citation = sop.get("citation")
        sop_severity = sop.get("severity")

        prompt = f"""You are MediBuddy's Weather-Advisory Support Bot. Answer the user query using ONLY the provided official SOP policy and exact live weather numbers.

CRITICAL INSTRUCTIONS:
1. State the EXACT weather numbers pulled from the live API for {location_name}:
   - Temperature: {temp}°C
   - Wind Speed: {wind} km/h (Gusts: {gusts} km/h)
   - Precipitation: {precip} mm (Rain Probability: {precip_prob}%)
   - UV Index: {uv}
2. State the matched Policy Citation: "{sop_citation}" (Severity: {sop_severity}).
3. Base your safety advice STRICTLY on the Prescribed Policy Guidance: "{sop_guidance}".
4. DO NOT invent generic safety advice outside this SOP policy.
5. Include the policy citation explicitly at the end of your response in the format:
   `[Policy Citation: {sop_citation}]`

User Question: "{user_query}"
"""

        try:
            llm = get_groq_llm()
            resp = llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_query)
            ])
            final_text = resp.content.strip()

            # Append citation explicitly if missing
            if sop_citation and sop_citation not in final_text:
                final_text += f"\n\n`[Policy Citation: {sop_citation}]`"

            return {
                "final_response": final_text,
                "sop_citation": sop_citation
            }
        except Exception as e:
            # Fallback formatted response if LLM call fails
            fallback_text = (
                f"Based on live weather data for {location_name} (Temperature: {temp}°C, Wind Speed: {wind} km/h, "
                f"Rain: {precip} mm, UV Index: {uv}):\n\n"
                f"**Safety Advisory ({sop_severity})**: {sop_guidance}\n\n"
                f"`[Policy Citation: {sop_citation}]`"
            )
            return {
                "final_response": fallback_text,
                "sop_citation": sop_citation
            }

    def render_no_sop_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Honest response when no SOP rule matches the user query.
        """
        user_query = state.get("user_query", "")
        weather = state.get("weather_data", {})
        location_name = weather.get("location_name", "your location")

        temp = weather.get("temperature_2m", "N/A")
        wind = weather.get("wind_speed_10m", "N/A")
        precip = weather.get("precipitation", "N/A")
        uv = weather.get("uv_index", "N/A")

        response = (
            f"We fetched live weather data for **{location_name}**:\n"
            f"- Temperature: {temp}°C\n"
            f"- Wind Speed: {wind} km/h\n"
            f"- Precipitation: {precip} mm\n"
            f"- UV Index: {uv}\n\n"
            f"However, **we do not have a Standard Operating Procedure (SOP) policy covering guidance for your specific query: '{user_query}'**.\n\n"
            f"As per company policy, our system is constrained to only provide advice backed by official written SOPs to ensure safety and accuracy. "
            f"Because no rule covers this activity under these conditions, we cannot offer ungrounded advice."
        )

        return {
            "final_response": response,
            "sop_citation": "None (No Matching Policy)"
        }

    def render_weather_error_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Honest failure response when weather data cannot be fetched or location cannot be resolved.
        """
        err = state.get("weather_error", "Weather service unavailable.")
        location = state.get("location", "specified location")

        response = (
            f"[ERROR] Unable to retrieve weather data for '{location}'.\n\n"
            f"Reason: {err}\n\n"
            f"As per company safety policy, we cannot evaluate outdoor activity safety without verified live weather data. "
            f"Please check the location name or try again later."
        )

        return {
            "final_response": response,
            "sop_citation": "None (Weather Data Unavailable)"
        }

    def run(self, user_query: str, history: List[BaseMessage] = None, location: str = None, activity: str = None, mock_weather_failure: bool = False, mock_weather_override: Dict = None) -> Dict[str, Any]:
        """
        Run the agent graph for a query.
        """
        initial_state: AgentState = {
            "messages": history or [],
            "user_query": user_query,
            "location": location,
            "activity": activity,
            "weather_data": None,
            "weather_error": None,
            "sop_matched": None,
            "secondary_sops": [],
            "sop_citation": None,
            "final_response": None,
            "mock_weather_failure": mock_weather_failure,
            "mock_weather_override": mock_weather_override
        }

        output_state = self.graph.invoke(initial_state)
        return output_state
