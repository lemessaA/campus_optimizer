# src/agents/insights_agent.py
"""Insights Agent: predictive insights across scheduling, energy, and equipment."""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.services.llm_service import LLMService
from src.services.monitoring import logger


class InsightsAgent(BaseAgent):
    """Agent that generates predictive and actionable insights."""

    def __init__(self):
        super().__init__("insights_agent", "insights")
        self.llm_service = LLMService()

    def setup_tools(self) -> None:
        pass

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate insights based on domain."""
        domain = (input_data.get("domain") or "all").strip().lower()
        if domain == "scheduling":
            return await self.scheduling_insights(input_data)
        if domain == "energy":
            return await self.energy_insights(input_data)
        if domain == "equipment":
            return await self.equipment_insights(input_data)
        return await self.cross_domain_insights(input_data)

    async def scheduling_insights(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insights for classroom scheduling optimization."""
        try:
            async with get_db() as db:
                entries = await crud.get_schedule_entries(db, limit=500)
                classrooms = await self._get_classroom_utilization(db, entries)

            underutilized = [c for c in classrooms if c.get("utilization", 0) < 0.5]
            overbooked = [c for c in classrooms if c.get("utilization", 1) > 0.95]
            building_balance = self._analyze_building_balance(entries)

            insights = []
            if underutilized:
                insights.append({
                    "type": "optimization",
                    "title": "Underutilized classrooms",
                    "detail": f"{len(underutilized)} rooms below 50% capacity",
                    "action": "Consider consolidating small classes or reassigning",
                })
            if overbooked:
                insights.append({
                    "type": "warning",
                    "title": "Near-capacity rooms",
                    "detail": f"{len(overbooked)} rooms above 95% capacity",
                    "action": "Review for potential overflow; consider larger rooms",
                })
            if building_balance:
                insights.append({
                    "type": "info",
                    "title": "Building distribution",
                    "detail": building_balance,
                    "action": "Balance load across buildings for energy efficiency",
                })

            return {
                "status": "success",
                "data": {
                    "insights": insights,
                    "total_courses": len(entries),
                    "utilization_summary": {
                        "underutilized_count": len(underutilized),
                        "overbooked_count": len(overbooked),
                    },
                    "generated_at": datetime.utcnow().isoformat(),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Scheduling insights failed: %s", e)
            return self.get_fallback_response(input_data)

    async def energy_insights(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Predictive energy optimization insights."""
        try:
            async with get_db() as db:
                logs = await crud.get_energy_log_entries(db, hours=168, limit=500)
                historical = await crud.get_historical_energy(db, days=30)

            daily_savings: Dict[str, float] = {}
            for log in logs:
                ts = log.get("timestamp")
                if ts and hasattr(ts, "strftime"):
                    d = ts.strftime("%Y-%m-%d")
                    daily_savings[d] = daily_savings.get(d, 0) + float(log.get("savings_kwh") or 0)

            avg_daily = sum(daily_savings.values()) / len(daily_savings) if daily_savings else 0
            projected_monthly = avg_daily * 22  # weekdays

            insights = []
            if avg_daily > 0:
                insights.append({
                    "type": "positive",
                    "title": "Energy savings trend",
                    "detail": f"Avg {avg_daily:.1f} kWh/day saved; projected ~{projected_monthly:.0f} kWh/month",
                    "action": "Continue empty-room optimizations",
                })
            if len(historical) < 10:
                insights.append({
                    "type": "info",
                    "title": "Data collection",
                    "detail": "More historical data will improve predictions",
                    "action": "Run energy optimizations regularly",
                })

            return {
                "status": "success",
                "data": {
                    "insights": insights,
                    "daily_savings_avg_kwh": round(avg_daily, 1),
                    "projected_monthly_kwh": round(projected_monthly, 1),
                    "generated_at": datetime.utcnow().isoformat(),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Energy insights failed: %s", e)
            return self.get_fallback_response(input_data)

    async def equipment_insights(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Equipment usage and maintenance insights."""
        try:
            async with get_db() as db:
                equipment = await crud.list_equipment(db)
                bookings = await crud.get_recent_equipment_bookings(db, limit=200)

            maintenance_due = []
            for e in equipment:
                last = e.get("last_maintenance")
                if last:
                    try:
                        delta = datetime.utcnow() - last
                        days = delta.days
                    except (TypeError, ValueError):
                        days = 999
                    if days > 90:
                        maintenance_due.append({"name": e.get("name"), "days_since": days})

            usage_by_equipment: Dict[str, int] = {}
            for b in bookings:
                name = b.get("equipment_name", "unknown")
                usage_by_equipment[name] = usage_by_equipment.get(name, 0) + 1
            top_used = sorted(usage_by_equipment.items(), key=lambda x: -x[1])[:5]

            insights = []
            if maintenance_due:
                insights.append({
                    "type": "warning",
                    "title": "Maintenance due",
                    "detail": f"{len(maintenance_due)} equipment items overdue for maintenance",
                    "action": "Schedule maintenance for high-usage equipment",
                })
            if top_used:
                insights.append({
                    "type": "info",
                    "title": "Most used equipment",
                    "detail": ", ".join(f"{n} ({c}x)" for n, c in top_used),
                    "action": "Ensure availability during peak hours",
                })

            return {
                "status": "success",
                "data": {
                    "insights": insights,
                    "maintenance_due_count": len(maintenance_due),
                    "top_used_equipment": dict(top_used),
                    "generated_at": datetime.utcnow().isoformat(),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Equipment insights failed: %s", e)
            return self.get_fallback_response(input_data)

    async def cross_domain_insights(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate insights across all domains."""
        try:
            sched = await self.scheduling_insights(input_data)
            energy = await self.energy_insights(input_data)
            equip = await self.equipment_insights(input_data)

            all_insights = []
            for r in [sched, energy, equip]:
                if r.get("status") == "success" and r.get("data", {}).get("insights"):
                    all_insights.extend(r["data"]["insights"])

            # Optionally use LLM to summarize
            summary = None
            if self.llm_service.client and all_insights:
                try:
                    summary = await self._llm_summarize_insights(all_insights)
                except Exception:
                    pass

            return {
                "status": "success",
                "data": {
                    "insights": all_insights,
                    "summary": summary or f"{len(all_insights)} insights across scheduling, energy, equipment",
                    "scheduling": sched.get("data", {}),
                    "energy": energy.get("data", {}),
                    "equipment": equip.get("data", {}),
                    "generated_at": datetime.utcnow().isoformat(),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Cross-domain insights failed: %s", e)
            return self.get_fallback_response(input_data)

    async def _get_classroom_utilization(self, db, entries: List[dict]) -> List[dict]:
        by_room: Dict[str, List[float]] = {}
        for e in entries:
            room = e.get("classroom_name", "unknown")
            util = e.get("utilization_rate", 0) or 0
            by_room.setdefault(room, []).append(util)
        return [
            {"room": r, "utilization": sum(v) / len(v) if v else 0}
            for r, v in by_room.items()
        ]

    def _analyze_building_balance(self, entries: List[dict]) -> Optional[str]:
        by_building: Dict[str, int] = {}
        for e in entries:
            b = e.get("building", "unknown")
            by_building[b] = by_building.get(b, 0) + 1
        if len(by_building) < 2:
            return None
        counts = list(by_building.values())
        if max(counts) / (min(counts) or 1) > 3:
            return f"Uneven distribution: {dict(by_building)}"
        return None

    async def _llm_summarize_insights(self, insights: List[Dict]) -> str:
        import asyncio
        text = "\n".join(
            f"- [{i.get('type')}] {i.get('title')}: {i.get('detail')}"
            for i in insights[:10]
        )
        prompt = f"Summarize these campus optimization insights in 2-3 sentences:\n\n{text}\n\nSummary:"
        completion = self.llm_service.client.chat.completions.create(
            model=self.llm_service.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return (completion.choices[0].message.content or "").strip()
