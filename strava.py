import httpx
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
