from fastapi import FastAPI, Request
import requests
import os

app = FastAPI()
VERIFY_TOKEN = "strava_verify_secret"

STRAVA_ACCESS_TOKEN = os.getenv("STRAVA_ACCESS_TOKEN")

def get_activity(activity_id):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"

    headers = {
        "Authorization": f"Bearer {STRAVA_ACCESS_TOKEN}"
    }

    response = requests.get(url, headers=headers)

    return response.json()

@app.get("/webhook")
async def verify(request: Request):

    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return {"hub.challenge": challenge}

    return {"error": "verification failed"}


# @app.post("/webhook")
# async def webhook(request: Request):
#     data = await request.json()

#     print("STRAVA EVENT RECEIVED:")
#     print(data)

#     return {"status": "received"}

@app.post("/webhook")
async def webhook(request: Request):

    data = await request.json()

    activity_id = data.get("object_id")
    print("EVENT RECEIVED:", activity_id)

    activity = get_activity(activity_id)
    print("FULL ACTIVITY DATA:")
    print(activity)

    return {"status": "processed"}


##################################################


