"""Simple SQLite storage for Strava activity metrics and derived training data.

Provides:
- init_db(db_path=None)
- save_activity(activity_id, metrics, training_data, weather, blog_url, post_title, meta_description)
- get_acwr_trend(limit=28)
- get_recent_activities(limit=20)

This module uses the stdlib sqlite3 module and stores raw JSON blobs for later analysis.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import DB_PATH

_DB_PATH = None


def init_db(db_path: Optional[str] = None):
    global _DB_PATH
    _DB_PATH = db_path or DB_PATH
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

    cur.execute(
        """
        INSERT INTO activities (
            activity_id, start_date, name, distance_km, duration_mins, elevation_m,
            average_pace, average_heartrate, max_heartrate, calories, acwr, health_status,
            injury_risk, weather_summary, weather_aqi, avg_speed_m_s, avg_pace_s_per_km, 
            pace_cv, pace_std_s, moving_pct, elev_gain_per_km, difficulty, effort_proxy,
            blog_url, post_title, meta_description, metrics_json, training_json, weather_json, 
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(activity_id) DO UPDATE SET
            start_date=excluded.start_date,
            name=excluded.name,
            distance_km=excluded.distance_km,
            duration_mins=excluded.duration_mins,
            elevation_m=excluded.elevation_m,
            average_pace=excluded.average_pace,
            average_heartrate=excluded.average_heartrate,
            max_heartrate=excluded.max_heartrate,
            calories=excluded.calories,
            acwr=excluded.acwr,
            health_status=excluded.health_status,
            injury_risk=excluded.injury_risk,
            weather_summary=excluded.weather_summary,
            weather_aqi=excluded.weather_aqi,
            avg_speed_m_s=excluded.avg_speed_m_s,
            avg_pace_s_per_km=excluded.avg_pace_s_per_km,
            pace_cv=excluded.pace_cv,
            pace_std_s=excluded.pace_std_s,
            moving_pct=excluded.moving_pct,
            elev_gain_per_km=excluded.elev_gain_per_km,
            difficulty=excluded.difficulty,
            effort_proxy=excluded.effort_proxy,
            blog_url=excluded.blog_url,
            post_title=excluded.post_title,
            meta_description=excluded.meta_description,
            metrics_json=excluded.metrics_json,
            training_json=excluded.training_json,
            weather_json=excluded.weather_json,
            updated_at=excluded.updated_at
        """,
        (
            activity_id, start_date, name, distance_km, duration_mins, elevation_m,
            average_pace, average_heartrate, max_heartrate, calories, acwr, health_status,
            injury_risk, weather_summary, weather_aqi, avg_speed_m_s, avg_pace_s_per_km,
            pace_cv, pace_std_s, moving_pct, elev_gain_per_km, difficulty, effort_proxy,
            blog_url, post_title, meta_description, metrics_json, training_json, weather_json, 
            now, now,
        ),
    )
    conn.commit()
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
