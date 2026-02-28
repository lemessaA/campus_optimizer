# src/services/websocket.py
from fastapi import WebSocket, WebSocketDisconnect, Depends
from typing import Dict, Set, Any
import json
import asyncio
from datetime import datetime
from src.core.security import AuthService, get_current_user
from src.services.monitoring import logger

class ConnectionManager:
    """WebSocket connection manager"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "dashboard": set(),
            "support": set(),
            "admin": set()
        }
        self.user_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, channel: str, user_id: str = None):
        """Accept and store connection"""
        await websocket.accept()
        
        if channel in self.active_connections:
            self.active_connections[channel].add(websocket)
        
        if user_id:
            self.user_connections[user_id] = websocket
        
        logger.info(f"WebSocket connected: channel={channel}, user={user_id}")
    
    def disconnect(self, websocket: WebSocket, channel: str, user_id: str = None):
        """Remove disconnected client"""
        if channel in self.active_connections:
            self.active_connections[channel].discard(websocket)
        
        if user_id and user_id in self.user_connections:
            del self.user_connections[user_id]
        
        logger.info(f"WebSocket disconnected: channel={channel}, user={user_id}")
    
    async def broadcast(self, channel: str, message: Dict[str, Any]):
        """Broadcast message to all connections in channel"""
        if channel not in self.active_connections:
            return
        
        disconnected = set()
        
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except:
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            self.active_connections[channel].discard(connection)
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]):
        """Send message to specific user"""
        if user_id in self.user_connections:
            try:
                await self.user_connections[user_id].send_json(message)
            except:
                del self.user_connections[user_id]
    
    async def subscribe(self, user_id: str, topic: str):
        """Subscribe user to topic"""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = set()
        self.subscriptions[topic].add(user_id)
    
    async def unsubscribe(self, user_id: str, topic: str):
        """Unsubscribe user from topic"""
        if topic in self.subscriptions and user_id in self.subscriptions[topic]:
            self.subscriptions[topic].remove(user_id)
    
    async def publish(self, topic: str, message: Dict[str, Any]):
        """Publish message to all subscribers of topic"""
        if topic not in self.subscriptions:
            return
        
        for user_id in self.subscriptions[topic]:
            await self.send_to_user(user_id, {
                "type": "notification",
                "topic": topic,
                "data": message,
                "timestamp": datetime.utcnow().isoformat()
            })

# Global connection manager
manager = ConnectionManager()

# WebSocket endpoints
async def websocket_dashboard(websocket: WebSocket):
    """Dashboard WebSocket for real-time updates"""
    await manager.connect(websocket, "dashboard")
    
    try:
        while True:
            # Receive heartbeat
            data = await websocket.receive_text()
            
            # Send acknowledgment
            await websocket.send_json({
                "type": "heartbeat_ack",
                "timestamp": datetime.utcnow().isoformat()
            })
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, "dashboard")

async def websocket_support(websocket: WebSocket, token: str = None):
    """Support WebSocket with authentication"""
    # Authenticate user
    if token:
        auth_service = AuthService()
        user = await auth_service.verify_token(token)
        if user:
            await manager.connect(websocket, "support", user.username)
            
            # Send connection confirmation
            await websocket.send_json({
                "type": "connected",
                "channel": "support",
                "user": user.username
            })
            
            try:
                while True:
                    # Receive messages
                    data = await websocket.receive_json()
                    
                    # Handle different message types
                    if data["type"] == "ticket_update":
                        await handle_ticket_update(data, user)
                    elif data["type"] == "chat_message":
                        await handle_chat_message(data, user)
                    elif data["type"] == "subscribe":
                        await manager.subscribe(user.username, data["topic"])
                    
            except WebSocketDisconnect:
                manager.disconnect(websocket, "support", user.username)
        else:
            await websocket.close(code=1008, reason="Authentication failed")
    else:
        await websocket.close(code=1008, reason="Token required")

async def handle_ticket_update(data: Dict, user):
    """Handle ticket update via WebSocket"""
    # Process ticket update
    ticket_id = data["ticket_id"]
    update = data["update"]
    
    # Broadcast to support channel
    await manager.broadcast("support", {
        "type": "ticket_updated",
        "ticket_id": ticket_id,
        "update": update,
        "updated_by": user.username,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Notify ticket owner if different
    if "owner_id" in data and data["owner_id"] != user.username:
        await manager.send_to_user(data["owner_id"], {
            "type": "ticket_notification",
            "ticket_id": ticket_id,
            "message": f"Your ticket has been updated: {update}",
            "timestamp": datetime.utcnow().isoformat()
        })

async def handle_chat_message(data: Dict, user):
    """Handle chat message via WebSocket"""
    # Send to recipient if specified
    if "recipient" in data:
        await manager.send_to_user(data["recipient"], {
            "type": "chat",
            "from": user.username,
            "message": data["message"],
            "timestamp": datetime.utcnow().isoformat()
        })
    else:
        # Broadcast to support channel
        await manager.broadcast("support", {
            "type": "chat",
            "from": user.username,
            "message": data["message"],
            "timestamp": datetime.utcnow().isoformat()
        })