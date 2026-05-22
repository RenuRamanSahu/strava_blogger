import json


def build_elevation_chart_html(elevation_profile: dict) -> str:
    """Builds a self-contained Chart.js elevation profile chart as an HTML snippet"""
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
if (!window.Chart && !document.getElementById('chartjs-loader')) {{
  var s = document.createElement('script');
  s.id = 'chartjs-loader';
  s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
  s.onload = function() {{ window.dispatchEvent(new Event('chartjs-ready')); }};
  document.head.appendChild(s);
}} else if (window.Chart) {{ window.dispatchEvent(new Event('chartjs-ready')); }}
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


def build_pace_chart_html(elevation_profile: dict) -> str:
    """Builds a Chart.js pace vs distance chart with inverted Y-axis (lower = faster)"""
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


def build_route_segments(elevation_profile: dict) -> str:
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
