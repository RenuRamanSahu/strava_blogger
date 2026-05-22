import httpx
from strava import (
    get_strava_access_token, get_activity_details, get_activity_streams,
    get_recent_activities, compute_acwr_and_health, build_strava_description,
    update_strava_description,
)
from ai_client import generate_blog_with_ai, generate_blog_title, generate_next_run_advice
from wordpress import post_to_wordpress, upload_media_to_wordpress
from map_image import generate_route_image
from weather import get_weather_for_activity
from config import WP_SITE_URL


async def process_pipeline_background(activity_id: int):
    """Master background execution link connecting data fetching to publishing"""
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch Working Strava Authorization Token
            access_token = await get_strava_access_token(client)
            print(f"\u2705 Step 1: Strava token acquired")

            # 2. Extract Specific Workout Metrics
            metrics = await get_activity_details(activity_id, access_token, client)
            print(f"\u2705 Step 2: Activity metrics fetched \u2014 {metrics.get('name')}")

            # 3. Fetch recent activities and compute ACWR + run health
            recent_activities = await get_recent_activities(access_token, client)
            training_data = compute_acwr_and_health(recent_activities)
            print(f"\u2705 Step 3: ACWR computed \u2014 {training_data.get('acwr')} ({training_data.get('health_status')})")

            # 4a. Build Strava activity URL
            strava_url = f"https://www.strava.com/activities/{activity_id}"

            # 4b. Fetch elevation profile streams (distance + altitude)
            elevation_profile = await get_activity_streams(activity_id, access_token, client)
            if elevation_profile:
                print(f"\u2705 Step 4b: Elevation profile fetched \u2014 {len(elevation_profile.get('distance_km', []))} points")
            else:
                print(f"\u26a0\ufe0f Step 4b: No stream data \u2014 skipping elevation profile")

            # 5. Fetch weather conditions at activity location and time
            weather = {}
            start_latlng = metrics.get("start_latlng", [])
            if start_latlng and len(start_latlng) == 2:
                weather = await get_weather_for_activity(
                    start_latlng[0], start_latlng[1], metrics["start_date_local"], client
                )
                print(f"\u2705 Step 5: Weather fetched \u2014 {weather.get('summary')}")
            else:
                print(f"\u26a0\ufe0f Step 5: No location data \u2014 skipping weather")

            # 6. Generate route map image with metrics overlay
            featured_media_id = None
            polyline = metrics.get("polyline", "")
            if polyline:
                image_bytes = generate_route_image(polyline, metrics, weather)
                filename = f"run-map-{activity_id}.png"
                featured_media_id = await upload_media_to_wordpress(image_bytes, filename, client)
                print(f"\u2705 Step 6: Route map generated and uploaded \u2014 media ID {featured_media_id}")
            else:
                print(f"\u26a0\ufe0f Step 6: No polyline data \u2014 skipping map image")

            # 7. Generate AI blog title and content (includes weather + Strava link in blog)
            post_title = await generate_blog_title(metrics)
            print(f"\u2705 Step 7a: AI title generated \u2014 {post_title}")
            blog_html = await generate_blog_with_ai(metrics, training_data, strava_url, weather, elevation_profile)
            print(f"\u2705 Step 7b: Blog content generated ({len(blog_html)} chars)")

            # 8. Upload Content Directly onto renuramansahu.com (with featured image)
            wp_result = await post_to_wordpress(post_title, blog_html, client, featured_media_id)
            blog_url = f"{WP_SITE_URL}/?p={wp_result['id']}"
            print(f"\u2705 Step 8: Blog published \u2014 {blog_url}")

            # 9. Update Strava activity description with summary + health metrics + weather + blog link
            next_run_advice = await generate_next_run_advice(metrics, training_data)
            print(f"\u2705 Step 9a: Next run advice generated \u2014 {next_run_advice}")
            description = build_strava_description(metrics, training_data, blog_url, next_run_advice, weather)
            await update_strava_description(activity_id, access_token, description, client)
            print(f"\u2705 Step 9b: Strava description updated")

    except Exception as e:
        import traceback
        print(f"❌ Error executing content pipeline: {e}")
        traceback.print_exc()


async def process_pipeline_streaming(activity_id: int):
    """Same pipeline as process_pipeline_background, but yields progress messages for SSE streaming"""
    try:
        async with httpx.AsyncClient() as client:
            access_token = await get_strava_access_token(client)
            yield "✅ Step 1: Strava token acquired"

            metrics = await get_activity_details(activity_id, access_token, client)
            yield f"✅ Step 2: Activity metrics fetched — {metrics.get('name')}"

            recent_activities = await get_recent_activities(access_token, client)
            training_data = compute_acwr_and_health(recent_activities)
            yield f"✅ Step 3: ACWR computed — {training_data.get('acwr')} ({training_data.get('health_status')})"

            strava_url = f"https://www.strava.com/activities/{activity_id}"

            elevation_profile = await get_activity_streams(activity_id, access_token, client)
            if elevation_profile:
                yield f"✅ Step 4: Elevation profile fetched — {len(elevation_profile.get('distance_km', []))} points"
            else:
                yield "⚠️ Step 4: No stream data — skipping elevation profile"

            weather = {}
            start_latlng = metrics.get("start_latlng", [])
            if start_latlng and len(start_latlng) == 2:
                weather = await get_weather_for_activity(
                    start_latlng[0], start_latlng[1], metrics["start_date_local"], client
                )
                yield f"✅ Step 5: Weather fetched — {weather.get('summary')}"
            else:
                yield "⚠️ Step 5: No location data — skipping weather"

            featured_media_id = None
            polyline = metrics.get("polyline", "")
            if polyline:
                image_bytes = generate_route_image(polyline, metrics, weather)
                filename = f"run-map-{activity_id}.png"
                featured_media_id = await upload_media_to_wordpress(image_bytes, filename, client)
                yield f"✅ Step 6: Route map generated and uploaded — media ID {featured_media_id}"
            else:
                yield "⚠️ Step 6: No polyline data — skipping map image"

            post_title = await generate_blog_title(metrics)
            yield f"✅ Step 7a: AI title generated — {post_title}"
            blog_html = await generate_blog_with_ai(metrics, training_data, strava_url, weather, elevation_profile)
            yield f"✅ Step 7b: Blog content generated ({len(blog_html)} chars)"

            wp_result = await post_to_wordpress(post_title, blog_html, client, featured_media_id)
            blog_url = f"{WP_SITE_URL}/?p={wp_result['id']}"
            yield f"✅ Step 8: Blog published — {blog_url}"

            next_run_advice = await generate_next_run_advice(metrics, training_data)
            yield f"✅ Step 9a: Next run advice generated — {next_run_advice}"
            description = build_strava_description(metrics, training_data, blog_url, next_run_advice, weather)
            await update_strava_description(activity_id, access_token, description, client)
            yield "✅ Step 9b: Strava description updated"

            yield f"🎉 Done! Blog post published at {blog_url}"

    except Exception as e:
        yield f"❌ Pipeline error: {e}"
