from fastapi import FastAPI, HTTPException, Request
import os
import requests
from requests.auth import HTTPBasicAuth
from google import genai
from google.genai import types

app = FastAPI(title="Strava AI Blogger Webhook")

VERIFY_TOKEN = os.getenv("STRAVA_VERIFY_TOKEN", "strava_verify_secret")
STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
WP_URL = os.getenv("WP_URL", "https://renuramansahu.com/wp-json/wp/v2/posts")
WP_USERNAME = os.getenv("WP_USERNAME", "admin")
WP_APPLICATION_PASSWORD = os.getenv("WP_APPLICATION_PASSWORD", "mcXD YJmp e2D6 N3XM 8cmZ 55TH")

if GEMINI_API_KEY:
    os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

client_genai = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else genai.Client()


def get_activity(activity_id: str) -> dict:
    if not STRAVA_ACCESS_TOKEN:
        raise RuntimeError("STRAVA_ACCESS_TOKEN is not configured")

    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    headers = {"Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def generate_blog(activity: dict) -> str:
    distance_km = round(activity.get("distance", 0) / 1000, 2)
    moving_time_min = round(activity.get("moving_time", 0) / 60, 1)
    elevation_m = activity.get("total_elevation_gain", 0)
    activity_name = activity.get("name", "Strava activity")

    system_prompt = (
        "You are a professional fitness blogger writing for renuramansahu.com. "
        "Your tone is reflective, disciplined, analytical, and human. "
        "Write a complete, structured blog post based on the provided activity details. "
        "Output clean HTML using only <h2>, <p>, <strong>, and <ul> tags. "
        "Do not wrap the response in markdown code blocks."
    )

    user_prompt = f"""
Please write a blog post about this latest Strava activity:
- Activity Name: {activity_name}
- Activity Type: {activity.get('type', 'Run')}
- Distance: {distance_km} km
- Duration: {moving_time_min} minutes
- Elevation Gain: {elevation_m} meters
"""

    response = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
        ),
    )

    return response.text

@app.get("/")
async def root():
    return {
        "service": "Strava AI Blogger Webhook",
        "status": "ready",
        "strava_access_token": STRAVA_ACCESS_TOKEN is not None,
        "gemini_api_key": GEMINI_API_KEY is not None,
        "wordpress_configured": WP_APPLICATION_PASSWORD is not None,
    }


@app.get("/webhook")
async def verify(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return {"hub.challenge": challenge}

    raise HTTPException(status_code=403, detail="verification failed")

def publish_to_wordpress(title: str, content: str) -> dict:
    if not WP_APPLICATION_PASSWORD:
        raise RuntimeError("WP_APPLICATION_PASSWORD is not configured")

    post = {"title": title, "content": content, "status": "publish"}
    response = requests.post(
        WP_URL,
        auth=HTTPBasicAuth(WP_USERNAME, WP_APPLICATION_PASSWORD),
        json=post,
    )
    response.raise_for_status()
    return response.json()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    object_type = data.get("object_type")
    activity_id = data.get("object_id")
    aspect_type = data.get("aspect_type")

    if object_type != "activity" or not activity_id:
        return {"status": "ignored", "reason": "not an activity event"}

    if aspect_type == "delete":
        return {"status": "ignored", "reason": "activity deleted"}

    try:
        activity = get_activity(str(activity_id))
        blog_content = generate_blog(activity)
        publish_response = publish_to_wordpress(activity.get("name", "Strava Activity"), blog_content)

        return {
            "status": "processed",
            "activity_id": activity_id,
            "post_id": publish_response.get("id"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))



