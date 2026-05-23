import math
import base64


def build_aqi_gauge_html(aqi_value) -> str:
    """Builds an AQI gauge as a base64-encoded SVG inside an <img> tag (WordPress-safe)"""
    if aqi_value is None:
        return ""
    clamped = max(0, min(int(aqi_value), 500))

    if clamped <= 50:
        zone_label = "Good"
        zone_color = "#4caf50"
    elif clamped <= 100:
        zone_label = "Moderate"
        zone_color = "#ffeb3b"
    elif clamped <= 150:
        zone_label = "Unhealthy (Sensitive)"
        zone_color = "#ff9800"
    elif clamped <= 200:
        zone_label = "Unhealthy"
        zone_color = "#f44336"
    elif clamped <= 300:
        zone_label = "Very Unhealthy"
        zone_color = "#9c27b0"
    else:
        zone_label = "Hazardous"
        zone_color = "#7e0023"

    svg = _build_svg(clamped, zone_label, zone_color)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    data_uri = f"data:image/svg+xml;base64,{encoded}"

    return (
        f'<div style="max-width:420px;margin:24px auto;text-align:center;">'
        f'<img src="{data_uri}" alt="AQI Gauge: {clamped} — {zone_label}" '
        f'style="max-width:400px;width:100%;" />'
        f'</div>\n'
    )


def _build_svg(clamped: int, zone_label: str, zone_color: str) -> str:
    """Generates the raw SVG markup for the AQI gauge"""

    cx, cy = 200, 195
    r = 140
    stroke_w = 22

    def point(angle_deg):
        rad = math.radians(angle_deg)
        return (cx + r * math.cos(rad), cy - r * math.sin(rad))

    def arc_path(start_deg, end_deg):
        x1, y1 = point(start_deg)
        x2, y2 = point(end_deg)
        sweep = start_deg - end_deg
        large_arc = 1 if sweep > 180 else 0
        return f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f}"

    # Map AQI value to angle: 0→180°, 500→0° (linear)
    def aqi_to_angle(val):
        return 180 - (val / 500) * 180

    # AQI zones mapped to arc segments
    zones = [
        (0,   50,  "#4caf50"),   # Good
        (50,  100, "#ffeb3b"),   # Moderate
        (100, 150, "#ff9800"),   # Unhealthy for Sensitive Groups
        (150, 200, "#f44336"),   # Unhealthy
        (200, 300, "#9c27b0"),   # Very Unhealthy
        (300, 500, "#7e0023"),   # Hazardous
    ]

    arcs_svg = ""
    for start_val, end_val, color in zones:
        start_angle = aqi_to_angle(start_val)
        end_angle = aqi_to_angle(end_val)
        path = arc_path(start_angle, end_angle)
        arcs_svg += f'  <path d="{path}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="butt"/>\n'

    # Needle
    needle_angle = aqi_to_angle(clamped)
    needle_rad = math.radians(needle_angle)
    needle_len = r - 10
    nx = cx + needle_len * math.cos(needle_rad)
    ny = cy - needle_len * math.sin(needle_rad)

    # Scale ticks and labels
    tick_inner_r = r + stroke_w / 2 + 2
    tick_outer_r = r + stroke_w / 2 + 10
    label_r = r + stroke_w / 2 + 22
    scale_svg = ""
    for value in [0, 50, 100, 150, 200, 300, 500]:
        angle = aqi_to_angle(value)
        rad = math.radians(angle)
        # Tick
        tx1 = cx + tick_inner_r * math.cos(rad)
        ty1 = cy - tick_inner_r * math.sin(rad)
        tx2 = cx + tick_outer_r * math.cos(rad)
        ty2 = cy - tick_outer_r * math.sin(rad)
        scale_svg += f'  <line x1="{tx1:.1f}" y1="{ty1:.1f}" x2="{tx2:.1f}" y2="{ty2:.1f}" stroke="#999" stroke-width="1.5"/>\n'
        # Label
        lx = cx + label_r * math.cos(rad)
        ly = cy - label_r * math.sin(rad)
        if angle > 135:
            anchor = "end"
        elif angle < 45:
            anchor = "start"
        else:
            anchor = "middle"
        scale_svg += f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="11" fill="#666" font-family="Arial,sans-serif">{value}</text>\n'

    # Text color for "Moderate" zone — use dark text since yellow is hard to read
    text_color = "#888" if zone_color == "#ffeb3b" else zone_color

    return f"""<svg viewBox="0 0 400 260" width="400" height="260" xmlns="http://www.w3.org/2000/svg">
{arcs_svg}{scale_svg}  <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#222" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="5" fill="#d32f2f"/>
  <circle cx="{cx}" cy="{cy}" r="8" fill="#333"/>
  <text x="{cx}" y="{cy + 30}" text-anchor="middle" font-size="28" font-weight="bold" fill="{text_color}" font-family="Arial,sans-serif">{clamped}</text>
  <text x="{cx}" y="{cy + 48}" text-anchor="middle" font-size="13" fill="#666" font-family="Arial,sans-serif">{zone_label}</text>
  <text x="{cx}" y="18" text-anchor="middle" font-size="12" fill="#999" font-family="Arial,sans-serif">US AQI (modeled)</text>
</svg>"""
