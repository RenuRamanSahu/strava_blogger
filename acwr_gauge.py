import math
import base64


def build_acwr_gauge_html(acwr_value: float) -> str:
    """Builds an ACWR gauge as a base64-encoded SVG inside an <img> tag (WordPress-safe)"""
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

    svg = _build_svg(clamped, zone_label, zone_color)
    encoded = base64.b64encode(svg.encode("utf-8")).decode("utf-8")
    data_uri = f"data:image/svg+xml;base64,{encoded}"

    return (
        f'<div style="max-width:420px;margin:24px auto;text-align:center;">'
        f'<img src="{data_uri}" alt="ACWR Gauge: {clamped:.2f} — {zone_label}" '
        f'style="max-width:400px;width:100%;" />'
        f'</div>\n'
    )


def _build_svg(clamped: float, zone_label: str, zone_color: str) -> str:
    """Generates the raw SVG markup for the ACWR gauge"""

    # SVG arc parameters
    cx, cy = 200, 195  # center of the arc
    r = 140            # radius
    stroke_w = 22      # arc thickness

    def point(angle_deg):
        """Convert angle (degrees from 3 o'clock) to SVG coordinates"""
        rad = math.radians(angle_deg)
        return (cx + r * math.cos(rad), cy - r * math.sin(rad))

    def arc_path(start_deg, end_deg):
        """SVG arc path for a portion of the semi-circle"""
        x1, y1 = point(start_deg)
        x2, y2 = point(end_deg)
        sweep = start_deg - end_deg
        large_arc = 1 if sweep > 180 else 0
        return f"M {x1:.1f} {y1:.1f} A {r} {r} 0 {large_arc} 1 {x2:.1f} {y2:.1f}"

    # Semi-circle from 180° (left) to 0° (right)
    # ACWR zones: 0.0=180°, 0.8=108°, 1.3=63°, 1.5=45°, 2.0=0°
    zones = [
        (180, 108, "#7eb8da"),  # 0.0–0.8 Under-training
        (108, 63,  "#4caf50"),  # 0.8–1.3 Optimal
        (63,  45,  "#ff9800"),  # 1.3–1.5 Overreaching
        (45,  0,   "#f44336"),  # 1.5–2.0 Danger
    ]

    # Build zone arcs
    arcs_svg = ""
    for start, end, color in zones:
        path = arc_path(start, end)
        arcs_svg += f'  <path d="{path}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="butt"/>\n'

    # Needle: map ACWR value to angle (0.0→180°, 2.0→0°)
    needle_angle = 180 - (clamped / 2.0) * 180
    needle_rad = math.radians(needle_angle)
    needle_len = r - 10
    nx = cx + needle_len * math.cos(needle_rad)
    ny = cy - needle_len * math.sin(needle_rad)

    # Scale ticks and labels placed just outside the arc along a consistent circular path
    tick_inner_r = r + stroke_w / 2 + 2
    tick_outer_r = r + stroke_w / 2 + 10
    label_r = r + stroke_w / 2 + 22
    scale_svg = ""
    for value in [0.0, 0.8, 1.0, 1.3, 1.5, 2.0]:
        angle = 180 - (value / 2.0) * 180
        rad = math.radians(angle)
        # Tick line
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
        display = f"{value:.1f}" if value in (0.0, 1.0, 2.0) else str(value)
        scale_svg += f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="11" fill="#666" font-family="Arial,sans-serif">{display}</text>\n'

    return f"""<svg viewBox="0 0 400 260" xmlns="http://www.w3.org/2000/svg">
{arcs_svg}{scale_svg}  <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#222" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="5" fill="#d32f2f"/>
  <circle cx="{cx}" cy="{cy}" r="8" fill="#333"/>
  <text x="{cx}" y="{cy + 30}" text-anchor="middle" font-size="28" font-weight="bold" fill="{zone_color}" font-family="Arial,sans-serif">{clamped:.2f}</text>
  <text x="{cx}" y="{cy + 48}" text-anchor="middle" font-size="13" fill="#666" font-family="Arial,sans-serif">{zone_label}</text>
</svg>"""
