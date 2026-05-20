import io
import polyline as pl
from staticmap import StaticMap, Line
from PIL import Image, ImageDraw, ImageFont


def generate_route_image(encoded_polyline: str, metrics: dict, weather: dict = None) -> bytes:
    """Decodes a Strava polyline, renders the route on a map, and overlays run metrics.
    Returns the final image as PNG bytes ready for upload."""

    # 1. Decode polyline to lat/lng coordinates
    coordinates = pl.decode(encoded_polyline)
    # staticmap expects (lng, lat) pairs
    line_coords = [(lng, lat) for lat, lng in coordinates]

    # 2. Render route on a static map tile
    m = StaticMap(800, 600, url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png")
    line = Line(line_coords, "#FC4C02", 4)  # Strava orange
    m.add_line(line)
    map_image = m.render()

    # 3. Overlay metrics and weather
    overlay = _overlay_metrics(map_image, metrics, weather or {})

    # 4. Export as PNG bytes
    buffer = io.BytesIO()
    overlay.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def _overlay_metrics(map_image: Image.Image, metrics: dict, weather: dict) -> Image.Image:
    """Draws semi-transparent panels with run stats and weather on the map image"""
    img = map_image.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Try to load a clean font, fall back to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        font_weather = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except OSError:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_weather = ImageFont.load_default()

    # ── Bottom-left panel: run metrics ──
    panel_w, panel_h = 480, 120
    panel_x, panel_y = 20, img.height - panel_h - 20

    draw.rounded_rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        radius=12,
        fill=(0, 0, 0, 180),
    )

    # Stat values
    distance = f"{metrics.get('distance_km', 0)} km"
    pace = f"{metrics.get('average_pace', 'N/A')} /km"
    duration = f"{metrics.get('duration_mins', 0)} min"

    padding = 20
    usable_w = panel_w - 2 * padding
    col_w = usable_w // 3
    stats = [
        ("DISTANCE", distance),
        ("PACE", pace),
        ("TIME", duration),
    ]

    for i, (label, value) in enumerate(stats):
        cx = panel_x + padding + col_w * i + col_w // 2

        bbox = draw.textbbox((0, 0), value, font=font_large)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, panel_y + 20), value, fill=(255, 255, 255, 255), font=font_large)

        bbox = draw.textbbox((0, 0), label, font=font_small)
        tw = bbox[2] - bbox[0]
        draw.text((cx - tw // 2, panel_y + 58), label, fill=(180, 180, 180, 255), font=font_small)

    # Branding line
    brand = "renuramansahu.com"
    bbox = draw.textbbox((0, 0), brand, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(
        (panel_x + panel_w // 2 - tw // 2, panel_y + panel_h - 30),
        brand,
        fill=(252, 76, 2, 255),
        font=font_small,
    )

    # ── Top-right panel: weather ──
    if weather and weather.get("temperature_c") is not None:
        temp = weather.get("temperature_c")
        feels = weather.get("feels_like_c")
        humidity = weather.get("humidity_pct")
        wind = weather.get("wind_speed_kmh")

        weather_lines = [f"\U0001f321\ufe0f {temp}\u00b0C"]
        if feels is not None and abs(feels - temp) >= 2:
            weather_lines[0] += f" (feels {feels}\u00b0C)"
        if humidity is not None:
            weather_lines.append(f"\U0001f4a7 {humidity}%")
        if wind is not None and wind > 0:
            weather_lines.append(f"\U0001f32c\ufe0f {wind} km/h")

        weather_text = "  ".join(weather_lines)
        bbox = draw.textbbox((0, 0), weather_text, font=font_weather)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        wp_w, wp_h = tw + 24, th + 16
        wp_x = img.width - wp_w - 20
        wp_y = 20

        draw.rounded_rectangle(
            [wp_x, wp_y, wp_x + wp_w, wp_y + wp_h],
            radius=10,
            fill=(0, 0, 0, 160),
        )
        draw.text(
            (wp_x + 12, wp_y + 8),
            weather_text,
            fill=(255, 255, 255, 230),
            font=font_weather,
        )

    return Image.alpha_composite(img, overlay).convert("RGB")
