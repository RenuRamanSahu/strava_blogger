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
    response = await client.post(url, data=data)
    response.raise_for_status()
    return response.json()['access_token']


async def get_activity_details(activity_id: int, access_token: str, client: httpx.AsyncClient):
    """Fetches the full metrics of the run/ride from Strava using the unique event ID"""
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {'Authorization': f'Bearer {access_token}'}
    response = await client.get(url, headers=headers)
    response.raise_for_status()

    data = response.json()
    return {
        "type": data.get("type"),
        "name": data.get("name"),
        "distance_km": round(data.get("distance", 0) / 1000, 2),
        "duration_mins": round(data.get("moving_time", 0) / 60, 1),
        "elevation_m": data.get("total_elevation_gain", 0)
    }


async def get_recent_activities(access_token: str, client: httpx.AsyncClient, days: int = 28):
    """Fetches all activities from the last N days for workload calculations"""
    after_epoch = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {'Authorization': f'Bearer {access_token}'}
    params = {'after': after_epoch, 'per_page': 200}
    response = await client.get(url, headers=headers, params=params)
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
        injury_risk = "Unknown"
    elif acwr < 0.8:
        health_status = "Undertraining"
        injury_risk = "Low (but detraining risk)"
    elif acwr <= 1.3:
        health_status = "Optimal Training Zone"
        injury_risk = "Low"
    elif acwr <= 1.5:
        health_status = "Overreaching"
        injury_risk = "Moderate"
    else:
        health_status = "Danger Zone"
        injury_risk = "High"

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
