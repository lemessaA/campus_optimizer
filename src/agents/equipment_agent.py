# src/agents/equipment_agent.py
from typing import Dict, Any
from datetime import datetime, timedelta
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.services.monitoring import logger
from src.services.llm_service import LLMService

class EquipmentAgent(BaseAgent):
    """Agent responsible for equipment management and booking"""
    
    def __init__(self):
        super().__init__("equipment_agent", "equipment")
        self.llm_service = LLMService()
    
    def setup_tools(self):
        pass
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process equipment booking requests"""
        event_type = input_data.get("event_type")
        
        if event_type == "equipment_booking":
            return await self.handle_booking(input_data)
        elif event_type == "maintenance_check":
            return await self.check_maintenance(input_data)
        else:
            return self.get_fallback_response(input_data)
    
    async def handle_booking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Intelligent equipment booking with conflict resolution"""
        try:
            booking = data.get("booking", {})
            equipment_id = booking.get("equipment_id")
            user_id = booking.get("user_id")
            time_slot = datetime.fromisoformat(booking.get("time_slot"))
            duration = booking.get("duration_hours", 1)
            
            async with get_db() as db:
                # Check equipment availability
                equipment = await crud.get_equipment(db, equipment_id)
                
                if not equipment:
                    return {
                        "status": "error",
                        "error": "Equipment not found",
                        "fallback_used": False
                    }
                
                if equipment.status != "available":
                    return {
                        "status": "error",
                        "error": f"Equipment is {equipment.status}",
                        "fallback_used": False
                    }
                
                # Check for conflicts
                end_time = time_slot + timedelta(hours=duration)
                conflicts = await crud.check_equipment_conflicts(
                    db, equipment_id, time_slot, end_time
                )
                
                if conflicts:
                    # Try to suggest alternative times
                    alternative = await self.suggest_alternative_slot(
                        db, equipment_id, time_slot, duration
                    )
                    
                    return {
                        "status": "conflict",
                        "data": {
                            "message": "Time slot not available",
                            "suggested_alternatives": alternative
                        },
                        "fallback_used": False
                    }
                
                # Predict maintenance needs
                needs_maintenance = await self.predict_maintenance(
                    db, equipment, time_slot
                )
                
                if needs_maintenance:
                    logger.info(f"Equipment {equipment_id} may need maintenance soon")
                
                # Create booking
                booking_result = await crud.create_equipment_booking(
                    db,
                    equipment_id=equipment_id,
                    user_id=user_id,
                    start_time=time_slot,
                    end_time=end_time
                )
                
                return {
                    "status": "success",
                    "data": {
                        "booking_id": booking_result.id,
                        "equipment": equipment.name,
                        "maintenance_advisory": needs_maintenance
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Equipment booking failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def suggest_alternative_slot(self, db, equipment_id, requested_time, duration):
        """Suggest alternative time slots if requested is unavailable"""
        alternatives = []
        for offset in [1, 2, 3, -1, -2]:  # Try adjacent time slots
            test_time = requested_time + timedelta(hours=offset)
            end_time = test_time + timedelta(hours=duration)
            
            conflicts = await crud.check_equipment_conflicts(
                db, equipment_id, test_time, end_time
            )
            
            if not conflicts:
                alternatives.append(test_time.isoformat())
                if len(alternatives) >= 3:
                    break
        
        return alternatives
    
    async def predict_maintenance(self, db, equipment, booking_time):
        """Predict if equipment will need maintenance soon"""
        if not equipment.last_maintenance:
            return False
        
        days_since_maintenance = (booking_time - equipment.last_maintenance).days
        
        # Get usage frequency
        usage_count = await crud.get_equipment_usage_count(
            db, equipment.id, days=30
        )
        
        # Simple prediction logic
        if days_since_maintenance > 180:  # 6 months
            return True
        if days_since_maintenance > 90 and usage_count > 50:
            return True
        
        return False
    
    async def check_maintenance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Check and predict maintenance needs"""
        # Implementation for bulk maintenance checking
        pass