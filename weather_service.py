import requests
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class WeatherData(BaseModel):
    location_name: str
    country: Optional[str] = ""
    latitude: float
    longitude: float
    temperature_2m: float = Field(description="Current temperature in Celsius")
    relative_humidity_2m: float = Field(default=0.0, description="Relative humidity %")
    precipitation: float = Field(default=0.0, description="Precipitation in mm")
    rain: float = Field(default=0.0, description="Rain in mm")
    showers: float = Field(default=0.0, description="Showers in mm")
    weather_code: int = Field(default=0, description="WMO Weather interpretation code")
    cloud_cover: float = Field(default=0.0, description="Cloud cover %")
    wind_speed_10m: float = Field(default=0.0, description="Wind speed in km/h")
    wind_gusts_10m: float = Field(default=0.0, description="Wind gusts in km/h")
    uv_index: float = Field(default=0.0, description="UV Index")
    precipitation_probability: float = Field(default=0.0, description="Precipitation probability %")

class WeatherFetchResult(BaseModel):
    success: bool
    data: Optional[WeatherData] = None
    error_message: Optional[str] = None


def geocode_city(city_name: str) -> Optional[Dict[str, Any]]:
    """
    Resolve city name to latitude and longitude using Open-Meteo Geocoding API.
    Returns dict with latitude, longitude, name, country if found, else None.
    """
    if not city_name or not city_name.strip():
        return None

    cleaned_name = city_name.strip().strip('"\'`').strip("?,.!")
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {
        "name": cleaned_name,
        "count": 1,
        "language": "en",
        "format": "json"
    }

    try:
        response = requests.get(url, params=params, timeout=5)
        if response.status_code != 200:
            return None
        
        payload = response.json()
        results = payload.get("results")
        if not results or len(results) == 0:
            return None
        
        first_match = results[0]
        return {
            "name": first_match.get("name", cleaned_name),
            "country": first_match.get("country", ""),
            "latitude": first_match.get("latitude"),
            "longitude": first_match.get("longitude")
        }
    except Exception as e:
        return None


def fetch_live_weather(city_name: str, mock_failure: bool = False) -> WeatherFetchResult:
    """
    Fetch live weather data from Open-Meteo API for a given location.
    Explicitly requests required fields: temperature_2m, wind_speed_10m, precipitation, uv_index, etc.
    """
    if mock_failure:
        return WeatherFetchResult(
            success=False,
            error_message=f"Simulated weather network failure for location '{city_name}'."
        )

    geo = geocode_city(city_name)
    if not geo:
        return WeatherFetchResult(
            success=False,
            error_message=f"Location '{city_name}' could not be resolved by geocoding service."
        )

    lat = geo["latitude"]
    lon = geo["longitude"]
    loc_display = f"{geo['name']}, {geo['country']}".strip(", ")

    forecast_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,precipitation,rain,showers,weather_code,cloud_cover,wind_speed_10m,wind_gusts_10m,uv_index",
        "hourly": "precipitation_probability,uv_index,wind_speed_10m",
        "forecast_days": 1,
        "timezone": "auto"
    }

    try:
        resp = requests.get(forecast_url, params=params, timeout=7)
        if resp.status_code != 200:
            return WeatherFetchResult(
                success=False,
                error_message=f"Open-Meteo API returned status code {resp.status_code} for coordinates ({lat}, {lon})."
            )
        
        data = resp.json()
        current = data.get("current", {})
        hourly = data.get("hourly", {})

        # Extract max precipitation probability from hourly forecast for today if present
        precip_probs = hourly.get("precipitation_probability", [0.0])
        max_precip_prob = float(max(precip_probs)) if precip_probs else 0.0

        # Hourly max UV if current uv_index is not supplied
        hourly_uvs = hourly.get("uv_index", [0.0])
        max_hourly_uv = float(max(hourly_uvs)) if hourly_uvs else 0.0

        current_uv = float(current.get("uv_index", max_hourly_uv))

        weather_obj = WeatherData(
            location_name=loc_display,
            country=geo.get("country", ""),
            latitude=lat,
            longitude=lon,
            temperature_2m=float(current.get("temperature_2m", 0.0)),
            relative_humidity_2m=float(current.get("relative_humidity_2m", 0.0)),
            precipitation=float(current.get("precipitation", 0.0)),
            rain=float(current.get("rain", 0.0)),
            showers=float(current.get("showers", 0.0)),
            weather_code=int(current.get("weather_code", 0)),
            cloud_cover=float(current.get("cloud_cover", 0.0)),
            wind_speed_10m=float(current.get("wind_speed_10m", 0.0)),
            wind_gusts_10m=float(current.get("wind_gusts_10m", 0.0)),
            uv_index=current_uv,
            precipitation_probability=max_precip_prob
        )

        return WeatherFetchResult(success=True, data=weather_obj)

    except Exception as e:
        return WeatherFetchResult(
            success=False,
            error_message=f"Network error while fetching weather data: {str(e)}"
        )
