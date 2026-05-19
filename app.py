import os
import httpx
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

from config import STRAVA_VERIFY_TOKEN
from strava import get_strava_access_token
from models import StravaWebhookPayload
from pipeline import process_pipeline_background

app = FastAPI()

# ─── DEBUG ENDPOINT ───

@app.get("/debug/strava-write")
async def debug_strava_write():
    """Tests whether the current Strava token has activity:write scope"""
    async with httpx.AsyncClient() as client:
        try:
            access_token = await get_strava_access_token(client)

            # Fetch most recent activity
            headers = {'Authorization': f'Bearer {access_token}'}
            resp = await client.get(
                "https://www.strava.com/api/v3/athlete/activities",
                headers=headers, params={"per_page": 1}
            )
            resp.raise_for_status()
            activities = resp.json()
            if not activities:
                return {"status": "error", "message": "No activities found on this account"}

            activity_id = activities[0]["id"]
            activity_name = activities[0].get("name", "Unknown")
            original_desc = activities[0].get("description") or ""

            # Attempt to write a test description
            test_desc = f"{original_desc}\n\n[DEBUG] Write test successful — this line was added automatically.".strip()
            put_resp = await client.put(
                f"https://www.strava.com/api/v3/activities/{activity_id}",
                headers=headers,
                json={"description": test_desc}
            )

            if put_resp.status_code == 200:
                # Restore original description
                await client.put(
                    f"https://www.strava.com/api/v3/activities/{activity_id}",
                    headers=headers,
                    json={"description": original_desc}
                )
                return {
                    "status": "success",
                    "message": "activity:write scope is working",
                    "activity_tested": activity_name,
                    "activity_id": activity_id,
                    "note": "Original description was restored after test"
                }
            else:
                return {
                    "status": "failed",
                    "http_code": put_resp.status_code,
                    "response": put_resp.text,
                    "message": "Cannot write — likely missing activity:write scope. Re-authorize your Strava app.",
                    "reauth_hint": "https://www.strava.com/oauth/authorize?client_id=YOUR_ID&response_type=code&redirect_uri=YOUR_URI&scope=activity:read_all,activity:write&approval_prompt=force"
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

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
