"""Simple SQLite storage for Strava activity metrics and derived training data.

Provides:
- init_db(db_path=None)
- save_activity(activity_id, metrics, training_data, weather, blog_url, post_title, meta_description)
- get_acwr_trend(limit=28)
- get_recent_activities(limit=20)
- trigger_backfill_if_empty(): async function to auto-backfill on first deployment

This module uses the stdlib sqlite3 module and stores raw JSON blobs for later analysis.
"""
import sqlite3
import json
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH

_DB_PATH = None


def _get_target_db_path() -> str:
    return _DB_PATH or DB_PATH


def _get_fallback_db_path() -> str:
    # Fallback DB checked into repo (may contain historical activities from a previous run)
    return os.path.join(os.path.dirname(__file__), "data", "strava_metrics_1.db")


def _activities_table_count(db_path: str) -> Optional[int]:
    """
    Return COUNT(*) from activities, or:
    - None if db file doesn't exist or activities table doesn't exist.
    """
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # activities table might not exist yet in a partially initialized DB
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activities'"
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return None

        cur.execute("SELECT COUNT(*) FROM activities")
        count = cur.fetchone()[0]
        conn.close()
        return int(count)
    except Exception:
        # If DB is corrupt/unreadable, don't block app startup; treat as unknown (no copy check)
        return None


def ensure_db_populated_from_fallback():
    """
    On startup, if the target DB file is missing or its `activities` table is empty,
    copy data from fallback DB (data/strava_metrics_1.db) if it exists.

    Uniqueness per activity_id is guaranteed by activities.activity_id PRIMARY KEY +
    UPSERT behavior in save_activity().
    """
    target_db_path = _get_target_db_path()
    fallback_db_path = _get_fallback_db_path()

    # If fallback doesn't exist, nothing to do
    if not os.path.exists(fallback_db_path):
        return

    target_count = _activities_table_count(target_db_path)

    # Copy conditions:
    # - target DB doesn't exist (count is None because file doesn't exist)
    # - target DB exists but activities table missing (count is None)
    # - target DB exists and activities table exists but is empty
    if target_count is None or target_count == 0:
        os.makedirs(os.path.dirname(target_db_path), exist_ok=True)
        # Copy fallback over target to preserve historical rows as-is
        shutil.copy2(fallback_db_path, target_db_path)


def _get_column_names(conn) -> set:
    """Get all column names in the activities table."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(activities)")
    rows = cur.fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(conn, col_name: str, col_type: str = "REAL"):
    """Safely add a column to activities table if it doesn't exist."""
    existing_cols = _get_column_names(conn)
    if col_name not in existing_cols:
        try:
            conn.execute(f"ALTER TABLE activities ADD COLUMN {col_name} {col_type}")
            conn.commit()
            print(f"✨ Added new column: {col_name} ({col_type})")
            return True
        except Exception as e:
            print(f"⚠️  Could not add column {col_name}: {e}")
            return False
    return False


def _extract_new_metrics(metrics: Dict[str, Any], training_data: Dict[str, Any], weather: Dict[str, Any]) -> Dict[str, tuple]:
    """
    Extract numeric/string fields that could be useful as columns.
    Returns: {column_name: (value, sql_type), ...}
    
    Only extracts top-level numeric/string fields (not nested objects).
    """
    new_fields = {}
    
    # Allowlist of field patterns to consider for column extraction
    # (avoid extracting everything, focus on likely metrics)
    metric_patterns = [
        "power", "cadence", "temperature", "humidity", "wind", "pressure",
        "gear", "device", "trainer", "commute", "manual", "flagged",
        "visible", "estimated", "suffered", "perceived", "normalized",
        "kilojoules", "vi", "workout", "relative", "intensity"
    ]
    
    for source_dict, prefix in [(metrics, "metric_"), (training_data, "training_"), (weather, "weather_")]:
        if not isinstance(source_dict, dict):
            continue
        
        for key, value in source_dict.items():
            # Skip if already a standard column or nested object
            if key in {"metrics_json", "training_json", "weather_json"} or isinstance(value, (dict, list)):
                continue
            
            # Determine if this looks like a metric worth storing as column
            is_candidate = (
                isinstance(value, (int, float, bool, str)) and
                any(pattern in key.lower() for pattern in metric_patterns)
            )
            
            if is_candidate:
                col_name = f"{prefix}{key}".replace("-", "_").lower()[:63]  # SQLite col name limit
                
                if isinstance(value, bool):
                    new_fields[col_name] = (value, "INTEGER")  # SQLite stores bool as 0/1
                elif isinstance(value, (int, float)):
                    new_fields[col_name] = (value, "REAL")
                else:  # string
                    new_fields[col_name] = (value, "TEXT")
    
    return new_fields


def init_db(db_path: Optional[str] = None):
    global _DB_PATH
    _DB_PATH = db_path or DB_PATH

    # If the DB is missing/empty, populate from fallback DB before creating tables.
    # This ensures the app has historical context immediately on first deploy.
    ensure_db_populated_from_fallback()

    # ensure directory exists
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS activities (
            activity_id INTEGER PRIMARY KEY,
            start_date TEXT,
            name TEXT,
            distance_km REAL,
            duration_mins REAL,
            elevation_m REAL,
            average_pace TEXT,
            average_heartrate REAL,
            max_heartrate REAL,
            calories REAL,
            acwr REAL,
            health_status TEXT,
            injury_risk TEXT,
            weather_summary TEXT,
            weather_aqi INTEGER,
            blog_url TEXT,
            post_title TEXT,
            meta_description TEXT,
            avg_speed_m_s REAL,
            avg_pace_s_per_km REAL,
            pace_cv REAL,
            pace_std_s REAL,
            moving_pct REAL,
            elev_gain_per_km REAL,
            difficulty REAL,
            effort_proxy REAL,
            metrics_json TEXT,
            training_json TEXT,
            weather_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activities_start_date ON activities(start_date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_activities_acwr ON activities(acwr)")
    conn.commit()
    conn.close()


def _get_conn():
    global _DB_PATH
    if not _DB_PATH:
        init_db()
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def save_activity(activity_id: int, metrics: Dict[str, Any], training_data: Dict[str, Any], weather: Dict[str, Any], elevation_profile: Dict[str, Any] = None, blog_url: str = None, post_title: str = None, meta_description: str = None):
    """Insert or update an activity record. Uses activity_id as the primary key.

    Stores raw JSON blobs for metrics/training/weather to allow later re-processing.
    Computes and stores HR-less derived metrics (pace variability, elevation per km, etc.).
    Dynamically detects and adds new metric columns as they appear.
    """
    conn = _get_conn()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()

    # prepare values
    start_date = metrics.get("start_date_local") or metrics.get("start_date_local_raw")
    name = metrics.get("name")
    distance_km = _safe_float(metrics.get("distance_km") or metrics.get("distance"))
    duration_mins = _safe_float(metrics.get("duration_mins") or metrics.get("moving_time"))
    elevation_m = _safe_float(metrics.get("elevation_m") or metrics.get("total_elevation_gain"))
    average_pace = metrics.get("average_pace")
    average_heartrate = _safe_float(metrics.get("average_heartrate"))
    max_heartrate = _safe_float(metrics.get("max_heartrate"))
    calories = _safe_float(metrics.get("calories"))
    acwr = _safe_float(training_data.get("acwr"))
    health_status = training_data.get("health_status")
    injury_risk = training_data.get("injury_risk")
    weather_summary = weather.get("summary") if weather else None
    weather_aqi = _safe_int(weather.get("aqi") if weather else None)

    # Compute HR-less derived metrics
    derived = compute_hr_less_metrics(metrics, elevation_profile)
    avg_speed_m_s = derived.get("avg_speed_m_s")
    avg_pace_s_per_km = derived.get("avg_pace_s_per_km")
    pace_cv = derived.get("pace_cv")
    pace_std_s = derived.get("pace_std_s")
    moving_pct = derived.get("moving_pct")
    elev_gain_per_km = derived.get("elev_gain_per_km")
    difficulty = derived.get("difficulty")
    effort_proxy = derived.get("effort_proxy")

    metrics_json = json.dumps(metrics, default=str)
    training_json = json.dumps(training_data, default=str)
    weather_json = json.dumps(weather or {}, default=str)

    # Detect and migrate new metric fields to dedicated columns
    new_metrics = _extract_new_metrics(metrics, training_data, weather)
    new_metric_values = {}
    for col_name, (value, col_type) in new_metrics.items():
        _add_column_if_missing(conn, col_name, col_type)
        new_metric_values[col_name] = value

    # Build dynamic INSERT/UPDATE statement with new metric columns
    standard_cols = [
        "activity_id", "start_date", "name", "distance_km", "duration_mins", "elevation_m",
        "average_pace", "average_heartrate", "max_heartrate", "calories", "acwr", "health_status",
        "injury_risk", "weather_summary", "weather_aqi", "avg_speed_m_s", "avg_pace_s_per_km", 
        "pace_cv", "pace_std_s", "moving_pct", "elev_gain_per_km", "difficulty", "effort_proxy",
        "blog_url", "post_title", "meta_description", "metrics_json", "training_json", "weather_json", 
        "created_at", "updated_at"
    ]
    all_cols = standard_cols + list(new_metric_values.keys())
    
    standard_vals = (
        activity_id, start_date, name, distance_km, duration_mins, elevation_m,
        average_pace, average_heartrate, max_heartrate, calories, acwr, health_status,
        injury_risk, weather_summary, weather_aqi, avg_speed_m_s, avg_pace_s_per_km,
        pace_cv, pace_std_s, moving_pct, elev_gain_per_km, difficulty, effort_proxy,
        blog_url, post_title, meta_description, metrics_json, training_json, weather_json, 
        now, now,
    )
    new_vals = tuple(new_metric_values[col] for col in new_metric_values.keys())
    all_vals = standard_vals + new_vals

    placeholders = ",".join(["?"] * len(all_cols))
    update_set = ",".join([f"{col}=excluded.{col}" for col in all_cols if col not in {"activity_id", "created_at"}])

    insert_sql = f"""
        INSERT INTO activities ({", ".join(all_cols)})
        VALUES ({placeholders})
        ON CONFLICT(activity_id) DO UPDATE SET {update_set}
    """

    try:
        cur.execute(insert_sql, all_vals)
        conn.commit()
    except Exception as e:
        print(f"❌ Error saving activity {activity_id}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def get_recent_activities(limit: int = 20) -> List[Dict[str, Any]]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM activities ORDER BY start_date DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_acwr_trend(limit: int = 28) -> List[Dict[str, Any]]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT start_date, acwr FROM activities WHERE acwr IS NOT NULL ORDER BY start_date DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_activity_count() -> int:
    """Return total number of activities in the database."""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM activities")
    count = cur.fetchone()[0]
    conn.close()
    return count


def is_db_empty() -> bool:
    """Check if database is empty (no activities recorded yet)."""
    return get_activity_count() == 0


def db_exists() -> bool:
    """Check if database file exists at the configured path."""
    global _DB_PATH
    if not _DB_PATH:
        return os.path.exists(DB_PATH)
    return os.path.exists(_DB_PATH)


def _safe_float(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def _safe_int(v):
    try:
        if v is None:
            return None
        return int(v)
    except Exception:
        return None


def compute_hr_less_metrics(metrics: Dict[str, Any], elevation_profile: Dict[str, Any] = None) -> Dict[str, Any]:
    """Compute HR-less derived metrics from raw metrics and elevation profile.

    Returns a dict with keys: avg_speed_m_s, avg_pace_s_per_km, pace_cv, pace_std_s, 
    moving_pct, elev_gain_per_km, difficulty, effort_proxy
    """
    derived = {}

    # Average speed (m/s)
    distance_m = _safe_float(metrics.get("distance")) or (_safe_float(metrics.get("distance_km", 0)) * 1000 if metrics.get("distance_km") else None)
    moving_time_s = _safe_float(metrics.get("moving_time")) or (_safe_float(metrics.get("duration_mins", 0)) * 60 if metrics.get("duration_mins") else None)
    if distance_m and moving_time_s and moving_time_s > 0:
        avg_speed_m_s = distance_m / moving_time_s
        derived["avg_speed_m_s"] = avg_speed_m_s
        # Average pace (s/km)
        if avg_speed_m_s > 0:
            derived["avg_pace_s_per_km"] = 1000 / avg_speed_m_s
    
    # Pace variability (if elevation profile with stream data available)
    if elevation_profile and elevation_profile.get("distance_km"):
        paces_km = elevation_profile.get("pace_per_km", [])
        if paces_km and len(paces_km) > 1:
            import statistics
            mean_pace = statistics.mean(paces_km)
            std_pace = statistics.pstdev(paces_km)
            derived["pace_std_s"] = std_pace
            if mean_pace > 0:
                derived["pace_cv"] = std_pace / mean_pace
    
    # Moving percentage
    elapsed_time_s = _safe_float(metrics.get("elapsed_time")) or moving_time_s
    if moving_time_s and elapsed_time_s and elapsed_time_s > 0:
        derived["moving_pct"] = (moving_time_s / elapsed_time_s) * 100
    
    # Elevation per km
    elevation_m = _safe_float(metrics.get("total_elevation_gain")) or _safe_float(metrics.get("elevation_m"))
    distance_km = _safe_float(metrics.get("distance_km")) or (distance_m / 1000 if distance_m else 0)
    if distance_km and distance_km > 0 and elevation_m:
        elev_per_km = elevation_m / distance_km
        derived["elev_gain_per_km"] = elev_per_km
        # Difficulty score: distance * (1 + 0.03 * elev_per_km)
        derived["difficulty"] = distance_km * (1 + 0.03 * elev_per_km)
    
    # Effort proxy: duration_mins * (reference_pace / avg_pace)
    # Use 5:00/km (300 s/km) as reference if no HR data
    if derived.get("avg_pace_s_per_km") and moving_time_s:
        reference_pace_s = 300  # 5:00/km
        effort_proxy = (moving_time_s / 60) * (reference_pace_s / derived["avg_pace_s_per_km"])
        derived["effort_proxy"] = effort_proxy
    
    return derived


async def trigger_backfill_if_empty():
    """
    Async wrapper to trigger backfill on app startup if database is empty.
    Dynamically imports and calls the backfill_activities function from backfill_db.py.
    """
    # If DB already has data, skip backfill
    if not is_db_empty():
        print("✅ Database already populated. Skipping backfill.")
        return
    
    # Dynamically import the backfill script
    scripts_dir = Path(__file__).parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    
    try:
        from backfill_db import backfill_activities
        
        print("📊 Backfill starting: fetching historical Strava activities...")
        success = await backfill_activities(days=90, force=False)
        
        if success:
            activity_count = get_activity_count()
            print(f"✅ Backfill complete! Database now has {activity_count} activities.")
        else:
            print("⚠️  Backfill was skipped or encountered an issue. App will continue normally.")
    
    except ImportError as e:
        print(f"⚠️  Could not import backfill module: {e}")
    except Exception as e:
        print(f"⚠️  Backfill error (app will continue working): {e}")
    finally:
        # Clean up sys.path
        if str(scripts_dir) in sys.path:
            sys.path.remove(str(scripts_dir))
