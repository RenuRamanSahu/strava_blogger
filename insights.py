"""Simple insight helpers that query the local SQLite store and compute basic signals.

Functions:
- acwr_summary(limit=28): returns recent ACWR values, average, max, and last value
- acwr_risk_activities(threshold=1.2): returns activities where ACWR exceeds threshold
"""
from typing import List, Dict, Any
from statistics import mean
import db


def acwr_summary(limit: int = 28) -> Dict[str, Any]:
    rows = db.get_acwr_trend(limit=limit)
    acwrs = [r.get('acwr') for r in rows if r.get('acwr') is not None]
    if not acwrs:
        return {'count': 0, 'average': None, 'max': None, 'last': None, 'series': rows}
    return {
        'count': len(acwrs),
        'average': mean(acwrs),
        'max': max(acwrs),
        'last': acwrs[0],  # get_acwr_trend returns newest-first
        'series': rows,
    }


def acwr_risk_activities(threshold: float = 1.2) -> List[Dict[str, Any]]:
    """Return recent activities where ACWR exceeds the given threshold."""
    rows = db.get_recent_activities(limit=200)
    return [r for r in rows if r.get('acwr') is not None and r.get('acwr') > threshold]
