import asyncio
import httpx
from datetime import datetime, timedelta, timezone


async def get_weather_for_activity(lat: float, lng: float, start_time: str, client: httpx.AsyncClient) -> dict:
    """Fetches weather conditions and air quality at the activity's location and start time"""

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
        weather_url = "https://archive-api.open-meteo.com/v1/archive"
    else:
        weather_url = "https://api.open-meteo.com/v1/forecast"

    lat_r = round(lat, 4)
    lng_r = round(lng, 4)

    weather_params = {
        "latitude": lat_r,
        "longitude": lng_r,
        "hourly": "temperature_2m,apparent_temperature,relative_humidity_2m,dew_point_2m,wind_speed_10m,precipitation",
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "auto",
    }

    aqi_url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    aqi_params = {
        "latitude": lat_r,
        "longitude": lng_r,
        "hourly": "us_aqi,pm2_5,pm10",
        "start_date": date_str,
        "end_date": date_str,
        "timezone": "auto",
    }

    # Fetch weather and AQI concurrently (with retries on transient upstream errors)
    print(f"\U0001f4e4 Fetching weather + AQI for ({lat}, {lng}) on {date_str} hour {hour}")
    weather_task = _get_with_retry(client, weather_url, weather_params, label="Weather")
    aqi_task = _get_with_retry(client, aqi_url, aqi_params, label="AQI")
    weather_resp, aqi_resp = await asyncio.gather(weather_task, aqi_task, return_exceptions=True)

    # Process weather response — degrade gracefully on failure instead of raising
    if isinstance(weather_resp, Exception) or weather_resp is None:
        print(f"\u26a0\ufe0f Weather fetch failed: {weather_resp}")
        return _empty_weather()
    print(f"\U0001f4e5 Weather response {weather_resp.status_code}")
    try:
        weather_resp.raise_for_status()
        data = weather_resp.json()
    except Exception as e:
        print(f"\u26a0\ufe0f Weather parse failed: {e}")
        return _empty_weather()

    hourly = data.get("hourly", {})
    idx = min(hour, len(hourly.get("temperature_2m", [])) - 1)
    if idx < 0:
        return _empty_weather()

    temp = hourly.get("temperature_2m", [None])[idx]
    feels_like = hourly.get("apparent_temperature", [None])[idx]
    humidity = hourly.get("relative_humidity_2m", [None])[idx]
    dew_point = hourly.get("dew_point_2m", [None])[idx]
    wind_speed = hourly.get("wind_speed_10m", [None])[idx]
    precipitation = hourly.get("precipitation", [None])[idx]

    # Process AQI response
    aqi_val, pm25, pm10, aqi_cat = None, None, None, None
    if not isinstance(aqi_resp, Exception) and aqi_resp is not None:
        print(f"\U0001f4e5 AQI response {aqi_resp.status_code}")
        try:
            aqi_resp.raise_for_status()
            aqi_data = aqi_resp.json()
            aqi_hourly = aqi_data.get("hourly", {})
            aqi_idx = min(hour, len(aqi_hourly.get("us_aqi", [])) - 1)
            if aqi_idx >= 0:
                aqi_val = aqi_hourly.get("us_aqi", [None])[aqi_idx]
                pm25 = aqi_hourly.get("pm2_5", [None])[aqi_idx]
                pm10 = aqi_hourly.get("pm10", [None])[aqi_idx]
                aqi_cat = _aqi_category(aqi_val)
        except Exception as e:
            print(f"\u26a0\ufe0f AQI parse failed: {e}")
    else:
        print(f"\u26a0\ufe0f AQI fetch failed: {aqi_resp}")

    return {
        "temperature_c": temp,
        "feels_like_c": feels_like,
        "humidity_pct": humidity,
        "dew_point_c": dew_point,
        "wind_speed_kmh": wind_speed,
        "precipitation_mm": precipitation,
        "aqi": aqi_val,
        "aqi_category": aqi_cat,
        "pm2_5": pm25,
        "pm10": pm10,
        "summary": _build_weather_summary(temp, feels_like, humidity, wind_speed, precipitation, aqi_val, aqi_cat),
    }


def _aqi_category(aqi) -> str | None:
    """Returns US AQI category label"""
    if aqi is None:
        return None
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def _build_weather_summary(temp, feels_like, humidity, wind_speed, precipitation, aqi=None, aqi_cat=None) -> str:
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
    if aqi is not None:
        parts.append(f"AQI {aqi} ({aqi_cat})")
    return " | ".join(parts) if parts else "N/A"


def _empty_weather() -> dict:
    return {
        "temperature_c": None,
        "feels_like_c": None,
        "humidity_pct": None,
        "dew_point_c": None,
        "wind_speed_kmh": None,
        "precipitation_mm": None,
        "aqi": None,
        "aqi_category": None,
        "pm2_5": None,
        "pm10": None,
        "summary": "N/A",
    }


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict,
    label: str,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
) -> httpx.Response | None:
    """GET with retries on transient errors (5xx, 429, network failures). Returns None if all attempts fail."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = await client.get(url, params=params)
            if resp.status_code < 500 and resp.status_code != 429:
                return resp
            print(f"\u26a0\ufe0f {label} attempt {attempt}/{max_attempts} got {resp.status_code}, retrying...")
        except (httpx.TransportError, httpx.TimeoutException) as e:
            last_exc = e
            print(f"\u26a0\ufe0f {label} attempt {attempt}/{max_attempts} network error: {e}")
        if attempt < max_attempts:
            await asyncio.sleep(backoff_seconds * (2 ** (attempt - 1)))
    if last_exc:
        print(f"\u26a0\ufe0f {label} exhausted retries: {last_exc}")
    return None

