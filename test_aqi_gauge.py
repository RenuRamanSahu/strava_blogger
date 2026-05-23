from aqi_gauge import _build_svg

# Change this value to test different AQI levels
TEST_AQI = 72

if TEST_AQI <= 50:
    zone_label, zone_color = "Good", "#4caf50"
elif TEST_AQI <= 100:
    zone_label, zone_color = "Moderate", "#ffeb3b"
elif TEST_AQI <= 150:
    zone_label, zone_color = "Unhealthy (Sensitive)", "#ff9800"
elif TEST_AQI <= 200:
    zone_label, zone_color = "Unhealthy", "#f44336"
elif TEST_AQI <= 300:
    zone_label, zone_color = "Very Unhealthy", "#9c27b0"
else:
    zone_label, zone_color = "Hazardous", "#7e0023"

svg = _build_svg(TEST_AQI, zone_label, zone_color)

html = f"""<!DOCTYPE html>
<html><head><title>AQI Gauge Test</title></head>
<body style="background:#f5f5f5;display:flex;justify-content:center;align-items:center;min-height:100vh;">
<div style="background:white;padding:32px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
{svg}
</div>
</body></html>"""

with open("test_aqi_gauge.html", "w") as f:
    f.write(html)
print(f"Generated test_aqi_gauge.html with AQI = {TEST_AQI}")
