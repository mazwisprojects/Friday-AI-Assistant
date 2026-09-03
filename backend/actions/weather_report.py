from datetime import datetime

import requests


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None,
) -> str:
    city     = parameters.get("city")
    when = parameters.get("time", "today")

    if not city or not isinstance(city, str) or not city.strip():
        msg = "Sir, the city is missing for the weather report."
        _log(msg, player)
        return msg

    city = city.strip()
    when = (when or "today").strip()

    try:
        weather = get_weather_data(city)
        msg = weather["summary"]
    except Exception as e:
        msg = f"Sir, I couldn't retrieve live weather for {city}: {e}"
        _log(msg, player)
        return msg

    _log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=f"weather in {city} {when}", response=msg)
        except Exception:
            pass

    return msg


def get_weather_data(city: str) -> dict:
    location = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=10,
        ).json()
    results = location.get("results", [])
    if not results:
        raise ValueError(f"No location found for {city}")
    place = results[0]
    forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "forecast_days": 5,
                "timezone": "Africa/Johannesburg",
            },
            timeout=10,
        ).json()
    current = forecast["current"]
    daily = forecast.get("daily", {})
    condition = _weather_code(current.get("weather_code"))
    today_high = daily.get("temperature_2m_max", [None])[0]
    today_low = daily.get("temperature_2m_min", [None])[0]
    rain_chance = daily.get("precipitation_probability_max", [None])[0]
    summary = (
        f"Weather in {place.get('name', city)}: {condition}, "
        f"{current.get('temperature_2m', 'n/a')}°C, feels like {current.get('apparent_temperature', 'n/a')}°C. "
        f"Humidity is {current.get('relative_humidity_2m', 'n/a')}%, wind {current.get('wind_speed_10m', 'n/a')} km/h. "
        f"Today's high is {today_high}°C, low {today_low}°C, with a {rain_chance}% chance of rain."
    )
    return {
        "city": place.get("name", city),
        "country": place.get("country", ""),
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "condition": condition,
        "humidity": current.get("relative_humidity_2m"),
        "wind": current.get("wind_speed_10m"),
        "high": today_high,
        "low": today_low,
        "rain_chance": rain_chance,
        "summary": summary,
    }


def _weather_code(code) -> str:
    descriptions = {
        0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
        61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow",
        80: "light showers", 81: "showers", 82: "heavy showers", 95: "thunderstorms",
        96: "thunderstorms with hail", 99: "thunderstorms with hail",
    }
    return descriptions.get(code, "conditions unavailable")


def _log(message: str, player=None) -> None:
    print(f"[Weather] {message}")
    if player:
        try:
            player.write_log(f"FRIDAY: {message}")
        except Exception:
            pass