import json


def build_run_chart_html(elevation_profile: dict) -> str:
    """Builds a combined elevation + pace + cadence Chart.js chart with multiple Y-axes"""
    distances = json.dumps(elevation_profile['distance_km'])
    altitudes = json.dumps(elevation_profile['altitude_m'])

    min_alt = min(elevation_profile['altitude_m'])
    max_alt = max(elevation_profile['altitude_m'])
    alt_pad = max((max_alt - min_alt) * 0.1, 2)
    alt_min = round(min_alt - alt_pad, 1)
    alt_max = round(max_alt + alt_pad, 1)

    # Pace data (optional)
    has_pace = bool(elevation_profile.get('pace_min_per_km'))
    paces = json.dumps(elevation_profile.get('pace_min_per_km', [])) if has_pace else '[]'
    if has_pace:
        min_pace = min(elevation_profile['pace_min_per_km'])
        max_pace = max(elevation_profile['pace_min_per_km'])
        pace_pad = max((max_pace - min_pace) * 0.1, 0.3)
        pace_min = round(min_pace - pace_pad, 1)
        pace_max = round(max_pace + pace_pad, 1)
    else:
        pace_min, pace_max = 4, 8

    # Cadence data (optional)
    has_cadence = bool(elevation_profile.get('cadence_spm'))
    cadence = json.dumps(elevation_profile.get('cadence_spm', [])) if has_cadence else '[]'
    if has_cadence:
        non_zero = [c for c in elevation_profile['cadence_spm'] if c > 0] or [0]
        min_cad = min(non_zero)
        max_cad = max(non_zero)
        cad_pad = max((max_cad - min_cad) * 0.05, 5)
        cad_min = round(min_cad - cad_pad)
        cad_max = round(max_cad + cad_pad)
    else:
        cad_min, cad_max = 150, 200

    # Build datasets array
    pace_dataset = f"""{{
        label: 'Pace (min/km)',
        data: {paces},
        borderColor: '#1D72B8',
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
        yAxisID: 'yPace'
      }}""" if has_pace else None

    cadence_dataset = f"""{{
        label: 'Cadence (spm)',
        data: {cadence},
        borderColor: '#9C27B0',
        backgroundColor: 'transparent',
        fill: false,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 1.5,
        borderDash: [4, 3],
        yAxisID: 'yCadence'
      }}""" if has_cadence else None

    datasets = [f"""{{
        label: 'Elevation (m)',
        data: {altitudes},
        borderColor: '#FC4C02',
        backgroundColor: 'rgba(252,76,2,0.12)',
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
        yAxisID: 'yElev'
      }}"""]
    if pace_dataset:
        datasets.append(pace_dataset)
    if cadence_dataset:
        datasets.append(cadence_dataset)
    datasets_js = ",\n      ".join(datasets)

    # Build scales
    pace_scale = f"""yPace: {{
          type: 'linear',
          position: 'right',
          reverse: true,
          min: {pace_min},
          max: {pace_max},
          title: {{ display: true, text: 'Pace (min/km)' }},
          ticks: {{
            callback: function(v) {{
              var m = Math.floor(v);
              var s = Math.round((v - m) * 60);
              return m + ':' + (s < 10 ? '0' : '') + s;
            }}
          }},
          grid: {{ display: false }}
        }},""" if has_pace else ""

    cadence_scale = f"""yCadence: {{
          type: 'linear',
          position: 'right',
          min: {cad_min},
          max: {cad_max},
          title: {{ display: true, text: 'Cadence (spm)' }},
          grid: {{ display: false }}
        }},""" if has_cadence else ""

    return f"""
<h2>Run Analysis</h2>
<div style="max-width:720px;margin:20px auto;">
<canvas id="runChart" width="720" height="340"></canvas>
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
function renderRunChart() {{
  var ctx = document.getElementById('runChart').getContext('2d');
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: {distances},
      datasets: [{datasets_js}]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: true, position: 'bottom', labels: {{ usePointStyle: true, boxWidth: 8 }} }},
        tooltip: {{
          mode: 'index',
          intersect: false,
          callbacks: {{
            title: function(items) {{ return items[0].label + ' km'; }},
            label: function(item) {{
              if (item.dataset.yAxisID === 'yPace') {{
                var m = Math.floor(item.raw);
                var s = Math.round((item.raw - m) * 60);
                return 'Pace: ' + m + ':' + (s < 10 ? '0' : '') + s + ' /km';
              }}
              if (item.dataset.yAxisID === 'yCadence') return 'Cadence: ' + item.raw + ' spm';
              return 'Elevation: ' + item.raw + ' m';
            }}
          }}
        }}
      }},
      scales: {{
        x: {{
          title: {{ display: true, text: 'Distance (km)' }},
          ticks: {{ maxTicksLimit: 10 }}
        }},
        yElev: {{
          type: 'linear',
          position: 'left',
          min: {alt_min},
          max: {alt_max},
          title: {{ display: true, text: 'Elevation (m)' }}
        }},
        {pace_scale}
        {cadence_scale}
      }}
    }}
  }});
}}
if (window.Chart) {{ renderRunChart(); }}
else {{ window.addEventListener('chartjs-ready', renderRunChart); }}
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
