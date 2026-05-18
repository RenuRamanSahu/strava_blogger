import os
import base64
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx
from google import genai
from google.genai import types

app = FastAPI()

# --- CONFIGURATION (Loaded Securely From Render Environment variables) ---
STRAVA_VERIFY_TOKEN = os.environ.get("STRAVA_VERIFY_TOKEN")
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")

WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APPLICATION_PASSWORD")
WP_SITE_URL = os.environ.get("WP_SITE_URL", "https://renuramansahu.com")

# Pydantic schema enforcing structure for incoming Strava alerts
class StravaWebhookPayload(BaseModel):
    object_type: str
    aspect_type: str
    object_id: int
    owner_id: int
    subscription_id: int
    event_time: int

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

def generate_blog_with_gemini(metrics: dict):
    """Uses gemini-2.5-flash to compile raw stats into a human narrative blog layout"""
    ai_client = genai.Client()
    
    system_instruction = (
        "You are a professional fitness blogger writing for renuramansahu.com. "
        "Your tone is authentic, engaging, and entirely human—avoid cliché AI phrasing. "
        "Write a structured blog post based on the provided activity data. "
        "Format using clean HTML (only <h2>, <p>, <strong>, and <ul> tags). No markdown wrappers."
    )
    
    user_prompt = f"""
    Write an engaging blog post about my recent workout:
    - Activity Type: {metrics['type']}
    - Workout Name: "{metrics['name']}"
    - Distance Covered: {metrics['distance_km']} km
    - Total Time: {metrics['duration_mins']} minutes
    - Elevation Gain: {metrics['elevation_m']} meters
    """
    
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )
    )
    return response.text

async def post_to_wordpress(title: str, html_content: str, client: httpx.AsyncClient):
    """Pushes the generated text payload directly to your WordPress backend as a Draft"""
    endpoint = f"{WP_SITE_URL}/wp-json/wp/v2/posts"
    
    # Bundle credentials to Base64 block required for WordPress Basic Auth header
    credential_string = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    base64_credentials = base64.b64encode(credential_string.encode("utf-8")).decode("utf-8")
    
    headers = {
        "Authorization": f"Basic {base64_credentials}",
        "Content-Type": "application/json"
    }
    
    post_data = {
        "title": title,
        "content": html_content,
        "status": "draft"  # Keeps the post as a draft for review before going live
    }
    
    print(f"Uploading draft post to {WP_SITE_URL}...")
    response = await client.post(endpoint, headers=headers, json=post_data)
    response.raise_for_status()
    
    result = response.json()
    print(f"✅ Success! Blog Draft created: {result.get('link')}")
    return result

async def process_pipeline_background(activity_id: int):
    """Master background execution link connecting data fetching to publishing"""
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch Working Strava Authorization Token
            access_token = await get_strava_access_token(client)
            
            # 2. Extract Specific Workout Metrics
            metrics = await get_activity_details(activity_id, access_token, client)
            
            # 3. Request Gemini Content Compilation
            blog_html = generate_blog_with_gemini(metrics)
            
            # 4. Upload Content Directly onto renuramansahu.com
            post_title = f"Recap: {metrics['name']}"
            await post_to_wordpress(post_title, blog_html, client)
            
    except Exception as e:
        print(f"❌ Error executing content pipeline: {e}")

# ─── THE WEBHOOK ROUTING ───

@app.get("/webhook")
def validate_strava_subscription(request: Request):
    """Listens for Strava's initial security subscription verification call"""
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == STRAVA_VERIFY_TOKEN:
        print("FastAPI app verified successfully by Strava!")
        return Response(content=params.get("hub.challenge"), media_type="text/plain")
    raise HTTPException(status_code=403, detail="Forbidden: Token mismatch")

@app.post("/webhook")
async def handle_strava_event(payload: StravaWebhookPayload, background_tasks: BackgroundTasks):
    """Catches live real-time incoming workout notification markers"""
    if payload.object_type == "activity" and payload.aspect_type == "create":
        print(f"🚀 Live Webhook Caught! Processing Activity ID: {payload.object_id}")
        
        # Offload pipeline processing to background thread so we can reply 200 OK instantly
        background_tasks.add_task(process_pipeline_background, payload.object_id)
        
    return JSONResponse(status_code=200, content={"status": "event processed"})

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
