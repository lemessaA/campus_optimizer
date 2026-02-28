# src/agents/scheduling_agent.py
from typing import Dict, Any, List
from datetime import datetime, time
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.core.exceptions import SchedulingError
from src.services.monitoring import logger

class SchedulingAgent(BaseAgent):
    """Agent responsible for optimal classroom allocation"""
    
    def __init__(self):
        super().__init__("scheduling_agent", "scheduling")
    
    def setup_tools(self):
        # Add any LangChain tools if needed
        pass
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process scheduling requests"""
        event_type = input_data.get("event_type")
        
        if event_type == "course_created":
            return await self.allocate_classroom(input_data)
        elif event_type == "timetable_updated":
            return await self.reoptimize_schedule(input_data)
        else:
            return self.get_fallback_response(input_data)
    
    async def allocate_classroom(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Allocate optimal classroom for a course"""
        try:
            course = data.get("course", {})
            students_count = course.get("students_count", 0)
            preferred_building = course.get("preferred_building")
            schedule_time = course.get("schedule_time")
            
            async with get_db() as db:
                # Get all available classrooms with sufficient capacity
                available_rooms = await crud.get_available_classrooms(
                    db, 
                    min_capacity=students_count,
                    building=preferred_building
                )
                
                if not available_rooms:
                    # Try without building constraint
                    available_rooms = await crud.get_available_classrooms(
                        db, min_capacity=students_count
                    )
                
                if not available_rooms:
                    # Check if any room can be adjusted (slightly larger classes)
                    available_rooms = await crud.get_available_classrooms(
                        db, min_capacity=students_count * 0.8
                    )
                    
                    if available_rooms:
                        logger.warning(f"Using slightly smaller room for course {course.get('name')}")
                
                if not available_rooms:
                    raise SchedulingError("No suitable classrooms available")
                
                # Select optimal room (smallest that fits to save energy)
                optimal_room = min(available_rooms, key=lambda r: r.capacity)
                
                # Create booking
                booking = await crud.create_classroom_booking(
                    db,
                    classroom_id=optimal_room.id,
                    course_id=course.get("id"),
                    time_slot=schedule_time
                )
                
                return {
                    "status": "success",
                    "data": {
                        "classroom": optimal_room.dict(),
                        "booking_id": booking.id,
                        "utilization_rate": students_count / optimal_room.capacity
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Scheduling allocation failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "fallback_used": True,
                "data": {
                    "classroom": None,
                    "message": "Using heuristic allocation: First available room"
                }
            }
    
    async def reoptimize_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Reoptimize entire schedule if needed"""
        # Implementation for bulk reoptimization
        pass