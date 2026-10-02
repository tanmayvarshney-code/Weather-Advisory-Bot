import json
import os
from typing import List, Dict, Any, Optional
from weather_service import WeatherData

SEVERITY_WEIGHTS = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1
}

class SOPEngine:
    def __init__(self, sops_file_path: str = "sops.json"):
        self.sops_file_path = sops_file_path
        self.sops: List[Dict[str, Any]] = []
        self.reload_sops()

    def reload_sops(self):
        """Dynamically reload SOP rules from JSON file without changing code."""
        if not os.path.exists(self.sops_file_path):
            raise FileNotFoundError(f"SOP configuration file not found at {self.sops_file_path}")
        
        with open(self.sops_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.sops = data.get("sops", [])

    def evaluate_sops(self, user_query: str, activity: str, weather: WeatherData) -> Dict[str, Any]:
        """
        Evaluate all loaded SOPs against user intent, extracted activity, and exact weather facts.
        Returns:
            {
                "sop_matched": primary_sop (highest severity match or System Alert),
                "secondary_sops": list of other applicable SOPs,
                "all_matches": list of all SOP matches
            }
        """
        self.reload_sops()  # Always read fresh state from sops.json
        matched_sops: List[Dict[str, Any]] = []

        query_lower = user_query.lower()
        activity_lower = activity.lower() if activity else ""

        for sop in self.sops:
            is_match = self._evaluate_single_sop(sop, query_lower, activity_lower, weather)
            if is_match:
                matched_sops.append(sop)

        if not matched_sops:
            return {
                "sop_matched": None,
                "secondary_sops": [],
                "all_matches": []
            }

        # Sort matches by severity (CRITICAL > HIGH > MEDIUM > LOW)
        sorted_sops = sorted(
            matched_sops,
            key=lambda x: SEVERITY_WEIGHTS.get(x.get("severity", "LOW").upper(), 1),
            reverse=True
        )

        primary_sop = sorted_sops[0]
        secondary_sops = sorted_sops[1:]

        return {
            "sop_matched": primary_sop,
            "secondary_sops": secondary_sops,
            "all_matches": sorted_sops
        }

    def _evaluate_single_sop(self, sop: Dict[str, Any], query_lower: str, activity_lower: str, weather: WeatherData) -> bool:
        is_system_wide = sop.get("is_system_wide", False)
        keywords = [k.lower() for k in sop.get("activity_keywords", [])]

        # Step 1: Check Activity Relevance
        activity_matches = False
        if is_system_wide or "all" in keywords:
            activity_matches = True
        else:
            # Check if any keyword is in extracted activity or query string
            for kw in keywords:
                if kw in activity_lower or kw in query_lower:
                    activity_matches = True
                    break

        if not activity_matches:
            return False

        # Step 2: Check Weather Code Triggers (if defined)
        weather_codes = sop.get("weather_code_triggers", [])
        if weather_codes and weather.weather_code in weather_codes:
            return True

        # Step 3: Check Numeric Rules (if defined)
        numeric_rules = sop.get("numeric_rules", {})
        if numeric_rules:
            numeric_pass = self._evaluate_numeric_rules(numeric_rules, weather)
            if not numeric_pass:
                return False

        # Step 4: Check Fuzzy Condition (if defined)
        fuzzy = sop.get("fuzzy_condition")
        if fuzzy:
            fuzzy_pass = self._evaluate_fuzzy_condition(fuzzy, weather, query_lower)
            if not fuzzy_pass:
                return False

        # If numeric or fuzzy rules were defined, and passed: return True
        if numeric_rules or fuzzy or weather_codes:
            return True

        # If only activity matched but no specific numeric/fuzzy rules defined: return False (prevent over-triggering)
        return False

    def _evaluate_numeric_rules(self, rules: Dict[str, Dict[str, float]], weather: WeatherData) -> bool:
        for field, ops in rules.items():
            if not hasattr(weather, field):
                return False
            
            val = getattr(weather, field)
            for op, threshold in ops.items():
                if op == "gte" and not (val >= threshold):
                    return False
                if op == "gt" and not (val > threshold):
                    return False
                if op == "lte" and not (val <= threshold):
                    return False
                if op == "lt" and not (val < threshold):
                    return False
                if op == "eq" and not (val == threshold):
                    return False
        return True

    def _evaluate_fuzzy_condition(self, fuzzy: Dict[str, Any], weather: WeatherData, query_lower: str) -> bool:
        eval_logic = fuzzy.get("eval_logic", "")
        if eval_logic == "composite_picnic":
            # Picnic is unfeasible if any of rain, high precip prob, high wind, or heavy cloud cover occurs
            if (weather.precipitation > 0.5 or 
                weather.precipitation_probability >= 50.0 or 
                weather.wind_speed_10m > 25.0 or 
                weather.cloud_cover > 85.0):
                return True
            return False
        return False
