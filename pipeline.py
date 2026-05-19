import httpx
from strava import (
    get_strava_access_token, get_activity_details, get_recent_activities,
    compute_acwr_and_health, build_strava_description, update_strava_description,
)
from gemini_client import generate_blog_with_gemini, generate_blog_title, generate_next_run_advice
from wordpress import post_to_wordpress


async def process_pipeline_background(activity_id: int):
    """Master background execution link connecting data fetching to publishing"""
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch Working Strava Authorization Token
            access_token = await get_strava_access_token(client)
            print(f"\u2705 Step 1: Strava token acquired")

            # 2. Extract Specific Workout Metrics
            metrics = await get_activity_details(activity_id, access_token, client)
            print(f"\u2705 Step 2: Activity metrics fetched — {metrics.get('name')}")

            # 3. Fetch recent activities and compute ACWR + run health
            recent_activities = await get_recent_activities(access_token, client)
            training_data = compute_acwr_and_health(recent_activities)
            print(f"\u2705 Step 3: ACWR computed — {training_data.get('acwr')} ({training_data.get('health_status')})")

            # 4. Build Strava activity URL
            strava_url = f"https://www.strava.com/activities/{activity_id}"

            # 5. Generate AI blog title and content (includes Strava link in blog)
            post_title = generate_blog_title(metrics)
            print(f"\u2705 Step 5a: AI title generated — {post_title}")
            blog_html = generate_blog_with_gemini(metrics, training_data, strava_url)
            print(f"\u2705 Step 5b: Blog content generated ({len(blog_html)} chars)")

            # 6. Upload Content Directly onto renuramansahu.com
            wp_result = await post_to_wordpress(post_title, blog_html, client)
            blog_url = wp_result.get("link", "https://renuramansahu.com")
            print(f"\u2705 Step 6: Blog published — {blog_url}")

            # 7. Update Strava activity description with summary + health metrics + blog link
            next_run_advice = generate_next_run_advice(metrics, training_data)
            print(f"\u2705 Step 7a: Next run advice generated — {next_run_advice}")
            description = build_strava_description(metrics, training_data, blog_url, next_run_advice)
            await update_strava_description(activity_id, access_token, description, client)
            print(f"\u2705 Step 7: Strava description updated")

    except Exception as e:
        import traceback
        print(f"❌ Error executing content pipeline: {e}")
        traceback.print_exc()
