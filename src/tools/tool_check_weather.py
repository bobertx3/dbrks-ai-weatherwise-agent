# check_weather.py
import requests
from langchain_core.tools import tool

@tool("check_weather", return_direct=True)
def check_weather(city: str, units: str = "imperial") -> str:
    """
    Returns the current weather for a given city using the Open-Meteo API.
    Arguments:
      city: City name (e.g. "New York" or "Paris")
      units: "imperial" for °F, "metric" for °C
    """
    try:
        # 1️⃣ Get coordinates
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
        geo_resp = requests.get(geo_url, timeout=10).json()
        if not geo_resp.get("results"):
            return f"❌ Could not find location for '{city}'."
        loc = geo_resp["results"][0]
        lat, lon, name = loc["latitude"], loc["longitude"], loc["name"]

        # 2️⃣ Fetch weather
        unit = "fahrenheit" if units == "imperial" else "celsius"
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true&temperature_unit={unit}"
        )
        w = requests.get(weather_url, timeout=10).json().get("current_weather", {})
        if not w:
            return f"⚠️ No weather data for {name}."

        # 3️⃣ Format response
        codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog", 51: "Light drizzle",
            61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Light snow", 73: "Moderate snow", 75: "Heavy snow",
            95: "Thunderstorm", 99: "Severe thunderstorm",
        }
        desc = codes.get(w.get("weathercode"), "Unknown")
        temp = w.get("temperature")
        wind = w.get("windspeed")
        unit_symbol = "°F" if units == "imperial" else "°C"

        return (
            f"🌤 Weather for {name}:\n"
            f"• Temperature: {temp}{unit_symbol}\n"
            f"• Wind Speed: {wind} km/h\n"
            f"• Conditions: {desc}"
        )
    except Exception as e:
        return f"❌ Error fetching weather: {type(e).__name__}: {e}"