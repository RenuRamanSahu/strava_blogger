import httpx
from strava import get_strava_access_token, get_activity_details
from gemini_client import generate_blog_with_gemini
from wordpress import post_to_wordpress


async def process_pipeline_background(activity_id: int):
    """Master background execution link connecting data fetching to publishing"""
    try:
        async with httpx.AsyncClient() as client:
            # 1. Fetch Working Strava Authorization Token
            access_token = await get_strava_access_token(client)

            # 2. Extract Specific Workout Metrics
            metrics = await get_activity_details(activity_id, access_token, client)

            # 3. Request Gemini Content Compilation
            blog_html = generate_blog_with_gemini(metrics)

            # 4. Upload Content Directly onto renuramansahu.com
            post_title = f"Recap: {metrics['name']}"
            await post_to_wordpress(post_title, blog_html, client)

    except Exception as e:
        print(f"❌ Error executing content pipeline: {e}")
