import math


def build_acwr_gauge_html(acwr_value: float) -> str:
    """Builds a pure SVG semi-circular ACWR gauge — no JavaScript required"""
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

    # SVG arc parameters
    cx, cy = 200, 180  # center of the arc
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

    return f"""
<div style="max-width:420px;margin:24px auto;text-align:center;">
<svg viewBox="0 0 400 220" xmlns="http://www.w3.org/2000/svg" style="max-width:400px;width:100%;">
  <!-- Zone arcs -->
{arcs_svg}
  <!-- Needle -->
  <line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#222" stroke-width="3.5" stroke-linecap="round"/>
  <circle cx="{nx:.1f}" cy="{ny:.1f}" r="5" fill="#d32f2f"/>
  <circle cx="{cx}" cy="{cy}" r="8" fill="#333"/>

  <!-- ACWR value -->
  <text x="{cx}" y="{cy - 18}" text-anchor="middle" font-size="28" font-weight="bold" fill="{zone_color}" font-family="-apple-system,BlinkMacSystemFont,sans-serif">{clamped:.2f}</text>
  <!-- Zone label -->
  <text x="{cx}" y="{cy + 2}" text-anchor="middle" font-size="13" fill="#666" font-family="-apple-system,BlinkMacSystemFont,sans-serif">{zone_label}</text>

  <!-- Scale labels -->
  <text x="38" y="{cy + 28}" text-anchor="start" font-size="12" fill="#999" font-family="-apple-system,BlinkMacSystemFont,sans-serif">0.0</text>
  <text x="{cx}" y="28" text-anchor="middle" font-size="12" fill="#999" font-family="-apple-system,BlinkMacSystemFont,sans-serif">1.0</text>
  <text x="362" y="{cy + 28}" text-anchor="end" font-size="12" fill="#999" font-family="-apple-system,BlinkMacSystemFont,sans-serif">2.0</text>
</svg>
</div>
"""
