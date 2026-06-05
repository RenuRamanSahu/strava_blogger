"""Standalone diagnostic for WordPress /media uploads.

Runs three upload variants against the live site to isolate which one (if any) WP/your host accepts:
  1. multipart/form-data           (what wp-admin uses; current production code)
  2. raw body + Content-Disposition (older python-wordpress-xmlrpc style)
  3. multipart with no User-Agent  (rules out UA-based WAF blocks)

Usage:
    python test_wp_upload.py

Prints the full response body for every attempt so you can see exactly what's blocking.
"""
import asyncio
import base64
import httpx
from config import WP_USERNAME, WP_APP_PASSWORD, WP_SITE_URL


# Smallest valid PNG (1x1 transparent pixel), ~70 bytes — small enough to rule out size issues.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _auth_header() -> dict:
    creds = base64.b64encode(f"{WP_USERNAME}:{WP_APP_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


async def _show_response(label: str, resp: httpx.Response):
    print(f"\n--- {label} ---")
    print(f"Status: {resp.status_code}")
    print(f"Response headers:")
    for k, v in resp.headers.items():
        print(f"  {k}: {v}")
    print(f"Body (first 1500 chars):")
    print(resp.text[:1500] if resp.text else "<empty>")


async def attempt_multipart(client: httpx.AsyncClient):
    url = f"{WP_SITE_URL}/wp-json/wp/v2/media"
    headers = {
        **_auth_header(),
        "Accept": "application/json",
        "User-Agent": "strava-blogger/1.0 (+https://renuramansahu.com)",
    }
    files = {"file": ("diagnostic.png", TINY_PNG, "image/png")}
    resp = await client.post(url, headers=headers, files=files)
    await _show_response("ATTEMPT 1: multipart/form-data (current prod)", resp)


async def attempt_raw_body(client: httpx.AsyncClient):
    url = f"{WP_SITE_URL}/wp-json/wp/v2/media"
    headers = {
        **_auth_header(),
        "Content-Type": "image/png",
        "Content-Disposition": 'attachment; filename="diagnostic.png"',
        "Accept": "application/json",
        "User-Agent": "strava-blogger/1.0 (+https://renuramansahu.com)",
    }
    resp = await client.post(url, headers=headers, content=TINY_PNG)
    await _show_response("ATTEMPT 2: raw body + Content-Disposition", resp)


async def attempt_multipart_default_ua(client: httpx.AsyncClient):
    url = f"{WP_SITE_URL}/wp-json/wp/v2/media"
    headers = {**_auth_header(), "Accept": "application/json"}
    files = {"file": ("diagnostic.png", TINY_PNG, "image/png")}
    resp = await client.post(url, headers=headers, files=files)
    await _show_response("ATTEMPT 3: multipart, default httpx User-Agent", resp)


async def precheck_rest_root(client: httpx.AsyncClient):
    """Confirm REST API is reachable at all (no auth needed)."""
    url = f"{WP_SITE_URL}/wp-json/"
    resp = await client.get(url)
    print(f"\n--- PRECHECK: GET /wp-json/ ---")
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"WP site: {data.get('name')}  ({data.get('description')})")
        print(f"Namespaces: {data.get('namespaces', [])[:5]}...")
    else:
        print(f"Body: {resp.text[:500]}")


async def precheck_user(client: httpx.AsyncClient):
    """Confirm app-password auth works and user has upload capability."""
    url = f"{WP_SITE_URL}/wp-json/wp/v2/users/me"
    resp = await client.get(url, headers={**_auth_header(), "Accept": "application/json"})
    print(f"\n--- PRECHECK: GET /users/me ---")
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        u = resp.json()
        print(f"Auth OK: user '{u.get('name')}' (id {u.get('id')}), roles: {u.get('roles')}")
        caps = u.get("capabilities", {}) or {}
        print(f"upload_files capability: {caps.get('upload_files', 'unknown')}")
    else:
        print(f"Body: {resp.text[:500]}")


async def main():
    print(f"Target site: {WP_SITE_URL}")
    print(f"User: {WP_USERNAME}")
    async with httpx.AsyncClient(timeout=30) as client:
        await precheck_rest_root(client)
        await precheck_user(client)
        for fn in (attempt_multipart, attempt_raw_body, attempt_multipart_default_ua):
            try:
                await fn(client)
            except Exception as e:
                print(f"\n--- {fn.__name__} raised: {type(e).__name__}: {e} ---")


if __name__ == "__main__":
    asyncio.run(main())
