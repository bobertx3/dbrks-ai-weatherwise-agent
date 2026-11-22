import requests
from langchain_core.tools import tool

@tool("check_weather", return_direct=True)
def check_weather(city: str, units: str = "imperial") -> str:
    """
    Returns current weather AND the daily forecast (high/low) for the next 7 days for a city,
    using the Open-Meteo API. Use the forecast row for each shipment's ETA date.
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

        # 2️⃣ Fetch current weather + 7-day daily forecast (dates in the city's local time)
        imperial = units == "imperial"
        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
            "&daily=temperature_2m_max,temperature_2m_min,weathercode&forecast_days=7&timezone=auto"
            f"&temperature_unit={'fahrenheit' if imperial else 'celsius'}"
            f"&windspeed_unit={'mph' if imperial else 'kmh'}"
        )
        data = requests.get(weather_url, timeout=10).json()
        w = data.get("current_weather", {})
        daily = data.get("daily", {})
        if not w and not daily:
            return f"⚠️ No weather data for {name}."

        # 3️⃣ Format response
        codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Drizzle", 55: "Dense drizzle",
            61: "Light rain", 63: "Moderate rain", 65: "Heavy rain", 66: "Freezing rain", 67: "Freezing rain",
            71: "Light snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Rain showers", 81: "Rain showers",
            82: "Violent rain showers", 85: "Snow showers", 86: "Snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Severe thunderstorm",
        }
        deg = "°F" if imperial else "°C"
        wind_unit = "mph" if imperial else "km/h"
        lines = [f"🌤 Weather for {name}:"]
        if w:
            lines.append(
                f"• Now: {w.get('temperature')}{deg}, {codes.get(w.get('weathercode'), 'Unknown')}, "
                f"wind {w.get('windspeed')} {wind_unit}"
            )
        lines.append("• Daily forecast (date: high / low, conditions):")
        for day, hi, lo, code in zip(
            daily.get("time", []),
            daily.get("temperature_2m_max", []),
            daily.get("temperature_2m_min", []),
            daily.get("weathercode", []),
        ):
            lines.append(f"  {day}: {hi}{deg} / {lo}{deg}, {codes.get(code, 'Unknown')}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error fetching weather: {type(e).__name__}: {e}"
