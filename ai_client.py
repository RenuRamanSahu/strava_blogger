import os
import httpx
from config import GEAR_LINKS, OPENROUTER_API_KEY
from charts import build_elevation_chart_html, build_pace_chart_html, build_route_segments
from acwr_gauge import build_acwr_gauge_html

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "meta-llama/llama-3.3-70b-instruct"
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def _load_prompt(filename: str) -> str:
    """Loads a prompt template from the prompts/ directory"""
    with open(os.path.join(PROMPTS_DIR, filename), "r", encoding="utf-8") as f:
        return f.read()


async def _openrouter_chat(system: str, user: str, temperature: float = 0.7) -> str:
    """Sends a chat completion request to OpenRouter targeting Llama 3 on Groq"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "provider": {"order": ["Groq"]},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def generate_blog_with_ai(metrics: dict, training_data: dict, strava_url: str, weather: dict = None, elevation_profile: dict = None):
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
    )

    blog_html = await _openrouter_chat(system_instruction, user_prompt, temperature=0.7)
    blog_html = _inject_charts(blog_html, metrics, training_data, elevation_profile)

    return blog_html


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
        f"Precipitation: {weather.get('precipitation_mm', 'N/A')} mm"
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


def _inject_charts(blog_html: str, metrics: dict, training_data: dict, elevation_profile: dict) -> str:
    """Deterministically injects charts and gear block into the AI-generated blog HTML"""
    # Elevation + Pace charts before Workload Intelligence
    route_charts = ""
    if elevation_profile and elevation_profile.get('distance_km'):
        route_charts += build_elevation_chart_html(elevation_profile)
        if elevation_profile.get('pace_min_per_km'):
            route_charts += build_pace_chart_html(elevation_profile)
    if route_charts:
        blog_html = _inject_before_section(blog_html, "Workload Intelligence", route_charts)

    # ACWR gauge before Physiological Impact
    acwr_value = training_data.get('acwr')
    if acwr_value is not None:
        blog_html = _inject_before_section(blog_html, "Physiological Impact", build_acwr_gauge_html(acwr_value))

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


def _build_gear_html(metrics: dict) -> str:
    """Builds a gear affiliate link block with transparency disclosure"""
    gear_name = metrics.get('gear', 'N/A')
    if gear_name == 'N/A':
        return ""
    link = GEAR_LINKS.get(gear_name)
    if not link:
        return ""
    distance = metrics.get('gear_distance_km')
    distance_text = f" ({distance} km on this pair)" if distance else ""
    return (
        f'<p><strong>Gear Used:</strong> '
        f'<a href="{link}" target="_blank" rel="nofollow noopener">{gear_name}</a>'
        f'{distance_text}</p>\n'
        f'<p style="font-size:0.75em;color:#888;">'
        f'Transparency: As an Amazon Associate, I earn a small commission if you purchase '
        f'through the link above — at no extra cost to you.</p>\n'
    )


async def generate_blog_title(metrics: dict) -> str:
    """Uses Llama 3 via OpenRouter/Groq to generate a creative, SEO-friendly blog post title"""

    prompt = _load_prompt("title_prompt.txt").format(
        name=metrics.get('name'),
        distance_km=metrics.get('distance_km'),
        duration_mins=metrics.get('duration_mins'),
        elevation_m=metrics.get('elevation_m'),
    )

    result = await _openrouter_chat(
        "You generate blog post titles. Return ONLY the title text, nothing else.",
        prompt,
        temperature=0.9,
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
    )
    return result.strip()
