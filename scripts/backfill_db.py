#!/usr/bin/env python3
"""Standalone backfill script to fetch historical Strava activities and populate the local SQLite database.

This script checks if the DB is empty on startup. If empty, it automatically backfills historical data.
For subsequent deployments, the DB will already be populated, so the script is safe to re-run.

Usage:
    python scripts/backfill_db.py                 # auto-detect if backfill needed (default)
    python scripts/backfill_db.py --days 90       # force backfill last 90 days
    python scripts/backfill_db.py --days 365      # force backfill last year
    python scripts/backfill_db.py --after-id 1234567  # fetch after specific activity

Environment:
    STRAVA_DB_PATH: override default DB path
    STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN: Strava credentials
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timedelta

# Add parent dir to path so we can import local modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from strava import get_strava_access_token, get_recent_activities, compute_acwr_and_health, get_activity_details, get_activity_streams
from db import init_db, save_activity, is_db_empty, db_exists


async def backfill_activities(days: int = 90, after_id: int = None, force: bool = False):
    """Fetch and backfill activities from the last N days (or after a given activity ID).
    
    Args:
        days: number of days to look back (ignored if after_id is set)
        after_id: if set, fetch all activities after this activity_id
        force: if False, skip backfill if DB already has data
    
    Returns:
        True if backfill completed, False if skipped
    """
    print("=" * 70)
    print("STRAVA ACTIVITY BACKFILL")
    print("=" * 70)
    
    # 1. Initialize DB
    print("\n[1/5] Initializing local database...")
    try:
        init_db()
        print("✅ Database initialized (or already exists)")
    except Exception as e:
        print(f"❌ Failed to init DB: {e}")
        return False
    
    # 2. Check if backfill is needed
    if not force:
        print("\n[2/5] Checking if backfill is needed...")
        if not is_db_empty():
            print("✅ Database already has activities. Skipping backfill.")
            print("    (Use --force to override)")
            return False
        print("📝 Database is empty. Proceeding with backfill.")
    else:
        print("\n[2/5] Force mode enabled. Will backfill regardless of existing data.")
    
    # 3. Fetch Strava token
    print("\n[3/5] Acquiring Strava access token...")
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            access_token = await get_strava_access_token(client)
            print(f"✅ Strava token acquired")
    except Exception as e:
        print(f"❌ Failed to get Strava token: {e}")
        return False
    
    # 4. Fetch recent activities
    print(f"\n[4/5] Fetching recent activities from Strava...")
    if after_id:
        print(f"    (after activity ID {after_id})")
    else:
        print(f"    (last {days} days)")
    
    try:
        async with httpx.AsyncClient(
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; strava-blogger/1.0; +https://renuramansahu.com)",
                "Accept": "application/json, */*",
            },
            timeout=60,
        ) as client:
            recent_activities = await get_recent_activities(access_token, client, days=days)
            print(f"✅ Fetched {len(recent_activities)} activities from Strava")
            
            # 5. Process and save each activity
            print(f"\n[5/5] Processing and saving {len(recent_activities)} activities to DB...")
            saved_count = 0
            failed_count = 0
            skipped_count = 0
            
            for idx, activity_summary in enumerate(recent_activities, 1):
                activity_id = activity_summary.get("id")
                name = activity_summary.get("name")
                
                # Skip if after_id is set and this activity is before it
                if after_id and activity_id <= after_id:
                    skipped_count += 1
                    continue
                
                try:
                    # Fetch full activity details
                    metrics = await get_activity_details(activity_id, access_token, client)
                    
                    # Fetch elevation profile for HR-less metric computation
                    elevation_profile = None
                    try:
                        elevation_profile = await get_activity_streams(activity_id, access_token, client) or {}
                    except Exception:
                        pass  # elevation profile is optional
                    
                    # Compute training load and ACWR using all recent activities
                    training_data = compute_acwr_and_health(recent_activities)
                    
                    # Save to DB (weather optional for backfill, not fetching it to save API calls)
                    save_activity(
                        activity_id=activity_id,
                        metrics=metrics,
                        training_data=training_data,
                        weather={},
                        elevation_profile=elevation_profile,
                        blog_url=None,
                        post_title=None,
                        meta_description=None,
                    )
                    
                    saved_count += 1
                    status = "✅" if saved_count % 5 == 0 else "  "
                    print(f"  {status} [{idx}/{len(recent_activities)}] {activity_id} | {name[:40]}")
                    
                except Exception as e:
                    failed_count += 1
                    print(f"  ❌ [{idx}/{len(recent_activities)}] {activity_id} | {name[:40]} — {e}")
            
            # Summary
            print("\n" + "=" * 70)
            print("BACKFILL COMPLETE")
            print("=" * 70)
            print(f"✅ Saved:    {saved_count}")
            print(f"❌ Failed:   {failed_count}")
            if skipped_count:
                print(f"⏭️  Skipped:  {skipped_count}")
            print(f"📊 Total:    {saved_count + failed_count + skipped_count}")
            print("\n✨ Your next run will have historical context for ACWR and insights!")
            return True
    
    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Backfill the local database with historical Strava activities.",
        epilog="On first deployment, this auto-detects and fills an empty DB. Safe to re-run."
    )
    parser.add_argument("--days", type=int, default=90, help="Number of days to look back (default: 90)")
    parser.add_argument("--after-id", type=int, default=None, help="Fetch activities after this activity_id (overrides --days)")
    parser.add_argument("--force", action="store_true", help="Force backfill even if DB already has data")
    args = parser.parse_args()
    
    success = asyncio.run(backfill_activities(days=args.days, after_id=args.after_id, force=args.force))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
