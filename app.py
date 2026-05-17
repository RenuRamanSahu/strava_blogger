from fastapi import FastAPI, Request

app = FastAPI()

# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def home():
    return {"status": "server is running"}

# =========================
# STRAVA WEBHOOK VERIFY (REQUIRED)
# =========================

VERIFY_TOKEN = "strava_verify_secret"

@app.get("/webhook")
async def verify(hub_mode: str = None,
                  hub_verify_token: str = None,
                  hub_challenge: str = None):

    if hub_verify_token == VERIFY_TOKEN:
        return {"hub.challenge": hub_challenge}

    return {"error": "invalid token"}

# =========================
# STRAVA EVENT RECEIVER
# =========================

@app.post("/webhook")
async def webhook(request: Request):

    data = await request.json()

    print("🔥 STRAVA EVENT RECEIVED:")
    print(data)

    return {"status": "received"}
