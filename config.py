import os

# --- CONFIGURATION (Loaded Securely From Render Environment variables) ---
STRAVA_VERIFY_TOKEN = os.environ.get("STRAVA_VERIFY_TOKEN")
STRAVA_CLIENT_ID = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_REFRESH_TOKEN = os.environ.get("STRAVA_REFRESH_TOKEN")

WP_USERNAME = os.environ.get("WP_USERNAME")
WP_APP_PASSWORD = os.environ.get("WP_APPLICATION_PASSWORD")
WP_SITE_URL = os.environ.get("WP_SITE_URL", "https://renuramansahu.com")
