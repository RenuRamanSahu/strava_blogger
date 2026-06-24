"""Simple insight helpers that compute useful training signals from cached activities."""
from typing import List, Dict, Any
from statistics import mean
from cache import get_cached_activities


def acwr_summary(limit: int = 28) -> Dict[str, Any]:
    activities = get_cached_activities()[:limit]
    acwrs = [a.get('acwr') for a in activities if a.get('acwr') is not None]
    if not acwrs:
        return {'count': 0, 'average': None, 'max': None, 'last': None, 'series': activities}
    return {
        'count': len(acwrs),
        'average': mean(acwrs),
        'max': max(acwrs),
        'last': acwrs[0],
        'series': activities,
    }


def acwr_risk_activities(threshold: float = 1.2) -> List[Dict[str, Any]]:
    """Return recent activities where ACWR exceeds the given threshold."""
    activities = get_cached_activities()[:200]
    return [a for a in activities if a.get('acwr') is not None and a.get('acwr') > threshold]
