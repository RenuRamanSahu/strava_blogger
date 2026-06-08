import os
import logging
import httpx
from config import OPENROUTER_API_KEY, GEAR_AFFILIATE
from charts import build_run_chart_html, build_route_segments
from acwr_gauge import build_acwr_gauge_html
from aqi_gauge import build_aqi_gauge_html

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

# Model chains per role — first model is primary, rest are fallbacks
MODEL_CHAINS = {
    "analysis": [
        {"model": "deepseek/deepseek-chat-v3-0324", "provider": {"order": ["DeepSeek"]}},
        {"model": "meta-llama/llama-3.3-70b-instruct", "provider": {"order": ["Groq"]}},
        {"model": "google/gemini-2.0-flash-001", "provider": {"order": ["Google"]}},
    ],
    "writing": [
        {"model": "meta-llama/llama-3.3-70b-instruct", "provider": {"order": ["Groq"]}},
        {"model": "deepseek/deepseek-chat-v3-0324", "provider": {"order": ["DeepSeek"]}},
        {"model": "google/gemini-2.0-flash-001", "provider": {"order": ["Google"]}},
    ],
}


def _load_prompt(filename: str) -> str:
    """Loads a prompt template from the prompts/ directory"""
    with open(os.path.join(PROMPTS_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


async def _openrouter_chat(system: str, user: str, temperature: float = 0.7, role: str = "writing") -> str:
    """Sends a chat request to OpenRouter, trying each model in the chain until one succeeds"""
    chain = MODEL_CHAINS.get(role, MODEL_CHAINS["writing"])
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    last_error = None
    for entry in chain:
        payload = {
            "model": entry["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "provider": entry.get("provider", {}),
        }
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
                resp.raise_for_status()
                result = resp.json()["choices"][0]["message"]["content"]
                logger.info(f"[{role}] Success with {entry['model']}")
                return result
        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout, KeyError) as e:
            last_error = e
            logger.warning(f"[{role}] {entry['model']} failed: {e}. Trying next...")
            continue
    raise RuntimeError(f"All models failed for role '{role}'. Last error: {last_error}")


async def generate_blog_with_ai(metrics: dict, training_data: dict, strava_url: str, weather: dict = None, elevation_profile: dict = None, user_note: str = ""):
    """Uses Llama 3 via OpenRouter/Groq to compile raw stats into a human narrative blog layout"""

    route_segments_text = build_route_segments(elevation_profile) if elevation_profile else "No segment data available."

    system_instruction = _load_prompt("blog_system.txt")

    session_data = _build_session_data(metrics)
    weather_data = _build_weather_data(weather)
    training_load_data = _build_training_load_data(training_data)

    user_prompt = _load_prompt("blog_structure.txt").format(
        session_data=session_data,
        weather_data=weather_data,
        training_load_data=training_load_data,
        route_segments=route_segments_text,
        strava_url=strava_url,
        user_note=(user_note or "").strip(),
    )

    blog_html = await _openrouter_chat(system_instruction, user_prompt, temperature=0.7, role="writing")
    blog_html = _inject_charts(blog_html, metrics, training_data, elevation_profile, weather or {})

    return blog_html


async def generate_user_note_summary(user_note: str) -> str:
    """Summarizes the runner's own activity note into 1–2 short sentences (<=180 chars)
    suitable for embedding in the updated Strava description. Returns "" when the note is empty.
    """
    note = (user_note or "").strip()
    if not note:
        return ""
    if len(note) <= 180:
        # Short enough to use verbatim — collapse newlines
        return " ".join(note.split())
    system = (
        "You summarize a runner's first-person activity note into 1–2 short sentences "
        "(<=180 characters total) for an athlete's Strava description. Keep their voice, "
        "first person if they used it, no hashtags or emojis. Plain text only."
    )
    user = f"Note:\n{note}\n\nReturn ONLY the summary text, nothing else."
    try:
        summary = await _openrouter_chat(system, user, temperature=0.3, role="analysis")
    except Exception as e:
        logger.warning(f"User note summarization failed: {e}; truncating verbatim instead")
        return note[:177].rstrip() + "..."
    summary = " ".join(summary.split()).strip().strip('"').strip("'")
    if len(summary) > 200:
        summary = summary[:197].rstrip() + "..."
    return summary


def _build_session_data(metrics: dict) -> str:
    """Formats activity metrics into a text block for the AI prompt"""
    session_data = (
        f"Activity: {metrics.get('name')}\n"
        f"Date: {metrics.get('start_date_local')}\n"
        f"Distance: {metrics.get('distance_km')} km\n"
        f"Moving Time: {metrics.get('duration_mins')} min\n"
        f"Elapsed Time: {metrics.get('elapsed_mins')} min\n"
        f"Stopped Time: {metrics.get('stopped_mins')} min\n"
        f"Elevation Gain: {metrics.get('elevation_m')} m\n"
        f"Avg Pace: {metrics.get('average_pace')} /km\n"
        f"Max Pace: {metrics.get('max_pace')} /km\n"
        f"Avg Heart Rate: {metrics.get('average_heartrate', 'N/A')} bpm\n"
        f"Max Heart Rate: {metrics.get('max_heartrate', 'N/A')} bpm\n"
        f"Avg Cadence: {metrics.get('average_cadence', 'N/A')} spm\n"
        f"Calories: {metrics.get('calories', 'N/A')} kcal\n"
        f"Relative Effort: {metrics.get('suffer_score', 'N/A')}\n"
        f"Gear: {metrics.get('gear', 'N/A')}"
    )
    gear_km = metrics.get('gear_distance_km')
    if gear_km:
        session_data += f" ({gear_km}km total)"
    return session_data


def _build_weather_data(weather: dict) -> str:
    """Formats weather data into a text block for the AI prompt"""
    if not weather:
        return "No weather data available."
    return (
        f"Temperature: {weather.get('temperature_c', 'N/A')}°C\n"
        f"Feels Like: {weather.get('feels_like_c', 'N/A')}°C\n"
        f"Humidity: {weather.get('humidity_pct', 'N/A')}%\n"
        f"Dew Point: {weather.get('dew_point_c', 'N/A')}°C\n"
        f"Wind Speed: {weather.get('wind_speed_kmh', 'N/A')} km/h\n"
        f"Precipitation: {weather.get('precipitation_mm', 'N/A')} mm\n"
        f"Air Quality Index (US AQI): {weather.get('aqi', 'N/A')} — {weather.get('aqi_category', 'N/A')}\n"
        f"PM2.5: {weather.get('pm2_5', 'N/A')} µg/m³\n"
        f"PM10: {weather.get('pm10', 'N/A')} µg/m³\n"
        f"(Note: AQI is modeled data from CAMS at ~45 km resolution — actual local conditions may differ)"
    )


def _build_training_load_data(training_data: dict) -> str:
    """Formats training load data into a text block for the AI prompt"""
    return (
        f"Acute Load (7d): {training_data.get('acute_load_7d')}\n"
        f"Chronic Load (weekly avg): {training_data.get('chronic_load_weekly_avg')}\n"
        f"ACWR: {training_data.get('acwr')}\n"
        f"Health Status: {training_data.get('health_status')}\n"
        f"Injury Risk: {training_data.get('injury_risk')}\n"
        f"Runs (7d / 28d): {training_data.get('runs_last_7d')} / {training_data.get('runs_last_28d')}\n"
        f"Distance (7d / 28d): {training_data.get('distance_last_7d_km')} km / {training_data.get('distance_last_28d_km')} km"
    )


def _inject_charts(blog_html: str, metrics: dict, training_data: dict, elevation_profile: dict, weather: dict) -> str:
    """Deterministically injects charts and gauge blocks into the AI-generated blog HTML"""
    # Combined run chart (elevation + pace + cadence) before Workload Intelligence
    route_charts = ""
    if elevation_profile and elevation_profile.get('distance_km'):
        route_charts = build_run_chart_html(elevation_profile)
    if route_charts:
        blog_html = _inject_before_section(blog_html, "Workload Intelligence", route_charts)

    # ACWR gauge before Physiological Impact
    acwr_value = training_data.get('acwr')
    if acwr_value is not None:
        blog_html = _inject_before_section(blog_html, "Physiological Impact", build_acwr_gauge_html(acwr_value))

    # AQI gauge after Run Snapshot (where weather context is set)
    aqi_value = weather.get('aqi') if weather else None
    if aqi_value is not None:
        blog_html = _inject_after_section(blog_html, "Run Snapshot", build_aqi_gauge_html(aqi_value))

    # Gear affiliate block at end
    blog_html += _build_gear_html(metrics)

    return blog_html


def _inject_before_section(html: str, section_title: str, chart_html: str) -> str:
    """Injects chart HTML just before an <h2> section. Falls back to appending if section not found."""
    marker = f"<h2>{section_title}</h2>"
    if marker in html:
        return html.replace(marker, chart_html + marker, 1)
    lower = html.lower()
    lower_marker = marker.lower()
    idx = lower.find(lower_marker)
    if idx != -1:
        return html[:idx] + chart_html + html[idx:]
    return html + chart_html


def _inject_after_section(html: str, section_title: str, chart_html: str) -> str:
    """Injects chart HTML after a section's content (before the next <h2>). Falls back to appending."""
    import re
    # Find the target <h2> (case-insensitive)
    pattern = re.compile(r'<h2[^>]*>' + re.escape(section_title) + r'</h2>', re.IGNORECASE)
    match = pattern.search(html)
    if not match:
        return html + chart_html
    # Find the next <h2> after this section
    next_h2 = re.search(r'<h2[^>]*>', html[match.end():], re.IGNORECASE)
    if next_h2:
        insert_pos = match.end() + next_h2.start()
    else:
        insert_pos = len(html)
    return html[:insert_pos] + chart_html + html[insert_pos:]


def _build_gear_html(metrics: dict) -> str:
    """Builds gear affiliate links block from config list"""
    if not GEAR_AFFILIATE:
        return ""
    items = []
    for gear in GEAR_AFFILIATE:
        items.append(
            f'<a href="{gear["link"]}" target="_blank" rel="nofollow noopener">'
            f'{gear["name"]}</a> ({gear["type"]})'
        )
    gear_list = " &bull; ".join(items)
    return (
        f'<p><strong>Gear Used:</strong> {gear_list}</p>\n'
        f'<p style="font-size:0.75em;color:#888;">'
        f'Transparency: The links above are affiliate links \u2014 if you purchase through them, '
        f'I earn a small commission at no extra cost to you. '
        f'It helps support my training and this data analysis hobby project.</p>\n'
    )


async def generate_blog_title(metrics: dict, blog_html: str) -> str:
    """Generates a title based on the completed blog content to capture the run's uniqueness"""

    # Extract a text summary from the blog HTML (strip tags for brevity)
    import re
    blog_text = re.sub(r'<[^>]+>', ' ', blog_html)
    blog_text = re.sub(r'\s+', ' ', blog_text).strip()
    # Send first ~1500 chars to keep token usage reasonable
    blog_excerpt = blog_text[:1500]

    prompt = _load_prompt("title_prompt.txt").format(
        name=metrics.get('name'),
        distance_km=metrics.get('distance_km'),
        duration_mins=metrics.get('duration_mins'),
        elevation_m=metrics.get('elevation_m'),
        blog_excerpt=blog_excerpt,
    )

    result = await _openrouter_chat(
        "You generate blog post titles. Return ONLY the title text, nothing else.",
        prompt,
        temperature=0.9,
        role="writing",
    )
    return result.strip()


async def generate_next_run_advice(metrics: dict, training_data: dict) -> str:
    """Uses Llama 3 via OpenRouter/Groq to generate a one-liner next run recommendation"""

    prompt = _load_prompt("advice_prompt.txt").format(
        distance_km=metrics.get('distance_km'),
        duration_mins=metrics.get('duration_mins'),
        elevation_m=metrics.get('elevation_m'),
        acwr=training_data.get('acwr', 'N/A'),
        health_status=training_data.get('health_status', 'N/A'),
        injury_risk=training_data.get('injury_risk', 'N/A'),
        runs_last_7d=training_data.get('runs_last_7d'),
        distance_last_7d_km=training_data.get('distance_last_7d_km'),
    )

    result = await _openrouter_chat(
        "You are an experienced running coach. Return ONLY one sentence, no quotes, no explanation.",
        prompt,
        temperature=0.8,
        role="analysis",
    )
    return result.strip()
