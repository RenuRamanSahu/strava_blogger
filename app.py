import os
import re
import secrets
import httpx
from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import STRAVA_VERIFY_TOKEN, WP_USERNAME, WP_APP_PASSWORD
from strava import get_strava_access_token
from models import StravaWebhookPayload
from pipeline import process_pipeline_background, process_pipeline_streaming

app = FastAPI()
security = HTTPBasic()


def verify_wp_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify the provided credentials match the WordPress credentials"""
    correct_username = secrets.compare_digest(credentials.username, WP_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, WP_APP_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

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


# ─── MANUAL TRIGGER DASHBOARD ───

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Run Pipeline Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117; color: #e6edf3;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh; padding: 20px;
        }
        .container {
            background: #161b22; border: 1px solid #30363d; border-radius: 12px;
            padding: 40px; max-width: 520px; width: 100%;
        }
        h1 { font-size: 1.4rem; margin-bottom: 8px; color: #fc4c02; }
        .subtitle { color: #8b949e; font-size: 0.9rem; margin-bottom: 28px; }
        label { display: block; font-size: 0.85rem; color: #8b949e; margin-bottom: 6px; }
        input[type="text"] {
            width: 100%; padding: 12px 14px; background: #0d1117;
            border: 1px solid #30363d; border-radius: 8px; color: #e6edf3;
            font-size: 1rem; outline: none; transition: border-color 0.2s;
        }
        input[type="text"]:focus { border-color: #fc4c02; }
        input[type="text"]::placeholder { color: #484f58; }
        button {
            width: 100%; padding: 12px; margin-top: 18px;
            background: #fc4c02; color: #fff; border: none; border-radius: 8px;
            font-size: 1rem; font-weight: 600; cursor: pointer; transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }
        #log {
            margin-top: 24px; padding: 16px; background: #0d1117;
            border: 1px solid #30363d; border-radius: 8px;
            font-family: 'Cascadia Code', 'Fira Code', monospace; font-size: 0.82rem;
            line-height: 1.6; max-height: 400px; overflow-y: auto; display: none;
            white-space: pre-wrap; word-break: break-word;
        }
        .log-step { color: #3fb950; }
        .log-warn { color: #d29922; }
        .log-error { color: #f85149; }
        .log-info { color: #8b949e; }
        .log-done { color: #fc4c02; font-weight: 600; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏃 Run Pipeline</h1>
        <p class="subtitle">Paste a Strava activity link or enter the activity ID to generate and publish a blog post.</p>
        <label for="activity">Strava Activity ID or URL</label>
        <input type="text" id="activity" placeholder="e.g. 12345678 or https://www.strava.com/activities/12345678" autofocus />
        <button id="trigger" onclick="triggerPipeline()">Generate Blog Post</button>
        <div id="log"></div>
    </div>
    <script>
        function extractActivityId(input) {
            input = input.trim();
            if (/^\\d+$/.test(input)) return input;
            const match = input.match(/strava\\.com\\/activities\\/(\\d+)/);
            return match ? match[1] : null;
        }

        async function triggerPipeline() {
            const input = document.getElementById('activity').value;
            const activityId = extractActivityId(input);
            if (!activityId) {
                alert('Please enter a valid Strava activity ID or URL.');
                return;
            }

            const btn = document.getElementById('trigger');
            const log = document.getElementById('log');
            btn.disabled = true;
            btn.textContent = 'Processing...';
            log.style.display = 'block';
            log.innerHTML = '<span class="log-info">⏳ Starting pipeline for activity ' + activityId + '...</span>\\n';

            try {
                const response = await fetch('/trigger', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ activity_input: activityId })
                });

                if (response.status === 401) {
                    log.innerHTML += '<span class="log-error">❌ Authentication failed.</span>\\n';
                    btn.disabled = false;
                    btn.textContent = 'Generate Blog Post';
                    return;
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const text = decoder.decode(value, { stream: true });
                    const lines = text.split('\\n').filter(l => l.startsWith('data: '));
                    for (const line of lines) {
                        const msg = line.substring(6);
                        let cls = 'log-info';
                        if (msg.startsWith('✅')) cls = 'log-step';
                        else if (msg.startsWith('⚠')) cls = 'log-warn';
                        else if (msg.startsWith('❌')) cls = 'log-error';
                        else if (msg.startsWith('🎉')) cls = 'log-done';
                        log.innerHTML += '<span class="' + cls + '">' + msg + '</span>\\n';
                        log.scrollTop = log.scrollHeight;
                    }
                }
            } catch (err) {
                log.innerHTML += '<span class="log-error">❌ Network error: ' + err.message + '</span>\\n';
            }

            btn.disabled = false;
            btn.textContent = 'Generate Blog Post';
        }

        document.getElementById('activity').addEventListener('keydown', function(e) {
            if (e.key === 'Enter') triggerPipeline();
        });
    </script>
</body>
</html>
"""


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(username: str = Depends(verify_wp_credentials)):
    """Serves the manual trigger dashboard — protected by WordPress credentials"""
    return HTMLResponse(content=DASHBOARD_HTML)


@app.post("/trigger")
async def trigger_pipeline(request: Request, username: str = Depends(verify_wp_credentials)):
    """Accepts an activity ID or Strava URL, runs the pipeline, streams progress via SSE"""
    body = await request.json()
    activity_input = str(body.get("activity_input", "")).strip()

    # Extract numeric activity ID from input (could be raw ID or URL)
    match = re.search(r"(\d+)", activity_input)
    if not match:
        raise HTTPException(status_code=400, detail="Could not extract activity ID from input")

    activity_id = int(match.group(1))

    async def event_stream():
        async for message in process_pipeline_streaming(activity_id):
            yield f"data: {message}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
