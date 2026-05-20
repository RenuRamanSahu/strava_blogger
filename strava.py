import httpx
from datetime import datetime, timedelta, timezone
from config import STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN


async def get_strava_access_token(client: httpx.AsyncClient):
    """Exchanges your permanent refresh token for a live 6-hour access token"""
    url = "https://www.strava.com/oauth/token"
    data = {
        'client_id': STRAVA_CLIENT_ID,
        'client_secret': STRAVA_CLIENT_SECRET,
        'refresh_token': STRAVA_REFRESH_TOKEN,
        'grant_type': 'refresh_token'
    }
    print(f"\U0001f4e4 POST {url} — requesting access token")
    response = await client.post(url, data=data)
    print(f"\U0001f4e5 Response {response.status_code} from {url}")
    response.raise_for_status()
    return response.json()['access_token']


async def get_activity_details(activity_id: int, access_token: str, client: httpx.AsyncClient):
    """Fetches the full metrics of the run/ride from Strava using the unique event ID"""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {'Authorization': f'Bearer {access_token}'}
    print(f"\U0001f4e4 GET {url} — fetching activity details")
    response = await client.get(url, headers=headers)
    print(f"\U0001f4e5 Response {response.status_code} from {url}")
    response.raise_for_status()

    data = response.json()

    # Compute derived metrics
    distance_km = round(data.get("distance", 0) / 1000, 2)
    moving_time_s = data.get("moving_time", 0)
    elapsed_time_s = data.get("elapsed_time", 0)
    duration_mins = round(moving_time_s / 60, 1)
    avg_speed = data.get("average_speed", 0)
    avg_pace_sec_per_km = round(1000 / avg_speed) if avg_speed > 0 else 0
    avg_pace = f"{avg_pace_sec_per_km // 60}:{avg_pace_sec_per_km % 60:02d}" if avg_speed > 0 else "N/A"
    max_speed = data.get("max_speed", 0)
    max_pace_sec_per_km = round(1000 / max_speed) if max_speed > 0 else 0
    max_pace = f"{max_pace_sec_per_km // 60}:{max_pace_sec_per_km % 60:02d}" if max_speed > 0 else "N/A"
    stopped_time_s = elapsed_time_s - moving_time_s

    return {
        "type": data.get("type"),
        "name": data.get("name"),
        "distance_km": distance_km,
        "duration_mins": duration_mins,
        "elapsed_mins": round(elapsed_time_s / 60, 1),
        "stopped_mins": round(stopped_time_s / 60, 1),
        "elevation_m": data.get("total_elevation_gain", 0),
        "average_speed": avg_speed,
        "average_pace": avg_pace,
        "max_speed": max_speed,
        "max_pace": max_pace,
        "average_heartrate": data.get("average_heartrate"),
        "max_heartrate": data.get("max_heartrate"),
        "suffer_score": data.get("suffer_score"),
        "calories": data.get("calories"),
        "average_cadence": data.get("average_cadence"),
        "start_date_local": data.get("start_date_local", ""),
        "gear": data.get("gear", {}).get("name", "N/A") if data.get("gear") else "N/A",
        "gear_distance_km": round(data["gear"]["distance"] / 1000) if data.get("gear") and data["gear"].get("distance") else None,
        "polyline": data.get("map", {}).get("summary_polyline", "") if data.get("map") else "",
        "start_latlng": data.get("start_latlng", []),
    }


async def get_recent_activities(access_token: str, client: httpx.AsyncClient, days: int = 28):
    """Fetches all activities from the last N days for workload calculations"""
    after_epoch = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'after': after_epoch, 'per_page': 200}
    print(f"\U0001f4e4 GET {url} — fetching recent activities (last {days} days)")
    response = await client.get(url, headers=headers, params=params)
    print(f"\U0001f4e5 Response {response.status_code} from {url} — {len(response.json())} activities")
    response.raise_for_status()
    return response.json()


def calculate_training_load(activity: dict) -> float:
    """Estimates training load as duration (mins) * intensity factor derived from pace"""
    duration_mins = activity.get("moving_time", 0) / 60
    avg_speed = activity.get("average_speed", 0)  # m/s
    # Intensity factor: normalized so ~3 m/s (6:00/km) ≈ 1.0
    intensity = avg_speed / 3.0 if avg_speed > 0 else 0.5
    return round(duration_mins * intensity, 1)


def compute_acwr_and_health(activities: list) -> dict:
    """Calculates acute:chronic workload ratio and run health from recent activities"""
    now = datetime.now(timezone.utc)
    acute_cutoff = now - timedelta(days=7)
    chronic_cutoff = now - timedelta(days=28)

    acute_load = 0.0
    chronic_load = 0.0
    run_count_7d = 0
    run_count_28d = 0
    total_distance_7d = 0.0
    total_distance_28d = 0.0

    for act in activities:
        if act.get("type") not in ("Run", "TrailRun", "VirtualRun"):
            continue

        start = datetime.fromisoformat(act["start_date"].replace("Z", "+00:00"))
        load = calculate_training_load(act)
        distance_km = act.get("distance", 0) / 1000

        if start >= chronic_cutoff:
            chronic_load += load
            run_count_28d += 1
            total_distance_28d += distance_km

        if start >= acute_cutoff:
            acute_load += load
            run_count_7d += 1
            total_distance_7d += distance_km

    # Chronic load normalized to weekly average (28 days = 4 weeks)
    chronic_weekly = chronic_load / 4.0 if chronic_load > 0 else 0

    acwr = round(acute_load / chronic_weekly, 2) if chronic_weekly > 0 else None

    # Determine run health status based on ACWR
    if acwr is None:
        health_status = "Insufficient Data"
        injury_risk = "\u26AA Unknown"
    elif acwr < 0.8:
        health_status = "Undertraining"
        injury_risk = "\U0001F535 Low (but detraining risk)"
    elif acwr <= 1.3:
        health_status = "Optimal Training Zone"
        injury_risk = "\U0001F7E2 Low"
    elif acwr <= 1.5:
        health_status = "Overreaching"
        injury_risk = "\U0001F7E0 Moderate"
    else:
        health_status = "Danger Zone"
        injury_risk = "\U0001F534 High"

    return {
        "acute_load_7d": round(acute_load, 1),
        "chronic_load_weekly_avg": round(chronic_weekly, 1),
        "acwr": acwr,
        "health_status": health_status,
        "injury_risk": injury_risk,
        "runs_last_7d": run_count_7d,
        "runs_last_28d": run_count_28d,
        "distance_last_7d_km": round(total_distance_7d, 1),
        "distance_last_28d_km": round(total_distance_28d, 1),
    }


def _format_gear(metrics: dict) -> str:
    """Formats gear name with total distance"""
    gear_name = metrics.get('gear', 'N/A')
    if gear_name == 'N/A':
        return gear_name
    distance = metrics.get('gear_distance_km')
    if distance:
        return f"{gear_name} ({distance}km)"
    return gear_name


def build_strava_description(metrics: dict, training_data: dict, blog_url: str, next_run_advice: str, weather: dict = None) -> str:
    """Builds a concise Strava activity description with run summary, health metrics, and blog link"""
    lines = [
        f"\U0001f4d6 Details of this run: {blog_url}",
        f"\U0001f4dd Raman's AI coach: {next_run_advice}",
        f"\U0001f4ca Today's Training Load & Health:",
        f"  ACWR: {training_data.get('acwr', 'N/A')} \u2014 {training_data.get('health_status', 'N/A')}",
        f"  Injury Risk: {training_data.get('injury_risk', 'N/A')}",
        f"  7-day load: {training_data.get('acute_load_7d')} | 28-day avg: {training_data.get('chronic_load_weekly_avg')}",
        f"  Runs: {training_data.get('runs_last_7d')} this week / {training_data.get('runs_last_28d')} this month",
        f"  Volume: {training_data.get('distance_last_7d_km')} km (7d) / {training_data.get('distance_last_28d_km')} km (28d)",
        f"  Gear: {_format_gear(metrics)}",
    ]
    if weather and weather.get("summary") != "N/A":
        lines.append(f"\U0001f326\ufe0f Weather: {weather['summary']}")
    return "\n".join(lines)


async def update_strava_description(activity_id: int, access_token: str, description: str, client: httpx.AsyncClient):
    """Updates the description of a Strava activity"""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {'Authorization': f'Bearer {access_token}'}
    print(f"\U0001f4e4 PUT {url} — updating activity description")
    response = await client.put(url, headers=headers, json={"description": description})
    print(f"\U0001f4e5 Response {response.status_code} from {url}")
    response.raise_for_status()
    print(f"\u2705 Strava activity {activity_id} description updated")
    return response.json()
