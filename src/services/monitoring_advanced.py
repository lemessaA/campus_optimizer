# src/services/monitoring_advanced.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time
from typing import Dict, Any
from datetime import datetime, timedelta
import asyncio
from src.services.monitoring import logger
from src.core.config import settings

# Prometheus metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration', ['method', 'endpoint'])
active_connections = Gauge('active_websocket_connections', 'Active WebSocket connections', ['channel'])
agent_execution_time = Histogram('agent_execution_seconds', 'Agent execution time', ['agent_name'])
ticket_count = Counter('support_tickets_total', 'Total support tickets', ['category', 'priority'])
energy_savings = Gauge('energy_savings_kwh', 'Energy savings in kWh', ['building'])
equipment_status = Gauge('equipment_status', 'Equipment status', ['equipment_id', 'status'])

class MonitoringService:
    """Advanced monitoring and alerting service"""
    
    def __init__(self):
        self.alert_thresholds = {
            "high_error_rate": {"threshold": 0.05, "window": 300},  # 5% errors in 5 minutes
            "high_response_time": {"threshold": 2.0, "window": 300},  # >2s average
            "low_disk_space": {"threshold": 0.1, "window": 0},  # <10% free
            "agent_failures": {"threshold": 3, "window": 3600},  # 3 failures per hour
            "urgent_tickets": {"threshold": 5, "window": 3600},  # 5 urgent tickets per hour
        }
        
        self.alert_webhooks = [
            "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
            "https://api.pagerduty.com/v2/triggers"  # For critical alerts
        ]
        
        self.alert_history = []
    
    async def record_request(self, method: str, endpoint: str, status: int, duration: float):
        """Record HTTP request metrics"""
        request_count.labels(method=method, endpoint=endpoint, status=status).inc()
        request_duration.labels(method=method, endpoint=endpoint).observe(duration)
        
        # Check for alerts
        await self.check_error_rate(endpoint)
        await self.check_response_time(endpoint)
    
    async def record_agent_execution(self, agent_name: str, duration: float, success: bool):
        """Record agent execution metrics"""
        agent_execution_time.labels(agent_name=agent_name).observe(duration)
        
        if not success:
            await self.check_agent_failures(agent_name)
    
    async def record_ticket(self, category: str, priority: int):
        """Record support ticket metrics"""
        priority_str = {1: "low", 2: "medium", 3: "high", 4: "urgent"}.get(priority, "unknown")
        ticket_count.labels(category=category, priority=priority_str).inc()
        
        if priority == 4:  # Urgent
            await self.check_urgent_tickets()
    
    async def check_error_rate(self, endpoint: str):
        """Check if error rate is too high"""
        # Query recent metrics
        # This would query Prometheus in production
        error_rate = 0.02  # Mock value
        
        if error_rate > self.alert_thresholds["high_error_rate"]["threshold"]:
            await self.send_alert(
                level="warning",
                title=f"High error rate on {endpoint}",
                message=f"Error rate: {error_rate:.1%}",
                metric="error_rate",
                value=error_rate
            )
    
    async def check_response_time(self, endpoint: str):
        """Check if response time is too high"""
        avg_response = 1.5  # Mock value
        
        if avg_response > self.alert_thresholds["high_response_time"]["threshold"]:
            await self.send_alert(
                level="warning",
                title=f"High response time on {endpoint}",
                message=f"Average: {avg_response:.2f}s",
                metric="response_time",
                value=avg_response
            )
    
    async def check_agent_failures(self, agent_name: str):
        """Check for excessive agent failures"""
        failures = 2  # Mock value
        
        if failures >= self.alert_thresholds["agent_failures"]["threshold"]:
            await self.send_alert(
                level="critical" if failures > 5 else "warning",
                title=f"Agent {agent_name} failing",
                message=f"{failures} failures in the last hour",
                metric="agent_failures",
                value=failures,
                agent=agent_name
            )
    
    async def check_urgent_tickets(self):
        """Check for too many urgent tickets"""
        urgent_count = 3  # Mock value
        
        if urgent_count >= self.alert_thresholds["urgent_tickets"]["threshold"]:
            await self.send_alert(
                level="warning",
                title="High volume of urgent tickets",
                message=f"{urgent_count} urgent tickets in last hour",
                metric="urgent_tickets",
                value=urgent_count
            )
    
    async def send_alert(self, level: str, title: str, message: str, **kwargs):
        """Send alert to configured channels"""
        alert = {
            "id": str(uuid.uuid4()),
            "level": level,
            "title": title,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "data": kwargs
        }
        
        # Store in history
        self.alert_history.append(alert)
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        # Log alert
        log_func = logger.warning if level == "warning" else logger.error
        log_func(f"ALERT [{level.upper()}]: {title} - {message}")
        
        # Send to Slack for all alerts
        await self.send_slack_alert(alert)
        
        # Send to PagerDuty for critical alerts
        if level == "critical":
            await self.send_pagerduty_alert(alert)
    
    async def send_slack_alert(self, alert: Dict):
        """Send alert to Slack"""
        color = {
            "warning": "#FFA500",
            "critical": "#FF0000",
            "info": "#0000FF"
        }.get(alert["level"], "#808080")
        
        payload = {
            "attachments": [{
                "color": color,
                "title": alert["title"],
                "text": alert["message"],
                "fields": [
                    {"title": "Level", "value": alert["level"].upper(), "short": True},
                    {"title": "Time", "value": alert["timestamp"], "short": True}
                ],
                "footer": "Campus Operations Monitor"
            }]
        }
        
        # Add additional fields
        for key, value in alert["data"].items():
            payload["attachments"][0]["fields"].append({
                "title": key.replace("_", " ").title(),
                "value": str(value),
                "short": True
            })
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.alert_webhooks[0],
                    json=payload,
                    timeout=5
                )
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    async def send_pagerduty_alert(self, alert: Dict):
        """Send critical alert to PagerDuty"""
        payload = {
            "routing_key": settings.PAGERDUTY_KEY,
            "event_action": "trigger",
            "payload": {
                "summary": alert["title"],
                "source": "campus-optimizer",
                "severity": alert["level"],
                "timestamp": alert["timestamp"],
                "custom_details": alert["data"]
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(
                    self.alert_webhooks[1],
                    json=payload,
                    timeout=5
                )
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alert: {e}")
    
    async def health_check_advanced(self) -> Dict:
        """Advanced health check with detailed metrics"""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "total_requests": request_count._value.get(),
                "active_connections": active_connections._value.get(),
                "error_rate": await self.calculate_error_rate(),
                "avg_response_time": await self.calculate_avg_response_time()
            },
            "alerts": {
                "recent": self.alert_history[-10:],
                "total": len(self.alert_history)
            },
            "resources": {
                "disk_usage": await self.check_disk_usage(),
                "memory_usage": await self.check_memory_usage(),
                "database_connections": await self.check_db_connections()
            }
        }
    
    async def calculate_error_rate(self) -> float:
        """Calculate current error rate"""
        # Mock implementation
        return 0.01
    
    async def calculate_avg_response_time(self) -> float:
        """Calculate average response time"""
        # Mock implementation
        return 0.235
    
    async def check_disk_usage(self) -> Dict:
        """Check disk usage"""
        import shutil
        usage = shutil.disk_usage("/")
        return {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent_used": (usage.used / usage.total) * 100
        }
    
    async def check_memory_usage(self) -> Dict:
        """Check memory usage"""
        import psutil
        memory = psutil.virtual_memory()
        return {
            "total": memory.total,
            "available": memory.available,
            "percent_used": memory.percent
        }
    
    async def check_db_connections(self) -> int:
        """Check database connection count"""
        async with get_db() as db:
            result = await db.execute("SELECT count(*) FROM pg_stat_activity")
            return result.scalar()