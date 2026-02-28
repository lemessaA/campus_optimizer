# src/agents/notification_agent.py
from typing import Dict, Any, List
from datetime import datetime
from src.agents.base_agent import BaseAgent
from src.services.monitoring import logger

class NotificationAgent(BaseAgent):
    """Agent responsible for user notifications and alerts"""
    
    def __init__(self):
        super().__init__("notification_agent", "notification")
        self.notification_queue = []
    
    def setup_tools(self):
        pass
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and send notifications"""
        try:
            notification_type = input_data.get("notification_type")
            recipient = input_data.get("recipient", "dashboard")
            message = input_data.get("message", {})
            
            # Log notification
            notification = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": notification_type,
                "recipient": recipient,
                "message": message,
                "status": "sent"
            }
            
            self.notification_queue.append(notification)
            
            # In production, this would send emails, push notifications, etc.
            logger.info(f"Notification sent: {notification_type}", 
                       extra={"recipient": recipient})
            
            # For UI, we'll store in cache for dashboard retrieval
            await self.store_for_dashboard(notification)
            
            return {
                "status": "success",
                "data": {
                    "notification_id": len(self.notification_queue),
                    "sent_at": notification["timestamp"]
                },
                "fallback_used": False
            }
            
        except Exception as e:
            logger.error(f"Notification failed: {str(e)}")
            return self.get_fallback_response(input_data)
    
    async def store_for_dashboard(self, notification: Dict[str, Any]):
        """Store notification for dashboard retrieval"""
        # In production, this would use Redis pub/sub
        from src.services.cache import redis_client
        
        await redis_client.lpush(
            "dashboard:notifications",
            str(notification)
        )
        await redis_client.ltrim("dashboard:notifications", 0, 99)  # Keep last 100
    
    async def get_dashboard_notifications(self, limit: int = 20) -> List[Dict]:
        """Get recent notifications for dashboard"""
        from src.services.cache import redis_client
        
        notifications = await redis_client.lrange("dashboard:notifications", 0, limit-1)
        return [eval(n) for n in notifications] if notifications else []