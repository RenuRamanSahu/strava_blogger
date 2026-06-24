#!/usr/bin/env python3
"""Lightweight JSON cache for recent Strava activities (90-day window).

Replaces database with a simple, ephemeral-storage-friendly JSON file.
Auto-refreshes from Strava API when stale (>6 hours old).

Provides:
- get_cached_activities() → list of recent activities for ACWR calculation
- cache_new_activity(activity_data) → add new activity to cache
- refresh_cache_if_stale() → fetch from Strava if cache is old
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "activities_cache.json")
CACHE_MAX_AGE_HOURS = 6
CACHE_WINDOW_DAYS = 90


def _ensure_cache_dir():
    """Create data directory if it doesn't exist."""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)


def get_cached_activities() -> List[Dict[str, Any]]:
    """Return list of cached activities for ACWR calculation."""
    _ensure_cache_dir()
    
    if not os.path.exists(CACHE_FILE):
        return []
    
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        return cache.get("activities", [])
    except Exception as e:
        print(f"⚠️  Could not read cache: {e}")
        return []


def cache_new_activity(activity_data: Dict[str, Any]) -> bool:
    """Add a new activity to the cache.
    
    Args:
        activity_data: Activity dict with at least: id, name, start_date, distance, moving_time
    
    Returns:
        True if cached successfully
    """
    _ensure_cache_dir()
    
    try:
        cache = {"activities": []}
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
        
        # Ensure it's a dict
        if not isinstance(cache, dict):
            cache = {"activities": []}
        if "activities" not in cache:
            cache["activities"] = []
        
        # Remove if already exists (avoid duplicates)
        activity_id = activity_data.get("id")
        cache["activities"] = [a for a in cache["activities"] if a.get("id") != activity_id]
        
        # Add new activity at front
        cache["activities"].insert(0, activity_data)
        
        # Keep only last 90 days worth
        cache["activities"] = cache["activities"][:365]  # ~90 days of 5/week activity
        
        cache["last_updated"] = datetime.utcnow().isoformat()
        cache["cache_window_days"] = CACHE_WINDOW_DAYS
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2, default=str)
        
        print(f"💾 Cached activity {activity_id} | Total: {len(cache['activities'])} activities")
        return True
    
    except Exception as e:
        print(f"⚠️  Failed to cache activity: {e}")
        return False


def is_cache_stale() -> bool:
    """Check if cache needs refresh from Strava API."""
    if not os.path.exists(CACHE_FILE):
        return True
    
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        last_updated = cache.get("last_updated")
        if not last_updated:
            return True
        
        last_update_time = datetime.fromisoformat(last_updated)
        age = datetime.utcnow() - last_update_time
        
        return age > timedelta(hours=CACHE_MAX_AGE_HOURS)
    except Exception:
        return True


def get_cache_age_str() -> str:
    """Return human-readable cache age."""
    if not os.path.exists(CACHE_FILE):
        return "no cache"
    
    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)
        
        last_updated = cache.get("last_updated")
        if not last_updated:
            return "unknown age"
        
        last_update_time = datetime.fromisoformat(last_updated)
        age = datetime.utcnow() - last_update_time
        
        if age.total_seconds() < 60:
            return "just now"
        elif age.total_seconds() < 3600:
            minutes = int(age.total_seconds() / 60)
            return f"{minutes}m ago"
        elif age.total_seconds() < 86400:
            hours = int(age.total_seconds() / 3600)
            return f"{hours}h ago"
        else:
            days = int(age.total_seconds() / 86400)
            return f"{days}d ago"
    except Exception:
        return "error reading cache"


def clear_cache():
    """Clear the cache file."""
    if os.path.exists(CACHE_FILE):
        os.remove(CACHE_FILE)
        print(f"✅ Cache cleared: {CACHE_FILE}")


async def refresh_cache_if_stale() -> bool:
    """Refresh cache from Strava if stale (>6 hours old).
    
    Returns:
        True if cache was refreshed, False if it's still fresh
    """
    if not is_cache_stale():
        return False
    
    try:
        import httpx
        from strava import get_strava_access_token, get_recent_activities
        
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; strava-blogger/1.0; +https://renuramansahu.com)",
                "Accept": "application/json, */*",
            },
            timeout=60,
        ) as client:
            access_token = await get_strava_access_token(client)
            recent_activities = await get_recent_activities(access_token, client)
            
            # Convert to cache format
            cache_entries = []
            for activity in recent_activities:
                entry = {
                    "id": activity.get("id"),
                    "name": activity.get("name"),
                    "start_date": activity.get("start_date_local") or activity.get("start_date"),
                    "distance_km": (activity.get("distance", 0) / 1000) if activity.get("distance") else 0,
                    "moving_time": activity.get("moving_time"),
                    "elevation_m": activity.get("total_elevation_gain"),
                    "average_heartrate": activity.get("average_heartrate"),
                    "max_heartrate": activity.get("max_heartrate"),
                }
                cache_entries.append(entry)
            
            _ensure_cache_dir()
            cache = {
                "last_updated": datetime.utcnow().isoformat(),
                "cache_window_days": CACHE_WINDOW_DAYS,
                "activities": cache_entries,
            }
            
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache, f, indent=2, default=str)
            
            print(f"🔄 Cache refreshed: {len(cache_entries)} activities from Strava")
            return True
    
    except Exception as e:
        print(f"⚠️  Cache refresh failed: {e}")
        return False


if __name__ == "__main__":
    # Quick test
    print(f"Cache file: {CACHE_FILE}")
    print(f"Cache age: {get_cache_age_str()}")
    print(f"Cached activities: {len(get_cached_activities())}")
    print(f"Stale: {is_cache_stale()}")
