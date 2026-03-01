# src/services/agent_metrics.py
"""Track agent execution metrics for analytics and health monitoring."""
from typing import Optional
from datetime import datetime
import time
import json

from src.services.cache import redis_client
from src.services.monitoring import logger

METRICS_TTL = 86400  # 24 hours
WINDOW_SIZE = 100  # Keep last N executions per agent


async def record_agent_execution(
    agent_name: str,
    status: str,
    duration_ms: float,
    event_type: Optional[str] = None,
) -> None:
    """Record an agent execution for analytics."""
    if not redis_client:
        return
    try:
        key = f"metrics:agent:{agent_name}"
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": status,
            "duration_ms": round(duration_ms, 2),
            "event_type": event_type or "unknown",
        }
        raw = await redis_client.get(key)
        data = json.loads(raw) if raw else {"executions": [], "total": 0, "errors": 0}
        data["executions"] = data.get("executions", [])[-WINDOW_SIZE:]
        data["executions"].append(entry)
        data["total"] = data.get("total", 0) + 1
        if status in ("error", "fallback"):
            data["errors"] = data.get("errors", 0) + 1
        durations = [e["duration_ms"] for e in data["executions"]]
        data["avg_duration_ms"] = sum(durations) / len(durations) if durations else 0
        data["error_rate"] = data["errors"] / data["total"] if data["total"] else 0
        data["last_updated"] = datetime.utcnow().isoformat()
        await redis_client.setex(key, METRICS_TTL, json.dumps(data))
    except Exception as e:
        logger.warning("Failed to record agent metrics: %s", e)


async def get_agent_health() -> dict:
    """Get health summary for all agents from metrics."""
    if not redis_client:
        return {}
    agents = ["scheduling", "equipment", "energy", "support", "notification", "analytics", "health", "insights"]
    health = {}
    for agent in agents:
        raw = await redis_client.get(f"metrics:agent:{agent}")
        if raw:
            try:
                data = json.loads(raw)
                health[agent] = {
                    "status": "degraded" if data.get("error_rate", 0) > 0.2 else "healthy",
                    "avg_duration_ms": data.get("avg_duration_ms", 0),
                    "error_rate": data.get("error_rate", 0),
                    "total_executions": data.get("total", 0),
                    "last_updated": data.get("last_updated"),
                }
            except Exception:
                health[agent] = {"status": "unknown"}
    return health
