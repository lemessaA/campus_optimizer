# src/agents/analytics_agent.py
"""Analytics Agent: analyzes system metrics, usage patterns, and performance across the app."""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.services.cache import redis_client
from src.services.monitoring import logger
import json
from src.services.llm_service import LLMService


class AnalyticsAgent(BaseAgent):
    """Agent that analyzes app metrics, usage patterns, and generates reports."""

    def __init__(self):
        super().__init__("analytics_agent", "analytics")
        self.llm_service = LLMService()

    def setup_tools(self) -> None:
        pass

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the appropriate analytics handler."""
        report_type = (input_data.get("report_type") or "full").strip().lower()
        if report_type == "usage":
            return await self.analyze_usage_patterns(input_data)
        if report_type == "performance":
            return await self.analyze_performance(input_data)
        if report_type == "trends":
            return await self.analyze_trends(input_data)
        return await self.generate_full_report(input_data)

    async def generate_full_report(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive analytics report across all domains."""
        try:
            async with get_db() as db:
                usage = await self._gather_usage_metrics(db)
                performance = await self._gather_performance_metrics(db)
                trends = await self._gather_trend_data(db)

            report = {
                "generated_at": datetime.utcnow().isoformat(),
                "period": "24h",
                "usage": usage,
                "performance": performance,
                "trends": trends,
                "summary": self._generate_summary(usage, performance, trends),
            }
            return {
                "status": "success",
                "data": report,
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Analytics full report failed: %s", e)
            return self.get_fallback_response(input_data)

    async def analyze_usage_patterns(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze usage patterns: courses, equipment, support, energy."""
        try:
            async with get_db() as db:
                schedule_entries = await crud.get_schedule_entries(db, limit=500)
                equipment_bookings = await crud.get_recent_equipment_bookings(db, limit=200)
                energy_logs = await crud.get_energy_log_entries(db, hours=168, limit=500)
                tickets = await self._get_ticket_stats(db)

            # Aggregate by building
            building_usage: Dict[str, int] = {}
            for e in schedule_entries:
                b = e.get("building", "unknown")
                building_usage[b] = building_usage.get(b, 0) + 1

            # Equipment by lab
            lab_usage: Dict[str, int] = {}
            for b in equipment_bookings:
                # Equipment name/lab from booking - we need lab from equipment
                lab_usage["total"] = lab_usage.get("total", 0) + 1

            # Energy by building
            energy_by_building: Dict[str, float] = {}
            for log in energy_logs:
                b = log.get("building", "unknown")
                energy_by_building[b] = energy_by_building.get(b, 0) + float(
                    log.get("savings_kwh", 0) or 0
                )

            return {
                "status": "success",
                "data": {
                    "building_utilization": building_usage,
                    "equipment_bookings_count": len(equipment_bookings),
                    "energy_savings_by_building": energy_by_building,
                    "support_tickets": tickets,
                    "peak_hours": await self._infer_peak_hours(schedule_entries),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Usage analysis failed: %s", e)
            return self.get_fallback_response(input_data)

    async def analyze_performance(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze agent performance from Redis metrics."""
        try:
            metrics = await self._load_agent_metrics()
            return {
                "status": "success",
                "data": {
                    "agent_metrics": metrics,
                    "recommendations": self._performance_recommendations(metrics),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Performance analysis failed: %s", e)
            return self.get_fallback_response(input_data)

    async def analyze_trends(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze trends over time."""
        try:
            async with get_db() as db:
                energy_logs = await crud.get_energy_log_entries(db, hours=168, limit=500)
                schedule_entries = await crud.get_schedule_entries(db, limit=500)

            daily_savings: Dict[str, float] = {}
            for log in energy_logs:
                ts = log.get("timestamp")
                if ts and hasattr(ts, "strftime"):
                    day = ts.strftime("%Y-%m-%d")
                    daily_savings[day] = daily_savings.get(day, 0) + float(
                        log.get("savings_kwh", 0) or 0
                    )

            return {
                "status": "success",
                "data": {
                    "energy_savings_trend": dict(sorted(daily_savings.items())),
                    "schedule_volume": len(schedule_entries),
                    "trend_direction": "improving" if len(daily_savings) > 1 else "stable",
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Trend analysis failed: %s", e)
            return self.get_fallback_response(input_data)

    async def _gather_usage_metrics(self, db) -> Dict[str, Any]:
        schedule = await crud.get_schedule_entries(db, limit=500)
        equipment = await crud.get_recent_equipment_bookings(db, limit=200)
        energy = await crud.get_energy_log_entries(db, hours=24, limit=200)
        total_savings = sum(float(e.get("savings_kwh") or 0) for e in energy)
        return {
            "courses_scheduled": len(schedule),
            "equipment_bookings": len(equipment),
            "energy_actions_24h": len(energy),
            "energy_savings_24h_kwh": round(total_savings, 1),
        }

    async def _gather_performance_metrics(self, db) -> Dict[str, Any]:
        return await self._load_agent_metrics()

    async def _gather_trend_data(self, db) -> Dict[str, Any]:
        energy = await crud.get_energy_log_entries(db, hours=168, limit=500)
        daily = {}
        for e in energy:
            ts = e.get("timestamp")
            if ts and hasattr(ts, "strftime"):
                d = ts.strftime("%Y-%m-%d")
                daily[d] = daily.get(d, 0) + float(e.get("savings_kwh") or 0)
        return {"energy_savings_by_day": daily}

    async def _get_ticket_stats(self, db) -> Dict[str, Any]:
        try:
            from sqlalchemy import select, func
            from src.database.models import SupportTicket

            result = await db.execute(
                select(
                    SupportTicket.status,
                    func.count(SupportTicket.id).label("count"),
                ).group_by(SupportTicket.status)
            )
            rows = result.all()
            return {row[0]: row[1] for row in rows}
        except Exception:
            return {}

    async def _load_agent_metrics(self) -> Dict[str, Any]:
        """Load agent execution metrics from Redis."""
        if not redis_client:
            return {}
        metrics = {}
        for agent in ["scheduling", "equipment", "energy", "support", "notification"]:
            key = f"metrics:agent:{agent}"
            raw = await redis_client.get(key)
            if raw:
                try:
                    metrics[agent] = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    metrics[agent] = {"raw": str(raw)}
        return metrics

    def _performance_recommendations(self, metrics: Dict[str, Any]) -> List[str]:
        recs = []
        for agent, data in metrics.items():
            if isinstance(data, dict):
                err_rate = data.get("error_rate", 0) or 0
                if err_rate > 0.1:
                    recs.append(f"{agent}: High error rate ({err_rate:.0%}) - review logs")
                avg_ms = data.get("avg_duration_ms", 0) or 0
                if avg_ms > 5000:
                    recs.append(f"{agent}: Slow avg response ({avg_ms:.0f}ms) - consider optimization")
        if not recs:
            recs.append("All agents performing within expected ranges.")
        return recs

    async def _infer_peak_hours(self, entries: List[dict]) -> List[str]:
        hour_counts: Dict[str, int] = {}
        for e in entries:
            t = e.get("time")
            if t:
                hour = str(t)[:2] if len(str(t)) >= 2 else "00"
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
        sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])[:5]
        return [f"{h}:00" for h, _ in sorted_hours]

    def _generate_summary(
        self,
        usage: Dict[str, Any],
        performance: Dict[str, Any],
        trends: Dict[str, Any],
    ) -> str:
        parts = []
        if usage.get("courses_scheduled"):
            parts.append(f"{usage['courses_scheduled']} courses scheduled")
        if usage.get("energy_savings_24h_kwh"):
            parts.append(f"{usage['energy_savings_24h_kwh']} kWh saved (24h)")
        if not parts:
            parts.append("No significant activity in the last 24h")
        return "; ".join(parts)
