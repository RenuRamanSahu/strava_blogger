import base64
import io
import httpx
from PIL import Image
from config import WP_USERNAME, WP_APP_PASSWORD, WP_SITE_URL

MAX_MEDIA_BYTES = 1_000_000  # 1 MB hard cap for WP media uploads


def _wp_auth_headers() -> dict:
    """Returns WordPress Basic Auth headers"""
    credential_string = f"{WP_USERNAME}:{WP_APP_PASSWORD}"
    base64_credentials = base64.b64encode(credential_string.encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {base64_credentials}"}


def _shrink_under_1mb(image_bytes: bytes, filename: str, content_type: str) -> tuple[bytes, str, str]:
    """If image is over MAX_MEDIA_BYTES, re-encode as JPEG with decreasing quality until it fits.
    Returns (bytes, filename, content_type). Animated GIFs are returned unchanged (re-encoding would break them).
    """
    if len(image_bytes) <= MAX_MEDIA_BYTES:
        return image_bytes, filename, content_type
    if content_type == "image/gif":
        print(f"\u26a0\ufe0f Image '{filename}' is {len(image_bytes)} bytes (>1MB) but is GIF — not re-encoding")
        return image_bytes, filename, content_type

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        print(f"\u26a0\ufe0f Could not open image '{filename}' for resize ({e}) — sending original")
        return image_bytes, filename, content_type

    # JPEG doesn't support alpha; flatten RGBA onto white
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    original_size = len(image_bytes)
    # First try quality steps; if still too big, downscale and try again
    for max_dim in (img.size[0], 1600, 1200, 900):
        if max_dim < img.size[0]:
            ratio = max_dim / img.size[0]
            new_size = (max_dim, int(img.size[1] * ratio))
            img_resized = img.resize(new_size, Image.LANCZOS)
        else:
            img_resized = img
        for quality in (85, 75, 65, 55, 45):
            buf = io.BytesIO()
            img_resized.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
            data = buf.getvalue()
            if len(data) <= MAX_MEDIA_BYTES:
                new_name = (filename.rsplit(".", 1)[0] if "." in filename else filename) + ".jpg"
                print(f"\u2705 Resized '{filename}' from {original_size} → {len(data)} bytes (≤{img_resized.size}, q={quality})")
                return data, new_name, "image/jpeg"

    # Fallback: return smallest version we managed even if still over (>1MB but better than nothing)
    print(f"\u26a0\ufe0f Could not shrink '{filename}' below 1MB — sending best-effort {len(data)} bytes")
    new_name = (filename.rsplit(".", 1)[0] if "." in filename else filename) + ".jpg"
    return data, new_name, "image/jpeg"


async def _get_or_create_category(name: str, client: httpx.AsyncClient) -> int:
    """Looks up a WordPress category by name, creates it if it doesn't exist, returns the ID"""
    # Search for existing category (GET has no body — do NOT send Content-Type, some WAFs return 415)
    search_url = f"{WP_SITE_URL}/wp-json/wp/v2/categories"
    print(f"\U0001f4e4 GET {search_url} — searching for category '{name}'")
    resp = await client.get(search_url, headers=_wp_auth_headers(), params={"search": name, "per_page": 100})
    print(f"\U0001f4e5 Response {resp.status_code} from {search_url}")
    resp_ct = resp.headers.get("content-type", "")
    if resp.status_code >= 400 or "json" not in resp_ct.lower():
        print(f"\u26a0\ufe0f WP categories search non-JSON or error (content-type='{resp_ct}'): {resp.text[:800]}")
    resp.raise_for_status()
    if "json" not in resp_ct.lower():
        raise RuntimeError(f"WP categories search returned non-JSON ({resp.status_code} {resp_ct}) — likely WAF interstitial")
    try:
        cats = resp.json()
    except Exception as e:
        raise RuntimeError(f"WP categories search JSON parse failed: {e}; body: {resp.text[:500]}")
    if not isinstance(cats, list):
        raise RuntimeError(f"WP categories search returned non-list payload (type={type(cats).__name__}): {str(cats)[:500]}")
    for cat in cats:
        if isinstance(cat, dict) and cat.get("name", "").lower() == name.lower():
            print(f"\u2705 Category '{name}' found — ID: {cat['id']}")
            return cat["id"]

    # Create if not found (POST needs Content-Type)
    create_headers = {**_wp_auth_headers(), "Content-Type": "application/json"}
    print(f"\U0001f4e4 POST {search_url} — creating category '{name}'")
    resp = await client.post(search_url, headers=create_headers, json={"name": name})
    print(f"\U0001f4e5 Response {resp.status_code} from {search_url}")
    resp_ct = resp.headers.get("content-type", "")
    if resp.status_code >= 400 or "json" not in resp_ct.lower():
        print(f"\u26a0\ufe0f WP category create non-JSON or error (content-type='{resp_ct}'): {resp.text[:800]}")
    resp.raise_for_status()
    if "json" not in resp_ct.lower():
        raise RuntimeError(f"WP category create returned non-JSON ({resp.status_code} {resp_ct}) — likely WAF interstitial")
    try:
        created = resp.json()
    except Exception as e:
        raise RuntimeError(f"WP category create JSON parse failed: {e}; body: {resp.text[:500]}")
    if not isinstance(created, dict) or "id" not in created:
        raise RuntimeError(f"WP category create returned unexpected payload (type={type(created).__name__}): {str(created)[:500]}")
    cat_id = created["id"]
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

    # Enforce 1MB cap (re-encodes oversized images as JPEG with adaptive quality/dimensions)
    image_bytes, filename, content_type = _shrink_under_1mb(image_bytes, filename, content_type)

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


async def post_to_wordpress(title: str, html_content: str, client: httpx.AsyncClient, featured_media_id: int = None, excerpt: str = ""):
    """Pushes the generated text payload directly to your WordPress backend.

    `excerpt` is used as the post excerpt so Yoast/Rank Math/Google use it as the
    meta description instead of auto-truncating the first paragraph.
    """
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

    if excerpt:
        post_data["excerpt"] = excerpt

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
