from fastapi import FastAPI, Request

app = FastAPI()

VERIFY_TOKEN = "strava_verify_secret"

@app.get("/webhook")
async def verify(request: Request):

    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    print("MODE:", mode)
    print("TOKEN:", token)
    print("CHALLENGE:", challenge)

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return {"hub.challenge": challenge}

    return {"error": "verification failed"}

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    print("STRAVA EVENT RECEIVED:")
    print(data)

    return {"status": "received"}