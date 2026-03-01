# src/agents/health_agent.py
"""System Health Agent: monitors agent health, error rates, and execution performance."""
from typing import Dict, Any, List
from datetime import datetime
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.services.cache import redis_client, check_redis_connection
from src.services.agent_metrics import get_agent_health
from src.services.monitoring import logger
from src.services.llm_service import LLMService


class HealthAgent(BaseAgent):
    """Agent that monitors system and agent health."""

    def __init__(self):
        super().__init__("health_agent", "health")
        self.llm_service = LLMService()

    def setup_tools(self) -> None:
        pass

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate health report."""
        report_type = (input_data.get("report_type") or "full").strip().lower()
        if report_type == "agents":
            return await self.agent_health_report(input_data)
        if report_type == "infrastructure":
            return await self.infrastructure_health_report(input_data)
        return await self.full_health_report(input_data)

    async def full_health_report(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Full system health: agents + infrastructure."""
        try:
            agent_health = await get_agent_health()
            db_ok = await self._check_db()
            redis_ok = await check_redis_connection()

            overall = "healthy"
            issues = []
            if not db_ok:
                overall = "degraded"
                issues.append("Database disconnected")
            if not redis_ok:
                overall = "degraded"
                issues.append("Redis disconnected")

            degraded_agents = [a for a, h in agent_health.items() if h.get("status") == "degraded"]
            if degraded_agents:
                overall = "degraded" if overall == "healthy" else overall
                issues.append(f"Degraded agents: {', '.join(degraded_agents)}")

            return {
                "status": "success",
                "data": {
                    "overall": overall,
                    "timestamp": datetime.utcnow().isoformat(),
                    "agents": agent_health,
                    "infrastructure": {
                        "database": "connected" if db_ok else "disconnected",
                        "redis": "connected" if redis_ok else "disconnected",
                    },
                    "issues": issues,
                    "recommendations": self._health_recommendations(agent_health, db_ok, redis_ok),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Health report failed: %s", e)
            return self.get_fallback_response(input_data)

    async def agent_health_report(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Agent-specific health metrics."""
        try:
            agent_health = await get_agent_health()
            return {
                "status": "success",
                "data": {
                    "agents": agent_health,
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Agent health report failed: %s", e)
            return self.get_fallback_response(input_data)

    async def infrastructure_health_report(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Infrastructure (DB, Redis) health."""
        try:
            db_ok = await self._check_db()
            redis_ok = await check_redis_connection()
            return {
                "status": "success",
                "data": {
                    "database": "connected" if db_ok else "disconnected",
                    "redis": "connected" if redis_ok else "disconnected",
                    "timestamp": datetime.utcnow().isoformat(),
                },
                "fallback_used": False,
            }
        except Exception as e:
            logger.exception("Infrastructure health failed: %s", e)
            return self.get_fallback_response(input_data)

    async def _check_db(self) -> bool:
        try:
            from src.services.database import check_db_connection
            return await check_db_connection()
        except Exception:
            return False

    def _health_recommendations(
        self,
        agent_health: Dict[str, Any],
        db_ok: bool,
        redis_ok: bool,
    ) -> List[str]:
        recs = []
        if not db_ok:
            recs.append("Check database connection and credentials")
        if not redis_ok:
            recs.append("Check Redis server and connection URL")
        for agent, data in agent_health.items():
            if isinstance(data, dict) and data.get("status") == "degraded":
                err = data.get("error_rate", 0) or 0
                recs.append(f"Review {agent} agent logs - error rate: {err:.0%}")
        if not recs:
            recs.append("All systems operational")
        return recs
