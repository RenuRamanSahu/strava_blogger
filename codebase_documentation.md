# Strava Blogger — Codebase Documentation

> Automated pipeline that listens for Strava activity completions and publishes AI-generated blog posts to a WordPress site.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Directory Structure](#directory-structure)
4. [Module Reference](#module-reference)
   - [app.py — FastAPI Server & Webhook Handler](#apppy)
   - [pipeline.py — Orchestration Pipeline](#pipelinepy)
   - [strava.py — Strava API Integration](#stravapy)
   - [gemini_client.py — AI Content Generation](#gemini_clientpy)
   - [wordpress.py — WordPress Publishing](#wordpresspy)
   - [map_image.py — Route Map Rendering](#map_imagepy)
   - [weather.py — Weather Data Fetching](#weatherpy)
   - [models.py — Pydantic Data Models](#modelspy)
   - [config.py — Environment Configuration](#configpy)
5. [Data Flow](#data-flow)
6. [External APIs](#external-apis)
7. [Dependencies](#dependencies)
8. [Environment Variables](#environment-variables)

---

## Project Overview

When a running activity is completed on Strava, a webhook fires to this FastAPI application. The app then:

1. Fetches detailed activity metrics from the Strava API.
2. Computes training load analytics (Acute:Chronic Workload Ratio).
3. Retrieves weather conditions at the activity's location and time.
4. Generates a route map image with metrics overlay.
5. Uses Google Gemini AI to write a data-driven blog post.
6. Publishes the post (with featured image) to a WordPress site.
7. Updates the Strava activity description with a summary, health metrics, and a link back to the blog.

---

## Architecture Diagram

```
┌──────────┐   webhook POST    ┌──────────────┐
│  Strava  │ ───────────────▶  │   app.py     │
│  (event) │                   │  (FastAPI)   │
└──────────┘                   └──────┬───────┘
                                      │ background task
                                      ▼
                               ┌──────────────┐
                               │ pipeline.py  │
                               │ (orchestrator)│
                               └──┬──┬──┬──┬──┘
                    ┌─────────────┘  │  │  └──────────────┐
                    ▼                ▼  ▼                  ▼
             ┌──────────┐   ┌────────────────┐   ┌──────────────┐
             │ strava.py │   │ gemini_client  │   │ wordpress.py │
             │ (metrics, │   │ (AI blog,      │   │ (publish,    │
             │  ACWR,    │   │  title,        │   │  upload      │
             │  update)  │   │  advice)       │   │  media)      │
             └──────────┘   └────────────────┘   └──────────────┘
                    │                                     ▲
          ┌────────┴────────┐                             │
          ▼                 ▼                      featured image
   ┌────────────┐   ┌──────────┐                         │
   │ weather.py │   │map_image │ ────────────────────────┘
   │(Open-Meteo)│   │ (route   │
   └────────────┘   │  PNG)    │
                    └──────────┘
```

---

## Directory Structure

```
hobby_projects/
├── app.py               # FastAPI entry point, webhook endpoints
├── pipeline.py          # Orchestration: ties all modules together
├── strava.py            # Strava OAuth, activity fetch, ACWR, description update
├── gemini_client.py     # Google Gemini AI blog/title/advice generation
├── wordpress.py         # WordPress REST API: post creation, media upload
├── map_image.py         # Static route map rendering with metrics overlay
├── weather.py           # Open-Meteo weather API integration
├── models.py            # Pydantic models for webhook payloads
├── config.py            # Environment variable loader
├── requirements.txt     # Python dependencies
└── README.md            # Project summary
```

---

## Module Reference

---

### `app.py`

**Role:** FastAPI application entry point. Exposes webhook endpoints and a debug route.

| Endpoint | Method | Purpose |
|---|---|---|
| `/webhook` | `GET` | Strava subscription verification handshake. Validates `hub.verify_token` and echoes `hub.challenge`. |
| `/webhook` | `POST` | Receives real-time Strava activity events. On `activity.create`, spawns a background task to run the full pipeline. |
| `/debug/strava-write` | `GET` | Tests whether the current Strava token has `activity:write` scope by writing and reverting a test description. |

**Key behavior:** The POST webhook returns `200 OK` immediately and processes the pipeline asynchronously via FastAPI `BackgroundTasks`, ensuring Strava's webhook timeout is never exceeded.

**Server startup:** Runs via Uvicorn on `0.0.0.0:PORT` (default `8000`).

---

### `pipeline.py`

**Role:** Master orchestrator that sequences all steps from data fetching to publishing.

#### `process_pipeline_background(activity_id: int)`

Executes the full 9-step pipeline as a background task:

| Step | Action | Module Used |
|---|---|---|
| 1 | Acquire Strava access token (OAuth refresh) | `strava.get_strava_access_token` |
| 2 | Fetch activity metrics (distance, pace, HR, polyline, etc.) | `strava.get_activity_details` |
| 3 | Fetch recent activities (28 days) and compute ACWR + health | `strava.get_recent_activities`, `strava.compute_acwr_and_health` |
| 4 | Build Strava activity URL | — |
| 5 | Fetch weather at activity location and time | `weather.get_weather_for_activity` |
| 6 | Generate route map PNG with metrics overlay, upload to WordPress | `map_image.generate_route_image`, `wordpress.upload_media_to_wordpress` |
| 7 | Generate AI blog title + full HTML content | `gemini_client.generate_blog_title`, `gemini_client.generate_blog_with_gemini` |
| 8 | Publish blog post to WordPress (with featured image) | `wordpress.post_to_wordpress` |
| 9 | Generate next-run coaching advice, build Strava description, update activity | `gemini_client.generate_next_run_advice`, `strava.build_strava_description`, `strava.update_strava_description` |

Error handling wraps the entire pipeline with traceback logging.

---

### `strava.py`

**Role:** All Strava API interactions — authentication, data retrieval, analytics, and activity updates.

#### Functions

| Function | Signature | Description |
|---|---|---|
| `get_strava_access_token` | `(client) → str` | Exchanges a permanent refresh token for a short-lived (6h) access token via OAuth. |
| `get_activity_details` | `(activity_id, access_token, client) → dict` | Fetches full activity data and computes derived metrics (pace, stopped time, gear info, polyline). |
| `get_recent_activities` | `(access_token, client, days=28) → list` | Retrieves all activities from the last N days for workload analysis. |
| `calculate_training_load` | `(activity) → float` | Estimates training load as `duration_mins × intensity_factor` where intensity is normalized to 3 m/s ≈ 1.0. |
| `compute_acwr_and_health` | `(activities) → dict` | Calculates Acute:Chronic Workload Ratio (7-day acute vs 28-day chronic weekly average). Returns ACWR value, health status, injury risk level, run counts, and distance totals. |
| `build_strava_description` | `(metrics, training_data, blog_url, next_run_advice, weather) → str` | Constructs a multi-line activity description with blog link, coaching advice, ACWR data, gear, and weather. |
| `update_strava_description` | `(activity_id, access_token, description, client) → dict` | PUTs the description back to the Strava activity. |

#### ACWR Health Zones

| ACWR Range | Status | Injury Risk |
|---|---|---|
| < 0.8 | Undertraining | Low (detraining risk) |
| 0.8 – 1.3 | Optimal Training Zone | Low |
| 1.3 – 1.5 | Overreaching | Moderate |
| > 1.5 | Danger Zone | High |

#### Derived Metrics Computed

- `distance_km` — distance in km (from meters)
- `duration_mins` — moving time in minutes
- `average_pace` / `max_pace` — formatted as `M:SS /km`
- `stopped_mins` — elapsed minus moving time
- `gear` — shoe/gear name with total distance

---

### `gemini_client.py`

**Role:** AI content generation using Google Gemini 2.5 Flash.

#### Functions

| Function | Signature | Description |
|---|---|---|
| `generate_blog_with_gemini` | `(metrics, training_data, strava_url, weather) → str` | Generates a full 500–800 word HTML blog post with 6 structured sections: Run Snapshot, Pace & Effort Breakdown, Workload Intelligence, Physiological Impact, Recovery & Next Session, Training Trajectory. |
| `generate_blog_title` | `(metrics) → str` | Generates an SEO-friendly blog title (< 80 chars) referencing the athlete "Raman". |
| `generate_next_run_advice` | `(metrics, training_data) → str` | Generates a one-liner coaching recommendation (< 120 chars) for the next run. |
| `_gear_blog_instruction` | `(metrics) → str` | Internal helper that generates a prompt fragment for gear affiliate link mentions. |

#### AI Configuration

- **Model:** `gemini-2.5-flash`
- **Blog temperature:** 0.7 (balanced creativity)
- **Title temperature:** 0.9 (more creative)
- **Advice temperature:** 0.8
- **System instruction:** Professional fitness blogger tone, clean HTML output (`<h2>`, `<p>`, `<strong>`, `<ul>`, `<a>`).

#### Gear Affiliate Links

Gear names mapped in `config.GEAR_LINKS` are injected as affiliate `<a>` tags in the blog content (with `rel="nofollow"`).

---

### `wordpress.py`

**Role:** WordPress REST API integration for publishing posts and uploading media.

#### Functions

| Function | Signature | Description |
|---|---|---|
| `post_to_wordpress` | `(title, html_content, client, featured_media_id) → dict` | Creates a published blog post in the "Athletics" category. Attaches featured image if provided. |
| `upload_media_to_wordpress` | `(image_bytes, filename, client) → int` | Uploads a PNG image to the WordPress media library. Returns the media ID. |
| `_get_or_create_category` | `(name, client) → int` | Finds a WordPress category by name or creates it. Returns category ID. |
| `_wp_auth_headers` | `() → dict` | Builds Basic Auth headers from WordPress credentials. |

**Authentication:** HTTP Basic Auth using WordPress Application Passwords (Base64-encoded `username:app_password`).

---

### `map_image.py`

**Role:** Generates a static route map image with overlaid run metrics and weather data.

#### Functions

| Function | Signature | Description |
|---|---|---|
| `generate_route_image` | `(encoded_polyline, metrics, weather) → bytes` | Full pipeline: decodes polyline → renders route on OpenStreetMap tiles → overlays metrics panel → returns PNG bytes. |
| `_overlay_metrics` | `(map_image, metrics, weather) → Image` | Draws semi-transparent panels on the map: bottom-left (distance, pace, time + branding), top-right (weather conditions). |

#### Visual Details

- **Map size:** 800×600 pixels
- **Route color:** `#FC4C02` (Strava orange), 4px width
- **Tile provider:** OpenStreetMap (`tile.openstreetmap.org`)
- **Bottom-left panel:** Distance, Pace, Time in 3-column layout with `renuramansahu.com` branding
- **Top-right panel:** Temperature (with feels-like), humidity, wind speed
- **Font:** DejaVu Sans (falls back to PIL default)

---

### `weather.py`

**Role:** Fetches historical/forecast weather data from the Open-Meteo API.

#### Functions

| Function | Signature | Description |
|---|---|---|
| `get_weather_for_activity` | `(lat, lng, start_time, client) → dict` | Queries Open-Meteo for hourly weather at the activity's coordinates and start hour. Returns temperature, feels-like, humidity, dew point, wind speed, precipitation, and a one-line summary. |
| `_build_weather_summary` | `(temp, feels_like, humidity, wind_speed, precipitation) → str` | Formats a pipe-separated one-liner (e.g., `"24°C | feels 28°C | 65% humidity | wind 12 km/h"`). |
| `_empty_weather` | `() → dict` | Returns a dict with all weather fields set to `None` and summary `"N/A"`. |

**API:** [Open-Meteo](https://open-meteo.com/) — free, no API key required. Uses hourly granularity with automatic timezone detection.

#### Weather Data Fields

| Field | Key | Unit |
|---|---|---|
| Temperature | `temperature_c` | °C |
| Feels Like | `feels_like_c` | °C |
| Humidity | `humidity_pct` | % |
| Dew Point | `dew_point_c` | °C |
| Wind Speed | `wind_speed_kmh` | km/h |
| Precipitation | `precipitation_mm` | mm |
| Summary | `summary` | text |

---

### `models.py`

**Role:** Pydantic data models for request/response validation.

#### `StravaWebhookPayload`

Validates incoming Strava webhook POST payloads.

| Field | Type | Description |
|---|---|---|
| `object_type` | `str` | Entity type (`"activity"`, `"athlete"`) |
| `aspect_type` | `str` | Event type (`"create"`, `"update"`, `"delete"`) |
| `object_id` | `int` | Strava activity/athlete ID |
| `owner_id` | `int` | Strava athlete ID who owns the object |
| `subscription_id` | `int` | Webhook subscription ID |
| `event_time` | `int` | Unix timestamp of the event |

---

### `config.py`

**Role:** Centralised environment variable loading. All secrets are read from environment variables (designed for Render deployment).

| Variable | Config Key | Description |
|---|---|---|
| `STRAVA_VERIFY_TOKEN` | `STRAVA_VERIFY_TOKEN` | Token for webhook subscription verification |
| `STRAVA_CLIENT_ID` | `STRAVA_CLIENT_ID` | Strava OAuth app client ID |
| `STRAVA_CLIENT_SECRET` | `STRAVA_CLIENT_SECRET` | Strava OAuth app client secret |
| `STRAVA_REFRESH_TOKEN` | `STRAVA_REFRESH_TOKEN` | Permanent refresh token for token exchange |
| `WP_USERNAME` | `WP_USERNAME` | WordPress admin username |
| `WP_APPLICATION_PASSWORD` | `WP_APP_PASSWORD` | WordPress application password |
| `WP_SITE_URL` | `WP_SITE_URL` | WordPress site URL (default: `https://renuramansahu.com`) |

#### Gear Affiliate Links

```python
GEAR_LINKS = {
    "Asics Novoblast 5": "https://amzn.to/4djQPGH",
}
```

Maps Strava gear names (exact match) to Amazon affiliate URLs for blog insertion.

---

## Data Flow

```
Strava Webhook (activity.create)
       │
       ▼
  Validate payload (Pydantic)
       │
       ▼
  OAuth token refresh ──▶ Strava API
       │
       ├──▶ GET /activities/{id}  ──▶ Activity metrics dict
       │
       ├──▶ GET /athlete/activities (28d) ──▶ ACWR computation
       │
       ├──▶ Open-Meteo API ──▶ Weather dict
       │
       ├──▶ Decode polyline ──▶ StaticMap + PIL ──▶ PNG bytes
       │         │
       │         └──▶ WordPress Media Upload ──▶ featured_media_id
       │
       ├──▶ Gemini AI ──▶ Blog title + HTML content + coaching advice
       │
       ├──▶ WordPress REST API ──▶ Published post ──▶ blog_url
       │
       └──▶ Strava PUT /activities/{id} ──▶ Updated description
              (blog link + ACWR + weather + coaching advice)
```

---

## External APIs

| API | Purpose | Auth | Module |
|---|---|---|---|
| **Strava API v3** | Activity data, OAuth, description updates | OAuth 2.0 (refresh token flow) | `strava.py` |
| **Google Gemini** | AI blog content, title, and advice generation | API key (via `google-genai` SDK) | `gemini_client.py` |
| **WordPress REST API** | Blog post publishing, media uploads | HTTP Basic Auth (Application Passwords) | `wordpress.py` |
| **Open-Meteo** | Weather data (hourly, location-based) | None (free, keyless) | `weather.py` |
| **OpenStreetMap Tiles** | Map tile rendering for route images | None (free) | `map_image.py` |

---

## Dependencies

From `requirements.txt`:

| Package | Version | Purpose |
|---|---|---|
| `fastapi` | ≥ 0.110.0 | Web framework and webhook server |
| `pydantic` | ≥ 2.6.0 | Data validation for webhook payloads |
| `uvicorn` | ≥ 0.28.0 | ASGI server for FastAPI |
| `google-genai` | ≥ 0.1.0 | Google Gemini AI SDK |
| `httpx` | ≥ 0.27.0 | Async HTTP client for all API calls |
| `polyline` | ≥ 2.0.0 | Decodes Strava encoded polylines to coordinates |
| `staticmap` | ≥ 0.5.7 | Renders route lines on OpenStreetMap tiles |
| `Pillow` | ≥ 10.0.0 | Image manipulation and metrics overlay |

---

## Environment Variables

All secrets must be set as environment variables before running (designed for Render cloud deployment):

```
STRAVA_VERIFY_TOKEN=<webhook verification token>
STRAVA_CLIENT_ID=<strava oauth client id>
STRAVA_CLIENT_SECRET=<strava oauth client secret>
STRAVA_REFRESH_TOKEN=<strava permanent refresh token>
WP_USERNAME=<wordpress username>
WP_APPLICATION_PASSWORD=<wordpress application password>
WP_SITE_URL=https://renuramansahu.com
```
