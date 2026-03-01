# src/agents/energy_agent.py
"""Energy agent: optimization, insights, and responsive user-facing output."""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.services.cache import redis_client
from src.services.monitoring import logger
from src.services.llm_service import LLMService

# Default recommendations when no data-driven ones apply
DEFAULT_RECOMMENDATIONS = [
    "Schedule heavy equipment use during off-peak hours to reduce peak demand.",
    "Enable power-saving mode in empty labs and classrooms.",
    "Consider LED lighting upgrades in high-usage buildings.",
    "Set HVAC setbacks when rooms are unoccupied.",
    "Review and consolidate after-hours usage.",
]

# CO2 kg per kWh (approximate grid factor)
KG_CO2_PER_KWH = 0.4


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _response(
    status: str,
    data: Optional[Dict[str, Any]] = None,
    message: str = "",
    summary: str = "",
    error: Optional[str] = None,
    fallback_used: bool = False,
) -> Dict[str, Any]:
    """Standard response shape for UI and API."""
    return {
        "status": status,
        "data": data or {},
        "message": message,
        "summary": summary or message,
        "error": error,
        "fallback_used": fallback_used,
    }


class EnergyAgent(BaseAgent):
    """Agent responsible for energy usage optimization and insights."""

    def __init__(self):
        super().__init__("energy_agent", "energy")
        self.energy_saving_threshold = 0.3  # 30% saving target
        self.kwh_per_empty_room_hour = 2.5  # Estimated savings per empty room per hour
        self.llm_service = LLMService()

    def setup_tools(self) -> None:
        pass

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Route to the right handler and return a consistent, user-friendly response."""
        event_type = (input_data.get("event_type") or "").strip().lower()
        if not event_type:
            return _response(
                "error",
                error="Missing event_type.",
                message="Please specify event_type: classroom_empty, schedule_updated, or energy_optimization.",
                fallback_used=False,
            )
        if event_type == "classroom_empty":
            return await self.optimize_empty_room(input_data)
        if event_type == "schedule_updated":
            return await self.optimize_building_energy(input_data)
        if event_type == "energy_optimization":
            return await self.get_energy_insights(input_data)
        return _response(
            "fallback",
            message=f"Unknown event type '{event_type}'. Use: classroom_empty, schedule_updated, energy_optimization.",
            summary="Unknown event type.",
            fallback_used=True,
        )

    async def optimize_empty_room(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize energy for empty classrooms in a building. Returns user-facing summary and details."""
        building = (data.get("building") or "").strip()
        if not building:
            return _response(
                "error",
                error="Building is required.",
                message="Please provide a building name to optimize empty rooms.",
                fallback_used=False,
            )
        try:
            async with get_db() as db:
                await crud.get_current_energy_usage(db, building)  # can use for context
                empty_rooms = await crud.get_empty_classrooms(db, building)
                savings_actions: List[Dict[str, Any]] = []
                total_savings = 0.0
                for room in empty_rooms:
                    name = getattr(room, "name", None) or f"Room_{getattr(room, 'id', '?')}"
                    saving = self.kwh_per_empty_room_hour
                    total_savings += saving
                    savings_actions.append({
                        "room": name,
                        "actions": [
                            "Reduce HVAC by 50%",
                            "Turn off lights",
                            "Disable non-critical equipment",
                        ],
                        "estimated_saving_kwh": round(saving, 1),
                    })
                await crud.create_energy_log(
                    db,
                    building=building,
                    action="empty_room_optimization",
                    savings_kwh=total_savings,
                )
                try:
                    if redis_client:
                        await redis_client.setex(
                            f"energy:optimization:{building}",
                            3600,
                            str(round(total_savings, 1)),
                        )
                except Exception as cache_err:
                    logger.warning("Energy cache write failed: %s", cache_err)

                carbon_kg = round(total_savings * KG_CO2_PER_KWH, 1)
                n = len(empty_rooms)
                message = (
                    f"Optimized {n} empty room(s) in {building}. "
                    f"Estimated savings: {total_savings:.1f} kWh (~{carbon_kg} kg CO₂ avoided)."
                )
                summary = f"{n} rooms optimized, {total_savings:.1f} kWh saved" if n else f"No empty rooms in {building}"
                return _response(
                    "success",
                    data={
                        "building": building,
                        "optimized_rooms": n,
                        "actions": savings_actions,
                        "total_savings_kwh": round(total_savings, 1),
                        "carbon_reduction_kg": carbon_kg,
                    },
                    message=message,
                    summary=summary,
                )
        except Exception as e:
            logger.exception("Energy optimization failed for building %s: %s", building, e)
            return _response(
                "fallback",
                error=str(e),
                message="Unable to run empty-room optimization. Please try again or check building name.",
                summary="Optimization failed.",
                fallback_used=True,
            )

    async def optimize_building_energy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a 24h energy plan from occupancy schedule. Returns plan and user-facing summary."""
        building = (data.get("building") or "").strip()
        schedule = data.get("schedule") or []
        if not building:
            return _response(
                "error",
                error="Building is required.",
                message="Please provide a building name for schedule-based optimization.",
                fallback_used=False,
            )
        try:
            async with get_db() as db:
                occupancy = await self.predict_occupancy(db, building, schedule)
                plan: List[Dict[str, Any]] = []
                total_savings = 0.0
                for hour in range(24):
                    time_str = f"{hour:02d}:00"
                    occupants = occupancy.get(time_str, 0)
                    if occupants == 0:
                        plan.append({
                            "time": time_str,
                            "action": "Deep energy saving mode",
                            "hvac": "0%",
                            "lights": "0%",
                            "savings_kwh": 50,
                        })
                        total_savings += 50
                    elif occupants < 10:
                        plan.append({
                            "time": time_str,
                            "action": "Reduced operation",
                            "hvac": "30%",
                            "lights": "20%",
                            "savings_kwh": 35,
                        })
                        total_savings += 35
                    else:
                        plan.append({
                            "time": time_str,
                            "action": "Normal operation",
                            "hvac": "100%",
                            "lights": "100%",
                            "savings_kwh": 0,
                        })
                monthly = total_savings * 22  # weekdays
                message = (
                    f"24-hour plan for {building}: estimated daily savings {total_savings:.0f} kWh "
                    f"(~{monthly:.0f} kWh/month on weekdays)."
                )
                summary = f"Daily savings: {total_savings:.0f} kWh | Monthly (wd): ~{monthly:.0f} kWh"
                return _response(
                    "success",
                    data={
                        "building": building,
                        "optimization_plan": plan,
                        "daily_savings_kwh": round(total_savings, 1),
                        "monthly_savings_kwh": round(monthly, 1),
                    },
                    message=message,
                    summary=summary,
                )
        except Exception as e:
            logger.exception("Building energy optimization failed for %s: %s", building, e)
            return _response(
                "fallback",
                error=str(e),
                message="Could not generate building energy plan. Please try again.",
                summary="Plan generation failed.",
                fallback_used=True,
            )

    async def get_energy_insights(self, input_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Aggregate 24h logs, peak periods, cache, and recommendations. Always returns a usable response."""
        try:
            async with get_db() as db:
                logs = await crud.get_recent_energy_logs(db, hours=24)
                total_savings = sum(
                    _safe_float(getattr(log, "savings_kwh", None))
                    for log in logs
                )
                n_logs = len(logs)
                avg_savings = total_savings / n_logs if n_logs else 0.0

                peak_periods = await self.predict_peak_periods(db)
                cached_optimizations: List[Dict[str, Any]] = []
                try:
                    if redis_client:
                        keys = await redis_client.keys("energy:optimization:*")
                        for key in keys:
                            val = await redis_client.get(key)
                            if key and val is not None:
                                decoded = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                                cached_optimizations.append({"key": key, "savings_kwh": decoded})
                except Exception as cache_err:
                    logger.warning("Energy cache read failed: %s", cache_err)

                recommendations = list(DEFAULT_RECOMMENDATIONS)
                if peak_periods:
                    hours = [str(p["hour"]) for p in peak_periods[:3] if p.get("hour")]
                    if hours:
                        recommendations.insert(
                            0,
                            f"Peak usage typically at {', '.join(hours)}. Shift non-essential load outside these hours.",
                        )
                if total_savings > 0:
                    recommendations.insert(
                        0,
                        f"Last 24h you saved {total_savings:.1f} kWh (~{total_savings * KG_CO2_PER_KWH:.1f} kg CO₂). Keep empty-room optimizations enabled.",
                    )

                carbon_kg = round(total_savings * KG_CO2_PER_KWH, 1)
                message = (
                    f"Last 24h: {total_savings:.1f} kWh saved (~{carbon_kg} kg CO₂). "
                    f"{len(peak_periods)} peak period(s) identified; see recommendations below."
                )
                summary = f"24h savings: {total_savings:.1f} kWh | Peaks: {len(peak_periods)}"
                return _response(
                    "success",
                    data={
                        "total_savings_24h": round(total_savings, 1),
                        "average_savings_per_action": round(avg_savings, 1),
                        "peak_periods": peak_periods,
                        "cached_optimizations": cached_optimizations,
                        "recommendations": recommendations,
                        "carbon_reduction_kg": carbon_kg,
                    },
                    message=message,
                    summary=summary,
                )
        except Exception as e:
            logger.exception("Energy insights failed: %s", e)
            return _response(
                "fallback",
                error=str(e),
                message="Unable to load energy insights. Please try again later.",
                summary="Insights unavailable.",
                fallback_used=True,
            )

    async def predict_occupancy(
        self, db: Any, building: str, schedule: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Predict occupants per hour for a building from schedule events."""
        occupancy = {f"{h:02d}:00": 0 for h in range(24)}
        for event in schedule:
            if event.get("building") != building:
                continue
            time_str = event.get("time")
            students = _safe_float(event.get("students"), 0.0)
            if time_str in occupancy:
                occupancy[time_str] += int(students)
        return occupancy

    async def predict_peak_periods(self, db: Any) -> List[Dict[str, Any]]:
        """Identify high-consumption hours from recent history. Safe when no data."""
        try:
            historical = await crud.get_historical_energy(db, days=30)
            hourly_consumption: Dict[int, List[float]] = {}
            for log in historical:
                ts = getattr(log, "timestamp", None)
                consumption = _safe_float(getattr(log, "consumption", None))
                savings = _safe_float(getattr(log, "savings_kwh", None))
                # Use consumption if present, else treat savings as proxy for activity
                value = consumption if consumption > 0 else (savings if savings > 0 else 0)
                if value <= 0:
                    continue
                hour = ts.hour if (ts is not None and hasattr(ts, "hour")) else 0
                if hour not in hourly_consumption:
                    hourly_consumption[hour] = []
                hourly_consumption[hour].append(value)
            peak_periods = []
            threshold = 100.0
            for hour, values in sorted(hourly_consumption.items()):
                avg = sum(values) / len(values) if values else 0
                if avg > threshold:
                    peak_periods.append({
                        "hour": f"{hour:02d}:00",
                        "average_consumption": round(avg, 1),
                        "peak_likelihood": "high",
                    })
            return peak_periods
        except Exception as e:
            logger.warning("Peak period prediction failed: %s", e)
            return []
