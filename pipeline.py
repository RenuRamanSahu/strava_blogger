import httpx
from strava import (
    get_strava_access_token, get_activity_details, get_recent_activities,
    compute_acwr_and_health, build_strava_description, update_strava_description,
)
from gemini_client import generate_blog_with_gemini, generate_blog_title
from wordpress import post_to_wordpress


async def process_pipeline_background(activity_id: int):
    """Master background execution link connecting data fetching to publishing"""
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch Working Strava Authorization Token
            access_token = await get_strava_access_token(client)

            # 2. Extract Specific Workout Metrics
            metrics = await get_activity_details(activity_id, access_token, client)

            # 3. Fetch recent activities and compute ACWR + run health
            recent_activities = await get_recent_activities(access_token, client)
            training_data = compute_acwr_and_health(recent_activities)

            # 4. Build Strava activity URL
            strava_url = f"https://www.strava.com/activities/{activity_id}"

            # 5. Generate AI blog title and content (includes Strava link in blog)
            post_title = generate_blog_title(metrics)
            blog_html = generate_blog_with_gemini(metrics, training_data, strava_url)

            # 6. Upload Content Directly onto renuramansahu.com
            wp_result = await post_to_wordpress(post_title, blog_html, client)
            blog_url = wp_result.get("link", "https://renuramansahu.com")

            # 7. Update Strava activity description with summary + health metrics + blog link
            description = build_strava_description(metrics, training_data, blog_url)
            await update_strava_description(activity_id, access_token, description, client)

    except Exception as e:
        print(f"❌ Error executing content pipeline: {e}")
