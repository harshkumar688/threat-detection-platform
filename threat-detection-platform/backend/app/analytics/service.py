"""
Analytics Service

Computes all analytics metrics from real data in the incident repository.
Every number returned is computed from actual stored records.
No fabricated data. If there are no incidents, counts are zero.

Provides:
1. Dashboard summary KPIs
2. Incidents over time (timeline)
3. Detection counts (from incidents as proxy until detection table exists)
4. Weapon category distribution
5. Risk-level distribution
6. Camera-wise incident counts
7. Hour-wise incident trends
8. Resolution status breakdown
9. False-positive rate (from labeled data)
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from app.incidents.models import Incident, IncidentStatus
from app.incidents.repository import IncidentRepository


class AnalyticsService:
    """
    Analytics computations backed by real data.

    All methods query the repository and perform in-memory aggregation.
    In a production system with PostgreSQL, these would be SQL GROUP BY queries.
    """

    def __init__(self, repository: IncidentRepository):
        self._repo = repository

    async def get_summary(self, camera_count: int = 0) -> Dict:
        """
        Dashboard summary KPIs.

        Returns real counts from the incident store.
        """
        all_incidents = await self._repo.list_all(limit=10000, offset=0)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total = len(all_incidents)
        open_count = sum(1 for i in all_incidents if i.status == IncidentStatus.OPEN)
        acknowledged_count = sum(1 for i in all_incidents if i.status == IncidentStatus.ACKNOWLEDGED)

        # Incidents by severity
        by_severity: Dict[str, int] = Counter()
        for inc in all_incidents:
            if inc.status not in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE):
                by_severity[inc.risk_level] += 1

        # Today's detections (using incident count as proxy since detection table is future)
        today_count = sum(1 for i in all_incidents if i.created_at >= today_start)

        # Average response time (time from OPEN to ACKNOWLEDGED)
        response_times = []
        for inc in all_incidents:
            if inc.acknowledged_at and inc.created_at:
                delta = (inc.acknowledged_at - inc.created_at).total_seconds()
                if delta > 0:
                    response_times.append(delta)

        avg_response = (sum(response_times) / len(response_times)) if response_times else None

        return {
            "total_incidents": total,
            "open_incidents": open_count + acknowledged_count,
            "total_detections_today": today_count,
            "active_cameras": camera_count,
            "avg_response_time_seconds": round(avg_response, 1) if avg_response else None,
            "incidents_by_severity": dict(by_severity),
        }

    async def get_incidents_timeline(
        self,
        granularity: str = "daily",
        days: int = 7,
    ) -> Dict:
        """
        Incidents over time.

        Groups incidents by time bucket (hourly/daily/weekly).
        Returns real counts — zeros where no incidents occurred.
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        # Filter to time range
        in_range = [i for i in all_incidents if i.created_at >= start]

        # Generate time buckets
        data_points = []

        if granularity == "hourly":
            for hour_offset in range(days * 24):
                bucket_start = start + timedelta(hours=hour_offset)
                bucket_end = bucket_start + timedelta(hours=1)
                count = sum(1 for i in in_range if bucket_start <= i.created_at < bucket_end)
                data_points.append({
                    "timestamp": bucket_start.isoformat(),
                    "count": count,
                    "label": bucket_start.strftime("%H:00"),
                })
        elif granularity == "daily":
            # Generate daily buckets from (days-1) days ago through today
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            for day_offset in range(days):
                bucket_start = today_start - timedelta(days=days - 1 - day_offset)
                bucket_end = bucket_start + timedelta(days=1)
                count = sum(1 for i in in_range if bucket_start <= i.created_at < bucket_end)
                data_points.append({
                    "timestamp": bucket_start.isoformat(),
                    "count": count,
                    "label": bucket_start.strftime("%b %d"),
                })
        elif granularity == "weekly":
            for week_offset in range(days // 7 + 1):
                bucket_start = start + timedelta(weeks=week_offset)
                bucket_end = bucket_start + timedelta(weeks=1)
                count = sum(1 for i in in_range if bucket_start <= i.created_at < bucket_end)
                data_points.append({
                    "timestamp": bucket_start.isoformat(),
                    "count": count,
                    "label": f"Week {week_offset + 1}",
                })

        total = sum(p["count"] for p in data_points)

        return {
            "data": data_points,
            "granularity": granularity,
            "total": total,
        }

    async def get_weapon_distribution(self) -> Dict:
        """
        Weapon category distribution.

        Counts incidents grouped by threat_type (handgun, rifle, knife, etc.).
        """
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        counter: Counter = Counter()
        for inc in all_incidents:
            counter[inc.threat_type] += 1

        total = sum(counter.values())
        data = [
            {
                "name": name,
                "count": count,
                "percentage": round((count / total) * 100, 1) if total > 0 else 0,
            }
            for name, count in counter.most_common()
        ]

        return {"data": data, "total": total, "group_by": "weapon_type"}

    async def get_risk_level_distribution(self) -> Dict:
        """
        Risk-level distribution.

        Counts incidents grouped by risk_level (LOW/MEDIUM/HIGH/CRITICAL).
        """
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        counter: Counter = Counter()
        for inc in all_incidents:
            counter[inc.risk_level] += 1

        total = sum(counter.values())
        # Fixed order
        order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        data = [
            {
                "name": level,
                "count": counter.get(level, 0),
                "percentage": round((counter.get(level, 0) / total) * 100, 1) if total > 0 else 0,
            }
            for level in order
            if counter.get(level, 0) > 0
        ]

        return {"data": data, "total": total, "group_by": "risk_level"}

    async def get_camera_distribution(self) -> Dict:
        """
        Camera-wise incident counts.

        Groups incidents by camera_id.
        """
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        counter: Counter = Counter()
        for inc in all_incidents:
            label = inc.location_name if inc.location_name else inc.camera_id
            counter[label] += 1

        total = sum(counter.values())
        data = [
            {
                "name": name,
                "count": count,
                "percentage": round((count / total) * 100, 1) if total > 0 else 0,
            }
            for name, count in counter.most_common()
        ]

        return {"data": data, "total": total, "group_by": "camera"}

    async def get_hourly_trend(self, days: int = 7) -> Dict:
        """
        Hour-wise incident trend.

        Aggregates incidents by hour-of-day (0-23) to show peak times.
        """
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        in_range = [i for i in all_incidents if i.created_at >= start]

        hourly: Dict[int, int] = defaultdict(int)
        for inc in in_range:
            hourly[inc.created_at.hour] += 1

        data = [
            {
                "timestamp": f"{hour:02d}:00",
                "count": hourly.get(hour, 0),
                "label": f"{hour:02d}:00",
            }
            for hour in range(24)
        ]

        return {"data": data, "granularity": "hourly_aggregate", "total": sum(hourly.values())}

    async def get_resolution_status(self) -> Dict:
        """
        Resolution status breakdown.

        Counts incidents by their current status.
        """
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        counter: Counter = Counter()
        for inc in all_incidents:
            counter[inc.status.value] += 1

        total = sum(counter.values())
        data = [
            {
                "name": status,
                "count": count,
                "percentage": round((count / total) * 100, 1) if total > 0 else 0,
            }
            for status, count in counter.most_common()
        ]

        return {"data": data, "total": total, "group_by": "status"}

    async def get_false_positive_rate(self) -> Dict:
        """
        False-positive rate.

        Computed ONLY from incidents that have reached a terminal state
        (RESOLVED or FALSE_POSITIVE). Never fabricated — if insufficient
        labeled data, returns null rate with explanation.
        """
        all_incidents = await self._repo.list_all(limit=10000, offset=0)

        terminal = [
            i for i in all_incidents
            if i.status in (IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE)
        ]

        total_labeled = len(terminal)
        false_positives = sum(1 for i in terminal if i.status == IncidentStatus.FALSE_POSITIVE)
        true_positives = sum(1 for i in terminal if i.status == IncidentStatus.RESOLVED)

        if total_labeled < 5:
            return {
                "rate": None,
                "false_positives": false_positives,
                "true_positives": true_positives,
                "total_labeled": total_labeled,
                "note": "Insufficient labeled data (minimum 5 resolved incidents required).",
            }

        rate = round((false_positives / total_labeled) * 100, 2)

        return {
            "rate": rate,
            "false_positives": false_positives,
            "true_positives": true_positives,
            "total_labeled": total_labeled,
            "note": f"Based on {total_labeled} resolved incidents.",
        }
