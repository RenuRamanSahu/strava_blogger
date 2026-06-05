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
    # Search for existing category (GET has no body — do NOT send Content-Type, some WAFs return 415)
    search_url = f"{WP_SITE_URL}/wp-json/wp/v2/categories"
    print(f"\U0001f4e4 GET {search_url} — searching for category '{name}'")
    resp = await client.get(search_url, headers=_wp_auth_headers(), params={"search": name, "per_page": 100})
    print(f"\U0001f4e5 Response {resp.status_code} from {search_url}")
    if resp.status_code >= 400:
        print(f"\u26a0\ufe0f WP categories search error body: {resp.text[:500]}")
    resp.raise_for_status()
    for cat in resp.json():
        if cat["name"].lower() == name.lower():
            print(f"\u2705 Category '{name}' found — ID: {cat['id']}")
            return cat["id"]

    # Create if not found (POST needs Content-Type)
    create_headers = {**_wp_auth_headers(), "Content-Type": "application/json"}
    print(f"\U0001f4e4 POST {search_url} — creating category '{name}'")
    resp = await client.post(search_url, headers=create_headers, json={"name": name})
    print(f"\U0001f4e5 Response {resp.status_code} from {search_url}")
    if resp.status_code >= 400:
        print(f"\u26a0\ufe0f WP category create error body: {resp.text[:500]}")
    resp.raise_for_status()
    cat_id = resp.json()["id"]
    print(f"\u2705 Category '{name}' created — ID: {cat_id}")
    return cat_id


async def upload_media_to_wordpress(image_bytes: bytes, filename: str, client: httpx.AsyncClient, content_type: str = "image/png") -> int:
    """Uploads an image to the WordPress media library and returns the media ID.

    Uses multipart/form-data (what wp-admin itself sends) to maximize compatibility
    with hosts that block raw-body uploads via WAF/security plugins. Normalizes
    content-type and filename so WP doesn't reject with 415 on extension/MIME mismatch.
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

    # NOTE: do NOT set Content-Type manually — httpx generates the multipart boundary header
    headers = {
        **_wp_auth_headers(),
        "Accept": "application/json",
        "User-Agent": "strava-blogger/1.0 (+https://renuramansahu.com)",
    }
    files = {"file": (filename, image_bytes, content_type)}

    print(f"\U0001f4e4 POST {endpoint} — uploading media '{filename}' ({len(image_bytes)} bytes, {content_type}) as multipart")
    response = await client.post(endpoint, headers=headers, files=files)
    print(f"\U0001f4e5 Response {response.status_code} from {endpoint}")
    resp_ct = response.headers.get("content-type", "")
    if response.status_code >= 400 or "json" not in resp_ct.lower():
        body_preview = response.text[:800] if response.text else ""
        print(f"\u26a0\ufe0f WP media upload non-JSON response (content-type='{resp_ct}'): {body_preview}")
    response.raise_for_status()
    if "json" not in resp_ct.lower():
        raise RuntimeError(f"WP media upload returned non-JSON ({response.status_code} {resp_ct}) — likely WAF/security plugin interstitial")

    try:
        payload = response.json()
    except Exception as e:
        raise RuntimeError(f"WP media upload JSON parse failed: {e}; body: {response.text[:500]}")
    if not isinstance(payload, dict) or "id" not in payload:
        raise RuntimeError(f"WP media upload returned unexpected payload (type={type(payload).__name__}): {str(payload)[:500]}")
    media_id = payload["id"]
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
    resp_ct = response.headers.get("content-type", "")
    if response.status_code >= 400 or "json" not in resp_ct.lower():
        body_preview = response.text[:800] if response.text else ""
        print(f"\u26a0\ufe0f WP post create non-JSON or error response (content-type='{resp_ct}'): {body_preview}")
    response.raise_for_status()
    if "json" not in resp_ct.lower():
        raise RuntimeError(f"WP post create returned non-JSON ({response.status_code} {resp_ct}) — likely WAF interstitial")

    try:
        result = response.json()
    except Exception as e:
        raise RuntimeError(f"WP post create JSON parse failed: {e}; body: {response.text[:500]}")
    if not isinstance(result, dict) or "id" not in result:
        raise RuntimeError(f"WP post create returned unexpected payload (type={type(result).__name__}): {str(result)[:500]}")
    print(f"\u2705 Blog published: {result.get('link')}")
    return result
