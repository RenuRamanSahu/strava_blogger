#!/usr/bin/env python3
"""Export SQLite database to JSON for backup/version control."""

import sys
import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH


def export_db_to_json(output_path: str = None):
    """Export activities from database to JSON file for backup."""
    if not output_path:
        output_path = os.path.join(os.path.dirname(__file__), "..", "data", "strava_activities_backup.json")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Fetch all activities
        cur.execute("SELECT * FROM activities ORDER BY start_date DESC")
        rows = cur.fetchall()
        activities = [dict(row) for row in rows]
        conn.close()
        
        # Write to JSON
        backup_data = {
            "export_time": datetime.utcnow().isoformat(),
            "activity_count": len(activities),
            "activities": activities
        }
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(backup_data, f, indent=2, default=str)
        
        print(f"✅ Exported {len(activities)} activities to {output_path}")
        return True
    
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export database to JSON backup")
    parser.add_argument("--output", help="Output JSON file path (default: data/strava_activities_backup.json)")
    args = parser.parse_args()
    
    success = export_db_to_json(args.output)
    sys.exit(0 if success else 1)
