import os
import httpx
from config import GEAR_LINKS, OPENROUTER_API_KEY

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

    # Build route segment data for the narrative section
    route_segments_text = _build_route_segments(elevation_profile) if elevation_profile else "No segment data available."

    system_instruction = _load_prompt("blog_system.txt")

    # Build data blocks for template substitution
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

    weather_data = (
        f"Temperature: {weather.get('temperature_c', 'N/A')}°C\n"
        f"Feels Like: {weather.get('feels_like_c', 'N/A')}°C\n"
        f"Humidity: {weather.get('humidity_pct', 'N/A')}%\n"
        f"Dew Point: {weather.get('dew_point_c', 'N/A')}°C\n"
        f"Wind Speed: {weather.get('wind_speed_kmh', 'N/A')} km/h\n"
        f"Precipitation: {weather.get('precipitation_mm', 'N/A')} mm"
    ) if weather else "No weather data available."

    training_load_data = (
        f"Acute Load (7d): {training_data.get('acute_load_7d')}\n"
        f"Chronic Load (weekly avg): {training_data.get('chronic_load_weekly_avg')}\n"
        f"ACWR: {training_data.get('acwr')}\n"
        f"Health Status: {training_data.get('health_status')}\n"
        f"Injury Risk: {training_data.get('injury_risk')}\n"
        f"Runs (7d / 28d): {training_data.get('runs_last_7d')} / {training_data.get('runs_last_28d')}\n"
        f"Distance (7d / 28d): {training_data.get('distance_last_7d_km')} km / {training_data.get('distance_last_28d_km')} km"
    )

    user_prompt = _load_prompt("blog_structure.txt").format(
        session_data=session_data,
        weather_data=weather_data,
        training_load_data=training_load_data,
        route_segments=route_segments_text,
        strava_url=strava_url,
    )

    blog_html = await _openrouter_chat(system_instruction, user_prompt, temperature=0.7)

    # Inject charts deterministically after specific sections
    # Elevation + Pace charts go after Route Narrative (before Workload Intelligence)
    route_charts = ""
    if elevation_profile and elevation_profile.get('distance_km'):
        route_charts += _build_elevation_chart_html(elevation_profile)
        if elevation_profile.get('pace_min_per_km'):
            route_charts += _build_pace_chart_html(elevation_profile)
    if route_charts:
        blog_html = _inject_before_section(blog_html, "Workload Intelligence", route_charts)

    # ACWR gauge goes after Workload Intelligence (before Physiological Impact)
    acwr_value = training_data.get('acwr')
    if acwr_value is not None:
        blog_html = _inject_before_section(blog_html, "Physiological Impact", _build_acwr_gauge_html(acwr_value))

    # Append gear affiliate block with disclosure
    blog_html += _build_gear_html(metrics)

    return blog_html


def _inject_before_section(html: str, section_title: str, chart_html: str) -> str:
    """Injects chart HTML just before an <h2> section. Falls back to appending if section not found."""
    marker = f"<h2>{section_title}</h2>"
    if marker in html:
        return html.replace(marker, chart_html + marker, 1)
    # Try case-insensitive match
    lower = html.lower()
    lower_marker = marker.lower()
    idx = lower.find(lower_marker)
    if idx != -1:
        return html[:idx] + chart_html + html[idx:]
    # Fallback: append at end
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


def _build_route_segments(elevation_profile: dict) -> str:
    """Splits streams into per-km segments with avg pace and elevation delta for the route narrative"""
    if not elevation_profile:
        return ""

    distances = elevation_profile.get('distance_km', [])
    altitudes = elevation_profile.get('altitude_m', [])
    paces = elevation_profile.get('pace_min_per_km', [])

    if not distances or not altitudes or not paces:
        return ""

    segments = []
    total_km = distances[-1] if distances else 0
    km_mark = 1

    while km_mark <= int(total_km) + 1:
        km_start = km_mark - 1
        km_end = min(km_mark, total_km)

        # Find indices within this km range
        indices = [i for i, d in enumerate(distances) if km_start <= d < km_end]
        if not indices:
            km_mark += 1
            continue

        seg_paces = [paces[i] for i in indices]
        avg_pace = sum(seg_paces) / len(seg_paces)
        pace_min = int(avg_pace)
        pace_sec = int((avg_pace - pace_min) * 60)

        elev_start = altitudes[indices[0]]
        elev_end = altitudes[indices[-1]]
        elev_delta = round(elev_end - elev_start, 1)
        elev_sign = "+" if elev_delta >= 0 else ""

        fastest = min(seg_paces)
        slowest = max(seg_paces)

        segments.append(
            f"           Km {km_mark}: avg pace {pace_min}:{pace_sec:02d}/km | "
            f"elevation {elev_sign}{elev_delta}m ({round(elev_start,1)}m → {round(elev_end,1)}m) | "
            f"range {int(fastest)}:{int((fastest % 1)*60):02d}–{int(slowest)}:{int((slowest % 1)*60):02d}/km"
        )

        km_mark += 1

    if not segments:
        return ""

    header = "\n        ── ROUTE SEGMENT DATA (per km) ──"
    return header + "\n" + "\n".join(segments) + "\n"


def _build_elevation_chart_html(elevation_profile: dict) -> str:
    """Builds a self-contained Chart.js elevation profile chart as an HTML snippet"""
    import json

    distances = json.dumps(elevation_profile['distance_km'])
    altitudes = json.dumps(elevation_profile['altitude_m'])

    min_alt = min(elevation_profile['altitude_m'])
    max_alt = max(elevation_profile['altitude_m'])
    padding = max((max_alt - min_alt) * 0.1, 2)
    y_min = round(min_alt - padding, 1)
    y_max = round(max_alt + padding, 1)

    return f"""
<h2>Elevation Profile</h2>
<div style="max-width:720px;margin:20px auto;">
<canvas id="elevationChart" width="720" height="300"></canvas>
</div>
<script>
if (!window.Chart) {{
  var s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
  s.onload = function() {{ window.dispatchEvent(new Event('chartjs-ready')); }};
  document.head.appendChild(s);
}} else {{ window.dispatchEvent(new Event('chartjs-ready')); }}
</script>
<script>
function renderElevationChart() {{
  var ctx = document.getElementById('elevationChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {distances},
      datasets: [{{
        label: 'Elevation (m)',
        data: {altitudes},
        borderColor: '#FC4C02',
        backgroundColor: 'rgba(252,76,2,0.15)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            title: function(items) {{ return items[0].label + ' km'; }},
            label: function(item) {{ return item.raw + ' m'; }}
          }}
        }}
      }},
      scales: {{
        x: {{
          title: {{ display: true, text: 'Distance (km)' }},
          ticks: {{ maxTicksLimit: 10 }}
        }},
        y: {{
          title: {{ display: true, text: 'Elevation (m)' }},
          min: {y_min},
          max: {y_max}
        }}
      }}
    }}
  }});
}}
if (window.Chart) {{ renderElevationChart(); }}
else {{ window.addEventListener('chartjs-ready', renderElevationChart); }}
</script>
"""


def _build_pace_chart_html(elevation_profile: dict) -> str:
    """Builds a Chart.js pace vs distance chart with inverted Y-axis (lower = faster)"""
    import json

    distances = json.dumps(elevation_profile['distance_km'])
    paces = json.dumps(elevation_profile['pace_min_per_km'])

    min_pace = min(elevation_profile['pace_min_per_km'])
    max_pace = max(elevation_profile['pace_min_per_km'])
    padding = max((max_pace - min_pace) * 0.1, 0.3)
    y_min = round(min_pace - padding, 1)
    y_max = round(max_pace + padding, 1)

    return f"""
<h2>Pace Analysis</h2>
<div style="max-width:720px;margin:20px auto;">
<canvas id="paceChart" width="720" height="300"></canvas>
</div>
<script>
function renderPaceChart() {{
  var ctx = document.getElementById('paceChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {distances},
      datasets: [{{
        label: 'Pace (min/km)',
        data: {paces},
        borderColor: '#1D72B8',
        backgroundColor: 'rgba(29,114,184,0.12)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2
      }}]
    }},
    options: {{
      responsive: true,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            title: function(items) {{ return items[0].label + ' km'; }},
            label: function(item) {{
              var m = Math.floor(item.raw);
              var s = Math.round((item.raw - m) * 60);
              return m + ':' + (s < 10 ? '0' : '') + s + ' /km';
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          title: {{ display: true, text: 'Distance (km)' }},
          ticks: {{ maxTicksLimit: 10 }}
        }},
        y: {{
          title: {{ display: true, text: 'Pace (min/km)' }},
          reverse: true,
          min: {y_min},
          max: {y_max},
          ticks: {{
            callback: function(v) {{
              var m = Math.floor(v);
              var s = Math.round((v - m) * 60);
              return m + ':' + (s < 10 ? '0' : '') + s;
            }}
          }}
        }}
      }}
    }}
  }});
}}
if (window.Chart) {{ renderPaceChart(); }}
else {{ window.addEventListener('chartjs-ready', renderPaceChart); }}
</script>
"""


def _build_acwr_gauge_html(acwr_value: float) -> str:
    """Builds a semi-circular ACWR gauge chart with a needle pointer using Chart.js"""
    clamped = max(0.0, min(float(acwr_value), 2.0))

    if clamped < 0.8:
        zone_label = "Under-training"
        zone_color = "#7eb8da"
    elif clamped <= 1.3:
        zone_label = "Optimal"
        zone_color = "#4caf50"
    elif clamped <= 1.5:
        zone_label = "Overreaching"
        zone_color = "#ff9800"
    else:
        zone_label = "Danger Zone"
        zone_color = "#f44336"

    return f"""
<div style="max-width:400px;margin:24px auto;text-align:center;">
<canvas id="acwrGauge" width="400" height="260"></canvas>
</div>
<script>
function renderAcwrGauge() {{
  var acwrValue = {clamped};
  var acwrMax = 2.0;
  var ctx = document.getElementById('acwrGauge').getContext('2d');

  var needlePlugin = {{
    id: 'acwrNeedle',
    afterDatasetDraw: function(chart) {{
      var meta = chart.getDatasetMeta(0);
      var arc = meta.data[0];
      var cx = arc.x;
      var cy = arc.y;
      var radius = arc.outerRadius * 0.85;
      var ratio = acwrValue / acwrMax;
      var angle = Math.PI * (1 - ratio);

      var needleX = cx + radius * Math.cos(angle);
      var needleY = cy - radius * Math.sin(angle);

      var drawCtx = chart.ctx;
      drawCtx.save();

      drawCtx.beginPath();
      drawCtx.moveTo(cx, cy);
      drawCtx.lineTo(needleX, needleY);
      drawCtx.lineWidth = 3;
      drawCtx.strokeStyle = '#333';
      drawCtx.stroke();

      drawCtx.beginPath();
      drawCtx.arc(needleX, needleY, 5, 0, Math.PI * 2);
      drawCtx.fillStyle = '#333';
      drawCtx.fill();

      drawCtx.beginPath();
      drawCtx.arc(cx, cy, 8, 0, Math.PI * 2);
      drawCtx.fillStyle = '#333';
      drawCtx.fill();

      drawCtx.font = 'bold 28px -apple-system, BlinkMacSystemFont, sans-serif';
      drawCtx.fillStyle = '{zone_color}';
      drawCtx.textAlign = 'center';
      drawCtx.fillText(acwrValue.toFixed(2), cx, cy - 20);

      drawCtx.font = '14px -apple-system, BlinkMacSystemFont, sans-serif';
      drawCtx.fillStyle = '#666';
      drawCtx.fillText('{zone_label}', cx, cy - 2);

      drawCtx.restore();
    }}
  }};

  var gradient = ctx.createLinearGradient(0, 0, 400, 0);
  gradient.addColorStop(0.0, '#7eb8da');
  gradient.addColorStop(0.35, '#7eb8da');
  gradient.addColorStop(0.40, '#4caf50');
  gradient.addColorStop(0.65, '#4caf50');
  gradient.addColorStop(0.70, '#ff9800');
  gradient.addColorStop(0.75, '#ff9800');
  gradient.addColorStop(0.80, '#f44336');
  gradient.addColorStop(1.0, '#f44336');

  new Chart(ctx, {{
    type: 'doughnut',
    data: {{
      datasets: [{{
        data: [100],
        backgroundColor: [gradient],
        borderWidth: 0,
        circumference: 180,
        rotation: 270
      }}]
    }},
    options: {{
      responsive: true,
      cutout: '85%',
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ enabled: false }}
      }}
    }},
    plugins: [needlePlugin]
  }});

  var canvas = document.getElementById('acwrGauge');
  var lCtx = canvas.getContext('2d');
  lCtx.font = '12px -apple-system, BlinkMacSystemFont, sans-serif';
  lCtx.fillStyle = '#999';
  lCtx.textAlign = 'left';
  lCtx.fillText('0.0', 28, canvas.height - 10);
  lCtx.textAlign = 'center';
  lCtx.fillText('1.0', canvas.width / 2, 18);
  lCtx.textAlign = 'right';
  lCtx.fillText('2.0', canvas.width - 28, canvas.height - 10);
}}
if (window.Chart) {{ renderAcwrGauge(); }}
else {{ window.addEventListener('chartjs-ready', renderAcwrGauge); }}
</script>
"""


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
