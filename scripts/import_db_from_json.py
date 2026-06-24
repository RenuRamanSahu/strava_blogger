#!/usr/bin/env python3
"""Import activities from JSON backup into SQLite database."""

import sys
import os
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH
from db import init_db, save_activity


def import_db_from_json(input_path: str):
    """Import activities from JSON backup file."""
    if not os.path.exists(input_path):
        print(f"❌ Backup file not found: {input_path}")
        return False
    
    try:
        # Initialize DB
        init_db()
        
        # Load JSON
        with open(input_path, 'r') as f:
            backup_data = json.load(f)
        
        activities = backup_data.get("activities", [])
        print(f"📝 Found {len(activities)} activities in backup")
        
        # Import each activity
        imported = 0
        failed = 0
        
        for activity in activities:
            try:
                # Extract fields from backup
                activity_id = activity.get("activity_id")
                
                # Reconstruct JSON objects
                metrics = json.loads(activity.get("metrics_json", "{}"))
                training_data = json.loads(activity.get("training_json", "{}"))
                weather = json.loads(activity.get("weather_json", "{}"))
                
                # Parse elevation profile if present
                elevation_profile = None
                if "elevation_json" in activity:
                    elevation_profile = json.loads(activity.get("elevation_json", "{}"))
                
                # Save activity
                save_activity(
                    activity_id=activity_id,
                    metrics=metrics,
                    training_data=training_data,
                    weather=weather,
                    elevation_profile=elevation_profile,
                    blog_url=activity.get("blog_url"),
                    post_title=activity.get("post_title"),
                    meta_description=activity.get("meta_description")
                )
                imported += 1
                if imported % 5 == 0:
                    print(f"  ✅ [{imported}] Imported activity {activity_id}")
            
            except Exception as e:
                failed += 1
                print(f"  ❌ Failed to import activity {activity.get('activity_id')}: {e}")
        
        print(f"\n✅ Import complete: {imported} activities imported, {failed} failed")
        return True
    
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Import activities from JSON backup")
    parser.add_argument("input", help="Input JSON backup file path")
    args = parser.parse_args()
    
    success = import_db_from_json(args.input)
    sys.exit(0 if success else 1)
