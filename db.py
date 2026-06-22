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


def save_activity(activity_id: int, metrics: Dict[str, Any], training_data: Dict[str, Any], weather: Dict[str, Any], blog_url: str = None, post_title: str = None, meta_description: str = None):
    """Insert or update an activity record. Uses activity_id as the primary key.

    Stores raw JSON blobs for metrics/training/weather to allow later re-processing.
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

    metrics_json = json.dumps(metrics, default=str)
    training_json = json.dumps(training_data, default=str)
    weather_json = json.dumps(weather or {}, default=str)

    cur.execute(
        """
        INSERT INTO activities (
            activity_id, start_date, name, distance_km, duration_mins, elevation_m,
            average_pace, average_heartrate, max_heartrate, calories, acwr, health_status,
            injury_risk, weather_summary, weather_aqi, blog_url, post_title, meta_description,
            metrics_json, training_json, weather_json, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            injury_risk, weather_summary, weather_aqi, blog_url, post_title, meta_description,
            metrics_json, training_json, weather_json, now, now,
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
