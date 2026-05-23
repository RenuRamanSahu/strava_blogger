import os

# --- CONFIGURATION (Loaded Securely From Render Environment variables) ---
STRAVA_VERIFY_TOKEN = os.environ.get("STRAVA_VERIFY_TOKEN")
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")

WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APPLICATION_PASSWORD")
WP_SITE_URL = os.environ.get("WP_SITE_URL", "https://renuramansahu.com")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")

# --- GEAR AFFILIATE LINKS ---
# Add/remove items as your gear changes. All entries are shown at the end of each post.
GEAR_AFFILIATE = [
    {"name": "Asics Novoblast 5", "link": "https://amzn.to/4djQPGH", "type": "Shoes"},
]
