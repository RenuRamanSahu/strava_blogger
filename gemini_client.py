from google import genai
from google.genai import types
from config import GEAR_LINKS


def generate_blog_with_gemini(metrics: dict, training_data: dict, strava_url: str, weather: dict = None, elevation_profile: dict = None):
    """Uses gemini-2.5-flash to compile raw stats into a human narrative blog layout"""
    ai_client = genai.Client()

    # Build route segment data for the narrative section
    route_segments_text = _build_route_segments(elevation_profile) if elevation_profile else ""

    system_instruction = (
        "You are a professional fitness blogger writing for renuramansahu.com. "
        "Your tone is authentic, engaging, and entirely human—avoid cliché AI phrasing. "
        "Write a structured blog post based on the provided activity data. "
        "Format using clean HTML (only <h2>, <p>, <strong>, <ul>, and <a> tags). No markdown wrappers."
    )

    user_prompt = f"""
        You are an experienced endurance running coach, exercise physiologist, and sports journalist.
        
        Write a data-centric blog post analyzing Raman's running activity using THIRD PERSON narration only.
        
        The tone should feel:
        - analytical and numbers-driven
        - scientifically grounded
        - reflective with real coaching insight
        - professional but human
        
        Do NOT write in first person. Do NOT say "I". Always refer to the athlete as "Raman".
        
        ── SESSION DATA ──
        Activity: {metrics.get('name')}
        Date: {metrics.get('start_date_local')}
        Distance: {metrics.get('distance_km')} km
        Moving Time: {metrics.get('duration_mins')} min
        Elapsed Time: {metrics.get('elapsed_mins')} min
        Stopped Time: {metrics.get('stopped_mins')} min
        Elevation Gain: {metrics.get('elevation_m')} m
        Avg Pace: {metrics.get('average_pace')} /km
        Max Pace: {metrics.get('max_pace')} /km
        Avg Heart Rate: {metrics.get('average_heartrate', 'N/A')} bpm
        Max Heart Rate: {metrics.get('max_heartrate', 'N/A')} bpm
        Avg Cadence: {metrics.get('average_cadence', 'N/A')} spm
        Calories: {metrics.get('calories', 'N/A')} kcal
        Relative Effort: {metrics.get('suffer_score', 'N/A')}
        Gear: {metrics.get('gear', 'N/A')}{f" ({metrics.get('gear_distance_km')}km total)" if metrics.get('gear_distance_km') else ""}
        
        ── WEATHER CONDITIONS ──
        Temperature: {weather.get('temperature_c', 'N/A')}°C
        Feels Like: {weather.get('feels_like_c', 'N/A')}°C
        Humidity: {weather.get('humidity_pct', 'N/A')}%
        Dew Point: {weather.get('dew_point_c', 'N/A')}°C
        Wind Speed: {weather.get('wind_speed_kmh', 'N/A')} km/h
        Precipitation: {weather.get('precipitation_mm', 'N/A')} mm
        
        ── TRAINING LOAD (28-DAY WINDOW) ──
        Acute Load (7d): {training_data.get('acute_load_7d')}
        Chronic Load (weekly avg): {training_data.get('chronic_load_weekly_avg')}
        ACWR: {training_data.get('acwr')}
        Health Status: {training_data.get('health_status')}
        Injury Risk: {training_data.get('injury_risk')}
        Runs (7d / 28d): {training_data.get('runs_last_7d')} / {training_data.get('runs_last_28d')}
        Distance (7d / 28d): {training_data.get('distance_last_7d_km')} km / {training_data.get('distance_last_28d_km')} km
        
        ── BLOG STRUCTURE ──
        Write the post in these sections:
        
        1. **Run Snapshot** — Open with the key numbers: distance, pace, duration, heart rate.
           Set the context (time of day, elevation, weather conditions).
           Mention the actual temperature, humidity, and how it felt.
           Keep it punchy — 2-3 sentences max.
        
        2. **Pace & Effort Breakdown** — Analyze the avg vs max pace gap.
           What does the difference suggest about pacing strategy?
           If heart rate data is available, discuss the effort-to-pace ratio.
           Compute and reference pace per km in min:sec format.
           If cadence is available, assess running form efficiency (optimal ~170-185 spm).
           Factor in weather impact — heat/humidity slow pace by ~2-5% per 5°C above 20°C.
           If dew point > 16°C, note the impact on breathing and evaporative cooling.
        
        3. **Route Narrative** — Tell the story of how Raman performed across different
           sections of the route, tying together elevation changes and pace variations.
           Use the per-kilometer segment data below to narrate the run chronologically.
           Describe how pace responded to uphills, downhills, and flat stretches.
           Identify the fastest and slowest segments and explain why — was it terrain,
           fatigue, a deliberate push, or a recovery section?
           Note any negative/positive splits and what they reveal about race strategy.
           Reference specific km markers, elevation deltas, and pace values.
           Make it read like a race commentary — vivid but data-backed.
           If no segment data is available, skip this section entirely.
{route_segments_text}
        4. **Workload Intelligence** — Dissect the ACWR number.
           Compare acute vs chronic load with actual values.
           Explain what the ratio means in practical terms for injury risk and adaptation.
           Reference the training frequency (runs per week vs month) and volume trends.
           Use the ACWR zones:
           • Below 0.8: Undertraining / detraining risk
           • 0.8–1.3: Optimal training zone
           • 1.3–1.5: Overreaching — caution
           • Above 1.5: Danger zone — high injury risk
        
        5. **Physiological Impact** — Based on the pace, duration, heart rate, and effort:
           What energy system was primarily targeted?
           What adaptations is this session driving? (e.g., mitochondrial density,
           capillarization, lactate clearance, fat oxidation, cardiac output)
           Be specific — reference the actual numbers to justify the analysis.
        
        6. **Recovery & Next Session** — Given the current ACWR and today's effort:
           How much recovery does Raman need before the next session?
           Prescribe a specific next workout (type, distance, target pace, intensity).
           Explain the reasoning using the load data.
        
        7. **Training Trajectory** — Zoom out to the 28-day picture.
           Is Raman building volume safely? Is the progression rate sustainable?
           What should the next 1-2 weeks look like to optimize adaptation
           without spiking injury risk?
        
        ── FORMATTING RULES ──
        - Reference actual numbers throughout — don't just describe, quantify.
        - When discussing pace, always use min:sec/km format.
        - Show your analytical reasoning (e.g., "At an ACWR of 1.12, the acute load
          of 180.5 sits comfortably within the chronic baseline of 161.2...").
        - Avoid vague statements like "good effort" or "solid run" without data backing.
        - Avoid generic motivational clichés.
        - Keep the length around 600–900 words.
        
        End with a concrete coaching directive referencing specific numbers
        (ACWR target, weekly km target, next session pace).
        
        At the very end of the blog post, include a link to the original Strava activity:
        <p><a href="{strava_url}" target="_blank">View the original activity on Strava</a></p>
        {_gear_blog_instruction(metrics)}
        """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.7,
        )
    )
    blog_html = response.text

    # Append Chart.js charts if stream data is available
    if elevation_profile and elevation_profile.get('distance_km'):
        blog_html += _build_elevation_chart_html(elevation_profile)
        if elevation_profile.get('pace_min_per_km'):
            blog_html += _build_pace_chart_html(elevation_profile)

    return blog_html


def _gear_blog_instruction(metrics: dict) -> str:
    """Generates the gear affiliate link instruction for the blog prompt"""
    gear_name = metrics.get('gear', 'N/A')
    if gear_name == 'N/A':
        return ""
    link = GEAR_LINKS.get(gear_name)
    if not link:
        return ""
    distance = metrics.get('gear_distance_km')
    distance_text = f" ({distance}km)" if distance else ""
    return (
        f"Also include a gear mention near the end of the blog post before the Strava link. "
        f"Mention that Raman ran this session in the {gear_name}{distance_text}. "
        f"Make the gear name a clickable link: "
        f'<a href="{link}" target="_blank" rel="nofollow">{gear_name}</a>. '
        f"Keep the mention natural and brief — one sentence."
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


def generate_blog_title(metrics: dict) -> str:
    """Uses Gemini to generate a creative, SEO-friendly blog post title"""
    ai_client = genai.Client()

    prompt = f"""
        Generate a single blog post title for a running activity recap on renuramansahu.com.

        Activity details:
        - Name: {metrics.get('name')}
        - Distance: {metrics.get('distance_km')} km
        - Duration: {metrics.get('duration_mins')} minutes
        - Elevation: {metrics.get('elevation_m')} meters

        Rules:
        - Return ONLY the title text, nothing else
        - No quotes, no explanation, no punctuation wrapping
        - Make it engaging, specific to the run, and SEO-friendly
        - Reference the athlete "Raman" by name
        - Keep it under 80 characters
        - Avoid generic phrases like "A Great Run" or "Another Day"
        """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.9),
    )
    return response.text.strip()


def generate_next_run_advice(metrics: dict, training_data: dict) -> str:
    """Uses Gemini to generate a one-liner next run recommendation"""
    ai_client = genai.Client()

    prompt = f"""
        You are an experienced running coach. Based on the athlete's latest run and
        training load data, generate a single actionable one-liner recommendation
        for their next run.

        Latest run:
        - Distance: {metrics.get('distance_km')} km
        - Duration: {metrics.get('duration_mins')} minutes
        - Elevation: {metrics.get('elevation_m')} meters

        Training load:
        - ACWR: {training_data.get('acwr', 'N/A')}
        - Health status: {training_data.get('health_status', 'N/A')}
        - Injury risk: {training_data.get('injury_risk', 'N/A')}
        - Runs last 7 days: {training_data.get('runs_last_7d')}
        - Distance last 7 days: {training_data.get('distance_last_7d_km')} km

        Rules:
        - Return ONLY one sentence, no quotes, no explanation
        - Be specific (mention distance, pace, or workout type)
        - Factor in current ACWR and injury risk
        - Keep it under 120 characters
        - Sound like a real coach, not an AI
        """

    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.8),
    )
    return response.text.strip()
