"""Generate a local HTML file to preview the ACWR gauge SVG"""
from acwr_gauge import build_acwr_gauge_html

# Change this value to test different zones:
# < 0.8 = Under-training, 0.8–1.3 = Optimal, 1.3–1.5 = Overreaching, > 1.5 = Danger
TEST_ACWR = 1.15

html = f"""<!DOCTYPE html>
<html><head><title>ACWR Gauge Test</title>
<style>body {{ font-family: -apple-system, sans-serif; background: #f5f5f5; padding: 40px; }}</style>
</head><body>
<h2 style="text-align:center;">ACWR Gauge Preview (value = {TEST_ACWR})</h2>
{build_acwr_gauge_html(TEST_ACWR)}
</body></html>
"""

with open("test_gauge.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Written test_gauge.html — open it in your browser.")
