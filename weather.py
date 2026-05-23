import httpx
from datetime import datetime, timedelta, timezone


async def get_weather_for_activity(lat: float, lng: float, start_time: str, client: httpx.AsyncClient) -> dict:
    """Fetches weather conditions at the activity's location and start time using Open-Meteo API"""

    # Parse the activity start time — Strava's start_date_local is already in local time
    # despite the misleading Z suffix, so we strip it and treat as naive local time
    clean_time = start_time.replace("Z", "")
    dt = datetime.fromisoformat(clean_time)
    date_str = dt.strftime("%Y-%m-%d")
    hour = dt.hour

    # Use archive API for past dates, forecast API for recent/future dates
    now_utc = datetime.now(timezone.utc)
    # Approximate: treat local time as ~5.5h ahead of UTC for days_ago check
    dt_approx_utc = dt.replace(tzinfo=timezone(timedelta(hours=5, minutes=30)))
    days_ago = (now_utc - dt_approx_utc).days
    if days_ago > 2:
        url = "https://archive-api.open-meteo.com/v1/archive"
    else:
        url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lng, 4),
        "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,dew_point_2m,wind_speed_10m,precipitation",
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "auto",
    }

    print(f"\U0001f4e4 GET {url} — fetching weather for ({lat}, {lng}) on {date_str} hour {hour}")
    response = await client.get(url, params=params)
    print(f"\U0001f4e5 Response {response.status_code} from {url}")
    response.raise_for_status()
    data = response.json()

    hourly = data.get("hourly", {})
    units = data.get("hourly_units", {})

    # Clamp hour index to available data
    idx = min(hour, len(hourly.get("temperature_2m", [])) - 1)
    if idx < 0:
        return _empty_weather()

    temp = hourly.get("temperature_2m", [None])[idx]
    feels_like = hourly.get("apparent_temperature", [None])[idx]
    humidity = hourly.get("relative_humidity_2m", [None])[idx]
    dew_point = hourly.get("dew_point_2m", [None])[idx]
    wind_speed = hourly.get("wind_speed_10m", [None])[idx]
    precipitation = hourly.get("precipitation", [None])[idx]

    return {
        "temperature_c": temp,
        "feels_like_c": feels_like,
        "humidity_pct": humidity,
        "dew_point_c": dew_point,
        "wind_speed_kmh": wind_speed,
        "precipitation_mm": precipitation,
        "summary": _build_weather_summary(temp, feels_like, humidity, wind_speed, precipitation),
    }


def _build_weather_summary(temp, feels_like, humidity, wind_speed, precipitation) -> str:
    """Builds a one-line weather summary string"""
    parts = []
    if temp is not None:
        parts.append(f"{temp}°C")
    if feels_like is not None and temp is not None and abs(feels_like - temp) >= 2:
        parts.append(f"feels {feels_like}°C")
    if humidity is not None:
        parts.append(f"{humidity}% humidity")
    if wind_speed is not None and wind_speed > 0:
        parts.append(f"wind {wind_speed} km/h")
    if precipitation is not None and precipitation > 0:
        parts.append(f"{precipitation}mm rain")
    return " | ".join(parts) if parts else "N/A"


def _empty_weather() -> dict:
    return {
        "temperature_c": None,
        "feels_like_c": None,
        "humidity_pct": None,
        "dew_point_c": None,
        "wind_speed_kmh": None,
        "precipitation_mm": None,
        "summary": "N/A",
    }
