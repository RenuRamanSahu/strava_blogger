import base64
import httpx
from config import WP_USERNAME, WP_APP_PASSWORD, WP_SITE_URL


def _wp_auth_headers() -> dict:
    """Returns WordPress Basic Auth headers"""
    credential_string = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    base64_credentials = base64.b64encode(credential_string.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {base64_credentials}"}


async def _get_or_create_category(name: str, client: httpx.AsyncClient) -> int:
    """Looks up a WordPress category by name, creates it if it doesn't exist, returns the ID"""
    headers = {**_wp_auth_headers(), "Content-Type": "application/json"}

    # Search for existing category
    search_url = f"{WP_SITE_URL}/wp-json/wp/v2/categories"
    print(f"\U0001f4e4 GET {search_url} — searching for category '{name}'")
    resp = await client.get(search_url, headers=headers, params={"search": name, "per_page": 100})
    print(f"\U0001f4e5 Response {resp.status_code} from {search_url}")
    resp.raise_for_status()
    for cat in resp.json():
        if cat["name"].lower() == name.lower():
            print(f"\u2705 Category '{name}' found — ID: {cat['id']}")
            return cat["id"]

    # Create if not found
    print(f"\U0001f4e4 POST {search_url} — creating category '{name}'")
    resp = await client.post(search_url, headers=headers, json={"name": name})
    print(f"\U0001f4e5 Response {resp.status_code} from {search_url}")
    resp.raise_for_status()
    cat_id = resp.json()["id"]
    print(f"\u2705 Category '{name}' created — ID: {cat_id}")
    return cat_id


async def upload_media_to_wordpress(image_bytes: bytes, filename: str, client: httpx.AsyncClient, content_type: str = "image/png") -> int:
    """Uploads an image to the WordPress media library and returns the media ID.

    Normalizes content-type and filename so WP doesn't reject with 415 due to
    extension/MIME mismatch or unsupported type.
    """
    endpoint = f"{WP_SITE_URL}/wp-json/wp/v2/media"

    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    ext_to_mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".jpe": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
    }
    mime_to_ext = {
        "image/jpeg": ".jpg", "image/png": ".png",
        "image/gif": ".gif", "image/webp": ".webp",
    }
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    inferred = ext_to_mime.get(ext)

    if content_type not in allowed:
        if inferred:
            print(f"\u26a0\ufe0f Normalizing content-type '{content_type}' \u2192 '{inferred}' (from ext '{ext}')")
            content_type = inferred
        else:
            raise ValueError(f"Unsupported media type '{content_type}' for filename '{filename}'")
    elif inferred and inferred != content_type:
        new_ext = mime_to_ext[content_type]
        new_filename = (filename.rsplit(".", 1)[0] if "." in filename else filename) + new_ext
        print(f"\u26a0\ufe0f Renaming '{filename}' \u2192 '{new_filename}' to match content-type '{content_type}'")
        filename = new_filename

    headers = {
        **_wp_auth_headers(),
        "Content-Type": content_type,
        "Content-Disposition": f'attachment; filename="{filename}"',
    }

    print(f"\U0001f4e4 POST {endpoint} — uploading media '{filename}' ({len(image_bytes)} bytes, {content_type})")
    response = await client.post(endpoint, headers=headers, content=image_bytes)
    print(f"\U0001f4e5 Response {response.status_code} from {endpoint}")
    if response.status_code >= 400:
        body_preview = response.text[:500] if response.text else ""
        print(f"\u26a0\ufe0f WP media upload error body: {body_preview}")
    response.raise_for_status()

    media_id = response.json().get("id")
    print(f"\u2705 Media uploaded — ID: {media_id}")
    return media_id


async def post_to_wordpress(title: str, html_content: str, client: httpx.AsyncClient, featured_media_id: int = None):
    """Pushes the generated text payload directly to your WordPress backend"""
    endpoint = f"{WP_SITE_URL}/wp-json/wp/v2/posts"

    headers = {
        **_wp_auth_headers(),
        "Content-Type": "application/json",
    }

    # Resolve "Athletics" category
    category_id = await _get_or_create_category("Athletics", client)

    post_data = {
        "title": title,
        "content": html_content,
        "status": "publish",
        "categories": [category_id],
    }

    if featured_media_id:
        post_data["featured_media"] = featured_media_id

    print(f"\U0001f4e4 POST {endpoint} — publishing blog post '{title}'")
    response = await client.post(endpoint, headers=headers, json=post_data)
    print(f"\U0001f4e5 Response {response.status_code} from {endpoint}")
    response.raise_for_status()

    result = response.json()
    print(f"\u2705 Blog published: {result.get('link')}")
    return result
