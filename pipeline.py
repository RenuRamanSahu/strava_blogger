import httpx
from strava import (
    get_strava_access_token, get_activity_details, get_activity_streams,
    get_recent_activities, compute_acwr_and_health, build_strava_description,
    update_strava_description, extract_user_note,
)
from ai_client import generate_blog_with_ai, generate_blog_title, generate_next_run_advice, generate_user_note_summary, generate_meta_description
from wordpress import post_to_wordpress, upload_media_to_wordpress
from map_image import generate_route_image
from weather import get_weather_for_activity
from config import WP_SITE_URL
from db import init_db, save_activity


async def process_pipeline_background(activity_id: int):
    """Master background execution link connecting data fetching to publishing.
    Only Step 8 (post_to_wordpress) is a hard stop — every other call has a fallback.
    """
    # ensure local DB exists
    try:
        init_db()
    except Exception:
        print("⚠️ Could not initialize local DB; continuing without persistence")

    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; strava-blogger/1.0; +https://renuramansahu.com)",
                "Accept": "application/json, */*",
            },
            timeout=60,
        ) as client:
            # 1. Fetch Working Strava Authorization Token
            access_token = None
            try:
                access_token = await get_strava_access_token(client)
                print(f"\u2705 Step 1: Strava token acquired")
            except Exception as e:
                print(f"\u26a0\ufe0f Step 1: Strava token fetch failed \u2014 {e}; subsequent Strava calls will be skipped")

            # 2. Extract Specific Workout Metrics
            metrics = {}
            if access_token:
                try:
                    metrics = await get_activity_details(activity_id, access_token, client)
                    print(f"\u2705 Step 2: Activity metrics fetched \u2014 {metrics.get('name')}")
                except Exception as e:
                    print(f"\u26a0\ufe0f Step 2: Activity metrics fetch failed \u2014 {e}; using minimal placeholders")
            metrics = _ensure_metrics_defaults(metrics, activity_id)

            # 3. Fetch recent activities and compute ACWR + run health
            training_data = {}
            if access_token:
                try:
                    recent_activities = await get_recent_activities(access_token, client)
                    training_data = compute_acwr_and_health(recent_activities)
                    print(f"\u2705 Step 3: ACWR computed \u2014 {training_data.get('acwr')} ({training_data.get('health_status')})")
                except Exception as e:
                    print(f"\u26a0\ufe0f Step 3: ACWR computation failed \u2014 {e}; continuing without training load")

            # 4a. Build Strava activity URL
            strava_url = f"https://www.strava.com/activities/{activity_id}"

            # 4b. Fetch elevation profile streams (distance + altitude)
            elevation_profile = {}
            if access_token:
                try:
                    elevation_profile = await get_activity_streams(activity_id, access_token, client) or {}
                    if elevation_profile:
                        print(f"\u2705 Step 4b: Elevation profile fetched \u2014 {len(elevation_profile.get('distance_km', []))} points")
                    else:
                        print(f"\u26a0\ufe0f Step 4b: No stream data \u2014 skipping elevation profile")
                except Exception as e:
                    print(f"\u26a0\ufe0f Step 4b: Elevation stream fetch failed \u2014 {e}; continuing without elevation profile")

            # 5. Fetch weather conditions at activity location and time
            weather = {}
            start_latlng = metrics.get("start_latlng", [])
            if start_latlng and len(start_latlng) == 2:
                try:
                    weather = await get_weather_for_activity(
                        start_latlng[0], start_latlng[1], metrics["start_date_local_raw"], client
                    )
                    print(f"\u2705 Step 5: Weather fetched \u2014 {weather.get('summary')}")
                except Exception as weather_err:
                    weather = {}
                    print(f"\u26a0\ufe0f Step 5: Weather pipeline failed \u2014 {weather_err}; continuing without weather")
            else:
                print(f"\u26a0\ufe0f Step 5: No location data \u2014 skipping weather")

            # 6. Generate route map image with metrics overlay
            featured_media_id = None
            polyline = metrics.get("polyline", "")
            if polyline:
                try:
                    image_bytes = generate_route_image(polyline, metrics, weather)
                    filename = f"run-map-{activity_id}.png"
                    featured_media_id = await upload_media_to_wordpress(image_bytes, filename, client)
                    print(f"\u2705 Step 6: Route map generated and uploaded \u2014 media ID {featured_media_id}")
                except Exception as map_err:
                    print(f"\u26a0\ufe0f Step 6: Route map generation/upload failed \u2014 {map_err}; continuing without featured image")
            else:
                print(f"\u26a0\ufe0f Step 6: No polyline data \u2014 skipping map image")

            # 7. Generate AI blog content, then derive title from the content
            user_note = extract_user_note(metrics.get("user_description", ""))
            if user_note:
                print(f"✅ Step 6b: User note detected ({len(user_note)} chars)")
            blog_html = ""
            try:
                blog_html = await generate_blog_with_ai(metrics, training_data, strava_url, weather, elevation_profile, user_note=user_note)
                print(f"\u2705 Step 7a: Blog content generated ({len(blog_html)} chars)")
            except Exception as e:
                print(f"\u26a0\ufe0f Step 7a: AI blog generation failed \u2014 {e}; using fallback summary")
            if not blog_html:
                blog_html = _fallback_blog_html(metrics, training_data, weather, strava_url)

            post_title = ""
            try:
                post_title = await generate_blog_title(metrics, blog_html)
                print(f"\u2705 Step 7b: AI title generated \u2014 {post_title}")
            except Exception as e:
                print(f"\u26a0\ufe0f Step 7b: AI title generation failed \u2014 {e}; using activity name")
            if not post_title:
                post_title = metrics.get("name") or f"Run — Activity {activity_id}"

            meta_description = ""
            try:
                meta_description = await generate_meta_description(post_title, blog_html, metrics)
                print(f"\u2705 Step 7c: Meta description generated ({len(meta_description)} chars)")
            except Exception as e:
                print(f"\u26a0\ufe0f Step 7c: Meta description generation failed \u2014 {e}; WP will auto-truncate first paragraph")

            # 8. Upload Content Directly onto renuramansahu.com (with featured image)
            # HARD STOP: this is the only step that fails the whole pipeline.
            wp_result = await post_to_wordpress(post_title, blog_html, client, featured_media_id, excerpt=meta_description)
            blog_url = f"{WP_SITE_URL}/?p={wp_result['id']}"
            print(f"\u2705 Step 8: Blog published \u2014 {blog_url}")

            # Persist activity + derived training data for later insights
            try:
                save_activity(activity_id, metrics, training_data, weather, elevation_profile=elevation_profile, blog_url=blog_url, post_title=post_title, meta_description=meta_description)
                print(f"\u2705 Step 8b: Activity saved to local DB (id={activity_id})")
            except Exception as e:
                print(f"\u26a0\ufe0f Step 8b: Failed to save activity to DB — {e}")

            # 9. Update Strava activity description with summary + health metrics + weather + blog link
            next_run_advice = ""
            try:
                next_run_advice = await generate_next_run_advice(metrics, training_data)
                print(f"\u2705 Step 9a: Next run advice generated \u2014 {next_run_advice}")
            except Exception as e:
                print(f"\u26a0\ufe0f Step 9a: Next run advice generation failed \u2014 {e}; skipping advice")

            if access_token:
                try:
                    description = build_strava_description(metrics, training_data, blog_url, next_run_advice, weather)
                    await update_strava_description(activity_id, access_token, description, client)
                    print(f"\u2705 Step 9b: Strava description updated")
                except Exception as e:
                    print(f"\u26a0\ufe0f Step 9b: Strava description update failed \u2014 {e}; blog is still published")
            else:
                print(f"\u26a0\ufe0f Step 9b: No Strava token \u2014 skipping description update")

    except Exception as e:
        import traceback
        print(f"❌ Error executing content pipeline: {e}")
        traceback.print_exc()


async def process_pipeline_streaming(activity_id: int):
    """Same pipeline as process_pipeline_background, but yields progress messages for SSE streaming.
    Only Step 8 (post_to_wordpress) is a hard stop — every other call has a fallback.
    """
    # ensure local DB exists
    try:
        init_db()
    except Exception:
        yield "⚠️ Could not initialize local DB; continuing without persistence"

    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; strava-blogger/1.0; +https://renuramansahu.com)",
                "Accept": "application/json, */*",
            },
            timeout=60,
        ) as client:
            access_token = None
            try:
                access_token = await get_strava_access_token(client)
                yield "✅ Step 1: Strava token acquired"
            except Exception as e:
                yield f"⚠️ Step 1: Strava token fetch failed — {e}; subsequent Strava calls will be skipped"

            metrics = {}
            if access_token:
                try:
                    metrics = await get_activity_details(activity_id, access_token, client)
                    yield f"✅ Step 2: Activity metrics fetched — {metrics.get('name')}"
                except Exception as e:
                    yield f"⚠️ Step 2: Activity metrics fetch failed — {e}; using minimal placeholders"
            metrics = _ensure_metrics_defaults(metrics, activity_id)

            training_data = {}
            if access_token:
                try:
                    recent_activities = await get_recent_activities(access_token, client)
                    training_data = compute_acwr_and_health(recent_activities)
                    yield f"✅ Step 3: ACWR computed — {training_data.get('acwr')} ({training_data.get('health_status')})"
                except Exception as e:
                    yield f"⚠️ Step 3: ACWR computation failed — {e}; continuing without training load"

            strava_url = f"https://www.strava.com/activities/{activity_id}"

            elevation_profile = {}
            if access_token:
                try:
                    elevation_profile = await get_activity_streams(activity_id, access_token, client) or {}
                    if elevation_profile:
                        yield f"✅ Step 4: Elevation profile fetched — {len(elevation_profile.get('distance_km', []))} points"
                    else:
                        yield "⚠️ Step 4: No stream data — skipping elevation profile"
                except Exception as e:
                    yield f"⚠️ Step 4: Elevation stream fetch failed — {e}; continuing without elevation profile"

            weather = {}
            start_latlng = metrics.get("start_latlng", [])
            if start_latlng and len(start_latlng) == 2:
                try:
                    weather = await get_weather_for_activity(
                        start_latlng[0], start_latlng[1], metrics["start_date_local_raw"], client
                    )
                    yield f"✅ Step 5: Weather fetched — {weather.get('summary')}"
                except Exception as weather_err:
                    weather = {}
                    yield f"⚠️ Step 5: Weather pipeline failed — {weather_err}; continuing without weather"
            else:
                yield "⚠️ Step 5: No location data — skipping weather"

            featured_media_id = None
            polyline = metrics.get("polyline", "")
            if polyline:
                try:
                    image_bytes = generate_route_image(polyline, metrics, weather)
                    filename = f"run-map-{activity_id}.png"
                    featured_media_id = await upload_media_to_wordpress(image_bytes, filename, client)
                    yield f"✅ Step 6: Route map generated and uploaded — media ID {featured_media_id}"
                except Exception as map_err:
                    yield f"⚠️ Step 6: Route map generation/upload failed — {map_err}; continuing without featured image"
            else:
                yield "⚠️ Step 6: No polyline data — skipping map image"

            blog_html = ""
            user_note = extract_user_note(metrics.get("user_description", ""))
            if user_note:
                yield f"✅ Step 6b: User note detected ({len(user_note)} chars)"
            try:
                blog_html = await generate_blog_with_ai(metrics, training_data, strava_url, weather, elevation_profile, user_note=user_note)
                yield f"✅ Step 7a: Blog content generated ({len(blog_html)} chars)"
            except Exception as e:
                yield f"⚠️ Step 7a: AI blog generation failed — {e}; using fallback summary"
            if not blog_html:
                blog_html = _fallback_blog_html(metrics, training_data, weather, strava_url)

            post_title = ""
            try:
                post_title = await generate_blog_title(metrics, blog_html)
                yield f"✅ Step 7b: AI title generated — {post_title}"
            except Exception as e:
                yield f"⚠️ Step 7b: AI title generation failed — {e}; using activity name"
            if not post_title:
                post_title = metrics.get("name") or f"Run — Activity {activity_id}"

            meta_description = ""
            try:
                meta_description = await generate_meta_description(post_title, blog_html, metrics)
                yield f"\u2705 Step 7c: Meta description generated ({len(meta_description)} chars)"
            except Exception as e:
                yield f"\u26a0\ufe0f Step 7c: Meta description generation failed \u2014 {e}; WP will auto-truncate first paragraph"

            # HARD STOP: only Step 8 fails the whole pipeline.
            wp_result = await post_to_wordpress(post_title, blog_html, client, featured_media_id, excerpt=meta_description)
            blog_url = f"{WP_SITE_URL}/?p={wp_result['id']}"
            yield f"✅ Step 8: Blog published — {blog_url}"

            # Persist activity for later insights
            try:
                save_activity(activity_id, metrics, training_data, weather, elevation_profile=elevation_profile, blog_url=blog_url, post_title=post_title, meta_description=meta_description)
                yield f"✅ Step 8b: Activity saved to local DB (id={activity_id})"
            except Exception as e:
                yield f"⚠️ Step 8b: Failed to save activity to DB — {e}"

            next_run_advice = ""
            try:
                next_run_advice = await generate_next_run_advice(metrics, training_data)
                yield f"✅ Step 9a: Next run advice generated — {next_run_advice}"
            except Exception as e:
                yield f"⚠️ Step 9a: Next run advice generation failed — {e}; skipping advice"

            note_summary = ""
            if user_note:
                try:
                    note_summary = await generate_user_note_summary(user_note)
                    yield f"✅ Step 9a2: User note summarized — {note_summary}"
                except Exception as e:
                    yield f"⚠️ Step 9a2: User note summarization failed — {e}; skipping note in Strava description"

            if access_token:
                try:
                    description = build_strava_description(metrics, training_data, blog_url, next_run_advice, weather, note_summary=note_summary)
                    await update_strava_description(activity_id, access_token, description, client)
                    yield "✅ Step 9b: Strava description updated"
                except Exception as e:
                    yield f"⚠️ Step 9b: Strava description update failed — {e}; blog is still published"
            else:
                yield "⚠️ Step 9b: No Strava token — skipping description update"

            yield f"🎉 Done! Blog post published at {blog_url}"

    except Exception as e:
        yield f"❌ Pipeline error: {e}"


def _ensure_metrics_defaults(metrics: dict, activity_id: int) -> dict:
    """Backfills required keys so downstream code never crashes on missing fields."""
    metrics = dict(metrics) if metrics else {}
    metrics.setdefault("name", f"Activity {activity_id}")
    metrics.setdefault("start_latlng", [])
    metrics.setdefault("polyline", "")
    metrics.setdefault("start_date_local_raw", "")
    metrics.setdefault("user_description", "")
    return metrics


def _fallback_blog_html(metrics: dict, training_data: dict, weather: dict, strava_url: str) -> str:
    """Minimal blog HTML used when AI generation fails. Keeps the pipeline able to publish."""
    name = metrics.get("name", "Run")
    distance = metrics.get("distance_km") or metrics.get("distance")
    duration = metrics.get("moving_time_str") or metrics.get("moving_time")
    pace = metrics.get("pace_per_km") or metrics.get("average_speed")

    stats_rows = []
    if distance is not None:
        stats_rows.append(f"<li><strong>Distance:</strong> {distance} km</li>")
    if duration is not None:
        stats_rows.append(f"<li><strong>Duration:</strong> {duration}</li>")
    if pace is not None:
        stats_rows.append(f"<li><strong>Pace:</strong> {pace}</li>")
    if weather and weather.get("summary") and weather["summary"] != "N/A":
        stats_rows.append(f"<li><strong>Conditions:</strong> {weather['summary']}</li>")
    if training_data.get("acwr") is not None:
        stats_rows.append(f"<li><strong>ACWR:</strong> {training_data['acwr']} ({training_data.get('health_status', '')})</li>")

    stats_html = f"<ul>{''.join(stats_rows)}</ul>" if stats_rows else ""
    return (
        f"<h2>{name}</h2>"
        f"<p>Automatically generated summary \u2014 the AI writer is temporarily unavailable, so here are the key stats.</p>"
        f"{stats_html}"
        f'<p><a href="{strava_url}" target="_blank" rel="noopener">View activity on Strava</a></p>'
    )
