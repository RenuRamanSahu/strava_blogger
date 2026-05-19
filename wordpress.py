import base64
import httpx
from config import WP_USERNAME, WP_APP_PASSWORD, WP_SITE_URL


async def post_to_wordpress(title: str, html_content: str, client: httpx.AsyncClient):
    """Pushes the generated text payload directly to your WordPress backend as a Draft"""
    endpoint = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

    # Bundle credentials to Base64 block required for WordPress Basic Auth header
    credential_string = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    base64_credentials = base64.b64encode(credential_string.encode("utf-8")).decode("utf-8")

    headers = {
        "Authorization": f"Basic {base64_credentials}",
        "Content-Type": "application/json"
    }

    post_data = {
        "title": title,
        "content": html_content,
        "status": "publish"  # Publishes the post to my blog
    }

    print(f"Uploading draft post to {WP_SITE_URL}...")
    response = await client.post(endpoint, headers=headers, json=post_data)
    response.raise_for_status()

    result = response.json()
    print(f"✅ Success! Blog Draft created: {result.get('link')}")
    return result
