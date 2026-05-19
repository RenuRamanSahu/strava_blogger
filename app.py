import os
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from config import STRAVA_VERIFY_TOKEN
from models import StravaWebhookPayload
from pipeline import process_pipeline_background

app = FastAPI()

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
    uvicorn.run("app:app", host="0.0.0.0", port=port)
