# src/agents/support_agent.py
from typing import Dict, Any, List, Optional, cast
from datetime import datetime, timedelta
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.services.cache import redis_client
from src.services.monitoring import logger
from src.services.llm_service import LLMService
import json
import re
import hashlib

class SupportAgent(BaseAgent):
    """Agent responsible for customer support and user assistance"""
    
    def __init__(self):
        super().__init__("support_agent", "support")
        self.support_categories = {
            "scheduling": ["classroom", "course", "timetable", "schedule"],
            "equipment": ["book", "equipment", "lab", "device", "microscope"],
            "facilities": ["maintenance", "clean", "repair", "broken"],
            "energy": ["power", "light", "hvac", "temperature"],
            "account": ["login", "password", "access", "permission"]
        }
        
        self.faq_database = self._initialize_faq()
        self.llm_service = LLMService()
        self._faq_index_hash: Optional[str] = None
        self.ticket_priority_levels = {"low": 1, "medium": 2, "high": 3, "urgent": 4}
    
    def setup_tools(self):
        """Initialize support-specific tools"""
        # Tools would be added here for LangChain integration
        pass
    
    def _initialize_faq(self) -> Dict[str, Any]:
        """Initialize FAQ database"""
        return {}


    async def _load_faqs_from_cache(self) -> Dict[str, Any]:
        try:
            if not redis_client:
                return {}
            raw = await redis_client.get("support:faqs")
            if not raw:
                return {}

            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode("utf-8")

            data = json.loads(raw)
            if isinstance(data, list):
                return {
                    str(item.get("id")): {
                        "question": item.get("question"),
                        "answer": item.get("answer"),
                        "category": item.get("category"),
                    }
                    for item in data
                    if item.get("id")
                }
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}


    async def _ensure_faqs_indexed(self, faqs_raw: str, faqs: Dict[str, Any]) -> None:
        try:
            if not faqs_raw:
                return
            if self.llm_service is None or getattr(self.llm_service, "vector_store", None) is None:
                return

            digest = hashlib.sha256(faqs_raw.encode("utf-8")).hexdigest()
            if self._faq_index_hash == digest:
                return

            faq_list = []
            for faq_id, faq in faqs.items():
                faq_list.append(
                    {
                        "id": str(faq_id),
                        "question": faq.get("question"),
                        "answer": faq.get("answer"),
                        "category": faq.get("category"),
                    }
                )

            await self.llm_service.initialize_faq_store(faq_list)
            self._faq_index_hash = digest
        except Exception:
            return
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process support requests"""
        request_type = input_data.get("request_type")
        
        if request_type == "faq_query":
            return await self.handle_faq_query(input_data)
        elif request_type == "create_ticket":
            return await self.create_support_ticket(input_data)
        elif request_type == "check_status":
            return await self.check_ticket_status(input_data)
        elif request_type == "escalate":
            return await self.escalate_ticket(input_data)
        elif request_type == "get_suggestions":
            return await self.get_contextual_suggestions(input_data)
        else:
            return self.get_fallback_response(input_data)
    
    async def handle_faq_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle FAQ queries with intelligent matching"""
        try:
            faqs_raw = ""
            if redis_client is not None and hasattr(redis_client, "get"):
                raw = await redis_client.get("support:faqs")
                if raw:
                    if isinstance(raw, (bytes, bytearray)):
                        raw = raw.decode("utf-8")
                    faqs_raw = str(raw)

            self.faq_database = await self._load_faqs_from_cache()
            try:
                await self._ensure_faqs_indexed(faqs_raw, self.faq_database)
            except Exception:
                pass
            query = data.get("query", "").lower()
            user_id = data.get("user_id")
            
            # Log the query for analytics
            await self.log_query(query, user_id)
            
            # Try exact match first
            for faq_id, faq in self.faq_database.items():
                if faq["question"].lower() in query or query in faq["question"].lower():
                    return {
                        "status": "success",
                        "data": {
                            "answer": faq["answer"],
                            "category": faq["category"],
                            "exact_match": True
                        },
                        "fallback_used": False
                    }
            
            # Try keyword matching
            matched_category = None
            best_match_score = 0
            best_match_answer = None
            
            for category, keywords in self.support_categories.items():
                score = sum(1 for keyword in keywords if keyword in query)
                if score > best_match_score:
                    best_match_score = score
                    matched_category = category
            
            if best_match_score > 0:
                # Find relevant FAQ in that category
                for faq_id, faq in self.faq_database.items():
                    if faq["category"] == matched_category:
                        best_match_answer = faq["answer"]
                        break
            
            if best_match_answer:
                return {
                    "status": "success",
                    "data": {
                        "answer": best_match_answer,
                        "category": matched_category,
                        "exact_match": False,
                        "confidence": best_match_score / 5  # Normalize score
                    },
                    "fallback_used": False
                }

            if self.llm_service is not None:
                try:
                    llm_resp = await self.llm_service.generate_response(
                        user_id=str(user_id or "anonymous"),
                        query=data.get("query", ""),
                    )

                    answer_text = llm_resp.get("answer")
                    if answer_text and answer_text != "LLM is not configured.":
                        return {
                            "status": "success",
                            "data": {
                                "answer": answer_text,
                                "category": "general",
                                "exact_match": False,
                                "confidence": llm_resp.get("sentiment", {}).get("score", 0.0),
                                "source_documents": llm_resp.get("source_documents", []),
                            },
                            "fallback_used": False,
                        }
                except Exception:
                    pass
            
            # No match found - create a ticket suggestion
            return {
                "status": "no_match",
                "data": {
                    "message": "I couldn't find an exact answer. Would you like to create a support ticket?",
                    "suggested_ticket": {
                        "category": self._suggest_category(query),
                        "description": query
                    }
                },
                "fallback_used": False
            }
            
        except Exception as e:
            logger.error(f"FAQ handling failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def create_support_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new support ticket with intelligent routing"""
        try:
            user_id = data.get("user_id")
            category = data.get("category")
            description = data.get("description")

            if not user_id or not category or not description:
                return {
                    "status": "error",
                    "error": "user_id, category, and description are required",
                    "fallback_used": False,
                }

            user_id_str = str(user_id)
            category_str = str(category)
            description_str = str(description)

            priority = self._determine_priority(description_str)
            
            # Get context from other agents
            context = await self._gather_context(user_id_str, category_str)
            
            async with get_db() as db:
                ticket = await crud.create_support_ticket(
                    db,
                    user_id=user_id_str,
                    category=category_str,
                    description=description_str,
                    priority=priority,
                    context=context
                )
                
                # If urgent, notify appropriate agents
                if priority >= 3:  # High or urgent
                    await self._notify_agents(ticket, category_str)
                
                # Store in cache for quick access
                if redis_client is not None and hasattr(redis_client, "setex"):
                    await redis_client.setex(
                        f"ticket:{ticket.id}",
                        3600,
                        json.dumps({
                            "id": ticket.id,
                            "status": "open",
                            "priority": priority
                        })
                    )
                
                # Get estimated resolution time
                eta = self._estimate_resolution_time(priority, category)
                
                return {
                    "status": "success",
                    "data": {
                        "ticket_id": ticket.id,
                        "priority": priority,
                        "estimated_resolution": eta,
                        "next_steps": self._get_next_steps(category, priority)
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Ticket creation failed: {str(e)}")
            return self.get_fallback_response(data)
    
    def _determine_priority(self, description: str) -> int:
        """Determine ticket priority based on content"""
        urgent_keywords = ["emergency", "urgent", "broken", "not working", "cannot access", "deadline"]
        high_keywords = ["important", "asap", "soon", "critical"]
        medium_keywords = ["help", "question", "issue", "problem"]
        
        desc_lower = description.lower()
        
        if any(keyword in desc_lower for keyword in urgent_keywords):
            return 4  # Urgent
        elif any(keyword in desc_lower for keyword in high_keywords):
            return 3  # High
        elif any(keyword in desc_lower for keyword in medium_keywords):
            return 2  # Medium
        else:
            return 1  # Low
    
    async def _gather_context(self, user_id: str, category: str) -> Dict[str, Any]:
        """Gather relevant context from other agents"""
        context = {}
        
        async with get_db() as db:
            # Get user's recent activities
            if category == "equipment":
                recent_bookings = await crud.get_user_recent_bookings(db, user_id, days=7)
                context["recent_equipment"] = [
                    {"id": b.equipment_id, "date": b.start_time.isoformat()}
                    for b in recent_bookings
                ]
            elif category == "scheduling":
                courses = await crud.get_user_courses(db, user_id)
                context["enrolled_courses"] = [c.name for c in courses]
            
            # Get any open tickets
            open_tickets = await crud.get_user_open_tickets(db, user_id)
            context["open_tickets"] = len(open_tickets)
        
        return context
    
    async def _notify_agents(self, ticket: Any, category: str):
        """Notify relevant agents about urgent tickets"""
        # Publish to Redis channel for real-time notification
        if redis_client is not None and hasattr(redis_client, "publish"):
            await redis_client.publish(
                "urgent_tickets",
                json.dumps({
                    "ticket_id": ticket.id,
                    "category": category,
                    "priority": ticket.priority,
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
        
        # In production, this could trigger SMS/email
        logger.warning(f"URGENT TICKET #{ticket.id}: {category} - Priority {ticket.priority}")
    
    def _estimate_resolution_time(self, priority: int, category: str) -> str:
        """Estimate resolution time based on priority and category"""
        if priority == 4:  # Urgent
            return "1-2 hours"
        elif priority == 3:  # High
            return "4-8 hours"
        elif priority == 2:  # Medium
            return "24 hours"
        else:  # Low
            return "2-3 business days"
    
    def _get_next_steps(self, category: str, priority: int) -> List[str]:
        """Get next steps based on ticket details"""
        steps = ["You will receive email confirmation"]
        
        if priority >= 3:
            steps.append("A support representative will contact you shortly")
        
        if category == "equipment":
            steps.append("Please do not attempt to repair equipment yourself")
        elif category == "facilities":
            steps.append("Maintenance team will be notified")
        
        return steps
    
    async def check_ticket_status(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check status of existing ticket"""
        try:
            ticket_id = data.get("ticket_id")

            if ticket_id is None:
                return {
                    "status": "error",
                    "error": "ticket_id is required",
                    "fallback_used": False,
                }
            
            # Check cache first
            ticket_id_int = int(ticket_id)

            if redis_client is not None and hasattr(redis_client, "get"):
                cached = await redis_client.get(f"ticket:{ticket_id_int}")
                if cached:
                    if isinstance(cached, (bytes, bytearray)):
                        cached = cached.decode("utf-8")
                    return {
                        "status": "success",
                        "data": json.loads(cached),
                        "fallback_used": False,
                        "cached": True
                    }
            
            async with get_db() as db:
                ticket = await crud.get_ticket(db, ticket_id_int)
                
                if not ticket:
                    return {
                        "status": "error",
                        "error": "Ticket not found",
                        "fallback_used": False
                    }
                
                # Get assignment info
                assigned_agent = await self._get_assigned_agent(ticket)
                
                response = {
                    "ticket_id": ticket.id,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "created_at": ticket.created_at.isoformat(),
                    "last_updated": ticket.updated_at.isoformat(),
                    "assigned_to": assigned_agent,
                    "updates": await self._get_ticket_updates(ticket_id_int)
                }
                
                # Cache the result
                if redis_client is not None and hasattr(redis_client, "setex"):
                    await redis_client.setex(
                        f"ticket:{ticket_id_int}",
                        300,  # 5 minutes cache
                        json.dumps(response)
                    )
                
                return {
                    "status": "success",
                    "data": response,
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Status check failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def _get_assigned_agent(self, ticket: Any) -> str:
        """Get the agent assigned to this ticket"""
        # In production, this would map categories to support teams
        assignment_map = {
            "scheduling": "Academic Support",
            "equipment": "Lab Operations",
            "facilities": "Facilities Management",
            "energy": "Energy Team",
            "account": "IT Support"
        }
        
        return assignment_map.get(ticket.category, "General Support")
    
    async def _get_ticket_updates(self, ticket_id: int) -> List[Dict]:
        """Get update history for ticket"""
        async with get_db() as db:
            updates = await crud.get_ticket_updates(db, ticket_id)
            return [
                {
                    "timestamp": u.created_at.isoformat(),
                    "message": u.message,
                    "type": u.update_type
                }
                for u in updates
            ]
    
    async def escalate_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Escalate a ticket to higher support"""
        try:
            ticket_id = data.get("ticket_id")
            reason = data.get("reason")

            if ticket_id is None or not reason:
                return {
                    "status": "error",
                    "error": "ticket_id and reason are required",
                    "fallback_used": False,
                }
            
            ticket_id_int = int(ticket_id)

            async with get_db() as db:
                ticket = await crud.get_ticket(db, ticket_id_int)
                
                if not ticket:
                    return {
                        "status": "error",
                        "error": "Ticket not found",
                        "fallback_used": False
                    }
                
                # Increase priority
                current_priority = int(cast(int, ticket.priority) or 1)
                new_priority = min(current_priority + 1, 4)
                await crud.update_ticket_priority(db, ticket_id_int, new_priority)
                
                # Notify supervisor
                await crud.create_ticket_update(
                    db,
                    ticket_id=ticket_id_int,
                    message=f"Ticket escalated: {reason}",
                    update_type="escalation"
                )
                
                # Clear cache
                if redis_client is not None and hasattr(redis_client, "delete"):
                    await redis_client.delete(f"ticket:{ticket_id_int}")
                
                return {
                    "status": "success",
                    "data": {
                        "ticket_id": ticket_id_int,
                        "new_priority": new_priority,
                        "message": "Ticket has been escalated"
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Escalation failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def get_contextual_suggestions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get contextual suggestions based on user activity"""
        try:
            user_id = data.get("user_id")
            current_page = data.get("current_page", "")

            if not user_id:
                return {
                    "status": "error",
                    "error": "user_id is required",
                    "fallback_used": False,
                }

            user_id_str = str(user_id)
            
            async with get_db() as db:
                # Get user's recent activity
                recent_bookings = await crud.get_user_recent_bookings(db, user_id_str, days=3)
                open_tickets = await crud.get_user_open_tickets(db, user_id_str)
                
                suggestions = []
                
                # Suggest based on current page
                if "equipment" in current_page and recent_bookings:
                    suggestions.append({
                        "type": "reminder",
                        "message": "You have equipment booked for tomorrow",
                        "action": "View booking"
                    })
                
                if "schedule" in current_page:
                    # Check for scheduling conflicts
                    conflicts = await self._check_scheduling_conflicts(db, user_id_str)
                    if conflicts:
                        suggestions.extend(conflicts)
                
                # Follow up on open tickets
                for ticket in open_tickets[:2]:
                    days_open = (datetime.utcnow() - ticket.created_at).days
                    if days_open > 2:
                        suggestions.append({
                            "type": "follow_up",
                            "message": f"Your ticket #{ticket.id} has been open for {days_open} days",
                            "action": "Check status"
                        })
                
                return {
                    "status": "success",
                    "data": {
                        "suggestions": suggestions,
                        "count": len(suggestions)
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Suggestions failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def _check_scheduling_conflicts(self, db, user_id: str) -> List[Dict]:
        """Check for scheduling conflicts"""
        # Implementation would check user's schedule
        return []
    
    def _suggest_category(self, query: str) -> str:
        """Suggest category based on query keywords"""
        for category, keywords in self.support_categories.items():
            if any(keyword in query for keyword in keywords):
                return category
        return "general"
    
    async def log_query(self, query: str, user_id: Optional[str]):
        """Log queries for analytics"""
        # In production, store in analytics database
        logger.info(f"Support query: {query[:50]}...", extra={"user": user_id})