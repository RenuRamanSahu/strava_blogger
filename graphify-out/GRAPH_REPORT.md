# Graph Report - .  (2026-06-08)

## Corpus Check
- Corpus is ~13,845 words - fits in a single context window. You may not need a graph.

## Summary
- 171 nodes · 311 edges · 10 communities
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 25 edges (avg confidence: 0.82)
- Token cost: 8,150 input · 3,240 output

## Community Hubs (Navigation)
- [[_COMMUNITY_AI Blog Generation|AI Blog Generation]]
- [[_COMMUNITY_Strava Data & Training Load|Strava Data & Training Load]]
- [[_COMMUNITY_WordPress Publishing & Pipeline Resilience|WordPress Publishing & Pipeline Resilience]]
- [[_COMMUNITY_FastAPI Webhook & Web App|FastAPI Webhook & Web App]]
- [[_COMMUNITY_Gauge Visualizations (ACWRAQI)|Gauge Visualizations (ACWR/AQI)]]
- [[_COMMUNITY_WordPress Upload Diagnostics|WordPress Upload Diagnostics]]
- [[_COMMUNITY_Weather & AQI Fetching|Weather & AQI Fetching]]
- [[_COMMUNITY_External APIs & Architecture|External APIs & Architecture]]
- [[_COMMUNITY_Route Map Rendering|Route Map Rendering]]
- [[_COMMUNITY_Running Metrics Theory|Running Metrics Theory]]

## God Nodes (most connected - your core abstractions)
1. `process_pipeline_background()` - 21 edges
2. `process_pipeline_streaming()` - 20 edges
3. `generate_blog_with_ai()` - 16 edges
4. `get_weather_for_activity()` - 11 edges
5. `_inject_charts()` - 9 edges
6. `generate_route_image()` - 9 edges
7. `get_activity_details()` - 9 edges
8. `upload_media_to_wordpress()` - 9 edges
9. `post_to_wordpress()` - 9 edges
10. `build_acwr_gauge_html()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Open-Meteo Historical and Forecast Weather API` --references--> `get_weather_for_activity()`  [INFERRED]
  codebase_documentation.md → weather.py
- `Google Gemini 2.5 Flash AI Model` --references--> `generate_blog_with_ai()`  [INFERRED]
  codebase_documentation.md → ai_client.py
- `Pillow Image Processing Library` --references--> `generate_route_image()`  [INFERRED]
  requirements.txt → map_image.py
- `polyline Route Encoding/Decoding` --references--> `generate_route_image()`  [INFERRED]
  requirements.txt → map_image.py
- `staticmap Route Map Rendering` --references--> `generate_route_image()`  [INFERRED]
  requirements.txt → map_image.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Strava Data Fetch Pipeline** — strava_get_strava_access_token, strava_get_activity_details, strava_get_activity_streams, strava_get_recent_activities [EXTRACTED 1.00]
- **AI Blog Generation & Title/Advice Flow** — ai_client_generate_blog_with_ai, ai_client_generate_blog_title, ai_client_generate_next_run_advice, ai_client_openrouter_chat [EXTRACTED 0.95]
- **WordPress Publishing Pipeline** — wordpress_upload_media_to_wordpress, wordpress_post_to_wordpress, wordpress_get_or_create_category [EXTRACTED 1.00]
- **Gauge Visualization Suite** — acwr_gauge_build_acwr_gauge_html, aqi_gauge_build_aqi_gauge_html [INFERRED 0.85]
- **Content Pipeline Orchestration** — pipeline_process_pipeline_background, pipeline_process_pipeline_streaming, app_handle_strava_event, app_trigger_pipeline [EXTRACTED 0.95]

## Communities (10 total, 0 thin omitted)

### Community 0 - "AI Blog Generation"
Cohesion: 0.10
Nodes (30): _build_gear_html(), _build_session_data(), _build_training_load_data(), _build_weather_data(), generate_blog_title(), generate_blog_with_ai(), generate_next_run_advice(), _inject_after_section() (+22 more)

### Community 1 - "Strava Data & Training Load"
Cohesion: 0.10
Nodes (29): debug_strava_write(), Tests whether the current Strava token has activity:write scope, process_pipeline_background(), Master background execution link connecting data fetching to publishing.     On, build_strava_description(), calculate_training_load(), compute_acwr_and_health(), _downsample_streams() (+21 more)

### Community 2 - "WordPress Publishing & Pipeline Resilience"
Cohesion: 0.16
Nodes (18): _ensure_metrics_defaults(), _fallback_blog_html(), process_pipeline_streaming(), Same pipeline as process_pipeline_background, but yields progress messages for S, Backfills required keys so downstream code never crashes on missing fields., Minimal blog HTML used when AI generation fails. Keeps the pipeline able to publ, _get_or_create_category(), post_to_wordpress() (+10 more)

### Community 3 - "FastAPI Webhook & Web App"
Cohesion: 0.15
Nodes (16): dashboard(), handle_strava_event(), Catches live real-time incoming workout notification markers, Verify the provided credentials match the WordPress credentials, Serves the manual trigger dashboard — protected by WordPress credentials, Accepts an activity ID or Strava URL, runs the pipeline, streams progress via SS, Listens for Strava's initial security subscription verification call, trigger_pipeline() (+8 more)

### Community 4 - "Gauge Visualizations (ACWR/AQI)"
Cohesion: 0.16
Nodes (12): build_acwr_gauge_html(), _build_svg(), Generates the raw SVG markup for the ACWR gauge, Builds an ACWR gauge as a base64-encoded SVG inside an <img> tag (WordPress-safe, build_aqi_gauge_html(), _build_svg(), Generates the raw SVG markup for the AQI gauge, Builds an AQI gauge as a base64-encoded SVG inside an <img> tag (WordPress-safe) (+4 more)

### Community 5 - "WordPress Upload Diagnostics"
Cohesion: 0.30
Nodes (13): attempt_multipart(), attempt_multipart_default_ua(), attempt_raw_body(), _auth_header(), main(), precheck_rest_root(), precheck_user(), AsyncClient (+5 more)

### Community 6 - "Weather & AQI Fetching"
Cohesion: 0.24
Nodes (11): _aqi_category(), _build_weather_summary(), _empty_weather(), get_weather_for_activity(), _get_with_retry(), AsyncClient, Response, Returns US AQI category label (+3 more)

### Community 7 - "External APIs & Architecture"
Cohesion: 0.22
Nodes (11): Strava Webhook Pipeline Architecture, AI-Driven Blog Post Generation from Run Metrics, Strava Webhook Real-Time Activity Event Handler, Google Gemini 2.5 Flash AI Model, Open-Meteo Historical and Forecast Weather API, Strava OAuth and Activity API, WordPress REST API with Basic Auth, Sports Performance Analyst System Prompt (+3 more)

### Community 8 - "Route Map Rendering"
Cohesion: 0.25
Nodes (8): Image, generate_route_image(), _overlay_metrics(), Draws semi-transparent panels with run stats and weather on the map image, Decodes a Strava polyline, renders the route on a map, and overlays run metrics., Pillow Image Processing Library, polyline Route Encoding/Decoding, staticmap Route Map Rendering

### Community 9 - "Running Metrics Theory"
Cohesion: 0.32
Nodes (8): Strava Blogger Codebase Complete Reference, ACWR Training Zone Classification and Injury Risk Levels, Air Quality Index Impact on Running Performance, Pace-to-Effort Ratio and Heart Rate Analysis, ACWR Calculation Formula and Zone Classification, Speed to Pace Conversion and Decimal Pace Calculation, Training Load Calculation (Acute and Chronic Load), Blog Post Section Structure and Content Guidelines

## Knowledge Gaps
- **9 isolated node(s):** `Image`, `Response`, `Response`, `Blog Title Generation Prompt Template`, `FastAPI Web Framework` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `generate_blog_with_ai()` connect `AI Blog Generation` to `Strava Data & Training Load`, `WordPress Publishing & Pipeline Resilience`, `Running Metrics Theory`, `External APIs & Architecture`?**
  _High betweenness centrality (0.193) - this node is a cross-community bridge._
- **Why does `process_pipeline_background()` connect `Strava Data & Training Load` to `AI Blog Generation`, `WordPress Publishing & Pipeline Resilience`, `FastAPI Webhook & Web App`, `Weather & AQI Fetching`, `External APIs & Architecture`, `Route Map Rendering`?**
  _High betweenness centrality (0.163) - this node is a cross-community bridge._
- **Why does `process_pipeline_streaming()` connect `WordPress Publishing & Pipeline Resilience` to `AI Blog Generation`, `Strava Data & Training Load`, `FastAPI Webhook & Web App`, `Weather & AQI Fetching`, `Route Map Rendering`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `generate_blog_with_ai()` (e.g. with `_fallback_blog_html()` and `Google Gemini 2.5 Flash AI Model`) actually correct?**
  _`generate_blog_with_ai()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Builds an ACWR gauge as a base64-encoded SVG inside an <img> tag (WordPress-safe`, `Generates the raw SVG markup for the ACWR gauge`, `Loads a prompt template from the prompts/ directory` to the rest of the system?**
  _69 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `AI Blog Generation` be split into smaller, more focused modules?**
  _Cohesion score 0.10080645161290322 - nodes in this community are weakly interconnected._
- **Should `Strava Data & Training Load` be split into smaller, more focused modules?**
  _Cohesion score 0.10114942528735632 - nodes in this community are weakly interconnected._