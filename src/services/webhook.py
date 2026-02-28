# src/services/webhook.py
from typing import Dict, Any, List, Optional
from datetime import datetime
import aiohttp
import asyncio
import hmac
import hashlib
import json
from src.database import crud
from src.services.monitoring import logger

class WebhookService:
    """Webhook service for external integrations"""
    
    def __init__(self):
        self.webhook_endpoints = {
            "lms": {
                "url": "https://lms.campus.edu/api/webhook",
                "events": ["course_created", "schedule_updated"],
                "secret": "lms_webhook_secret"
            },
            "building_management": {
                "url": "https://bms.campus.edu/api/events",
                "events": ["energy_optimization", "classroom_empty"],
                "secret": "bms_webhook_secret"
            },
            "notification": {
                "url": "https://notify.campus.edu/send",
                "events": ["notification_sent", "urgent_ticket"],
                "secret": "notify_webhook_secret"
            },
            "slack": {
                "url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXX",
                "events": ["urgent_ticket", "equipment_maintenance_needed"],
                "secret": None  # No signature for Slack
            }
        }
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Initialize HTTP session"""
        self.session = aiohttp.ClientSession()
    
    async def stop(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()
    
    def _generate_signature(self, payload: Dict, secret: str) -> str:
        """Generate HMAC signature for webhook"""
        if not secret:
            return None
        
        message = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            secret.encode(),
            message,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def send_webhook(self, endpoint_name: str, event_type: str, payload: Dict):
        """Send webhook to external system"""
        endpoint = self.webhook_endpoints.get(endpoint_name)
        
        if not endpoint:
            logger.warning(f"Unknown webhook endpoint: {endpoint_name}")
            return
        
        if event_type not in endpoint["events"]:
            return  # Event not subscribed
        
        webhook_payload = {
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "CampusOptimizer/1.0"
        }
        
        # Add signature if secret exists
        if endpoint.get("secret"):
            signature = self._generate_signature(webhook_payload, endpoint["secret"])
            headers["X-Webhook-Signature"] = signature
        
        try:
            async with self.session.post(
                endpoint["url"],
                json=webhook_payload,
                headers=headers,
                timeout=5
            ) as response:
                if response.status in [200, 201, 202]:
                    logger.info(f"Webhook sent to {endpoint_name}: {event_type}")
                    
                    # Log webhook delivery
                    async with get_db() as db:
                        await crud.log_webhook_delivery(
                            db,
                            endpoint=endpoint_name,
                            event=event_type,
                            status="success",
                            response_code=response.status
                        )
                else:
                    logger.error(f"Webhook failed: {endpoint_name} - {response.status}")
                    
                    # Log failure
                    async with get_db() as db:
                        await crud.log_webhook_delivery(
                            db,
                            endpoint=endpoint_name,
                            event=event_type,
                            status="failed",
                            response_code=response.status
                        )
                    
                    # Retry logic for failed webhooks
                    await self.schedule_retry(endpoint_name, event_type, payload)
        
        except Exception as e:
            logger.error(f"Webhook error for {endpoint_name}: {str(e)}")
            
            # Log exception
            async with get_db() as db:
                await crud.log_webhook_delivery(
                    db,
                    endpoint=endpoint_name,
                    event=event_type,
                    status="error",
                    error=str(e)
                )
            
            # Schedule retry
            await self.schedule_retry(endpoint_name, event_type, payload)
    
    async def schedule_retry(self, endpoint_name: str, event_type: str, payload: Dict, attempt: int = 1):
        """Schedule webhook retry with exponential backoff"""
        if attempt > 3:
            logger.error(f"Max retries exceeded for {endpoint_name}: {event_type}")
            return
        
        # Calculate backoff: 2^attempt * 60 seconds
        delay = (2 ** attempt) * 60
        
        await asyncio.sleep(delay)
        
        # Retry
        await self.send_webhook(endpoint_name, event_type, payload)
    
    async def register_webhook(self, endpoint_name: str, url: str, events: List[str], secret: Optional[str] = None):
        """Register a new webhook endpoint"""
        self.webhook_endpoints[endpoint_name] = {
            "url": url,
            "events": events,
            "secret": secret
        }
        
        # Store in database
        async with get_db() as db:
            await crud.register_webhook(db, endpoint_name, url, events, secret)
        
        logger.info(f"Registered webhook endpoint: {endpoint_name}")