from fastapi import FastAPI, Request
import requests
import os
from google import genai
from google.genai import types


app = FastAPI()
VERIFY_TOKEN = "strava_verify_secret"

STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")

# ==================================
# GEMINI CONFIG
# ==================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client_genai = genai.Client(api_key="GEMINI_API_KEY")

# ==================================
# WORDPRESS CONFIG
# ==================================
WP_URL = "https://renuramansahu.com/wp-json/wp/v2/posts"
USERNAME = "admin"
APPLICATION_PASSWORD = "mcXD YJmp e2D6 N3XM 8cmZ 55TH"


def get_activity(activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"

    headers = {
        "Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"
    }

    response = requests.get(url, headers=headers)

    return response.json()

def generate_blog(activity):

    distance_km = round(activity["distance"] / 1000, 2)

    moving_time_min = round(activity["moving_time"] / 60)

    prompt = f"""
    Write a motivational running blog post.

    Activity Name: {activity['name']}
    Distance: {distance_km} km
    Moving Time: {moving_time_min} minutes
    Elevation Gain: {activity.get('total_elevation_gain', 0)} meters

    The tone should feel personal, reflective,
    motivating, and human.
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.choices[0].message.content

@app.get("/webhook")
async def verify(request: Request):

    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return {"hub.challenge": challenge}

    return {"error": "verification failed"}

@app.post("/webhook")
async def webhook(request: Request):

    data = await request.json()

    activity_id = data.get("object_id")

    print("EVENT RECEIVED:", activity_id)

    activity = get_activity(activity_id)

    print("FULL ACTIVITY:")
    print(activity)

    blog = generate_blog(activity)

    print("GENERATED BLOG:")
    print(blog)

    return {"status": "processed"}


##################################################


