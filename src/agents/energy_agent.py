# src/agents/energy_agent.py
from typing import Dict, Any, List
from datetime import datetime, timedelta
from src.agents.base_agent import BaseAgent
from src.services.database import get_db
from src.database import crud
from src.services.cache import redis_client
from src.services.monitoring import logger

class EnergyAgent(BaseAgent):
    """Agent responsible for energy usage optimization"""
    
    def __init__(self):
        super().__init__("energy_agent", "energy")
        self.energy_saving_threshold = 0.3  # 30% saving target
    
    def setup_tools(self):
        pass
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process energy optimization requests"""
        event_type = input_data.get("event_type")
        
        if event_type == "classroom_empty":
            return await self.optimize_empty_room(input_data)
        elif event_type == "schedule_updated":
            return await self.optimize_building_energy(input_data)
        elif event_type == "energy_optimization":
            return await self.get_energy_insights()
        else:
            return self.get_fallback_response(input_data)
    
    async def optimize_empty_room(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize energy usage for empty classrooms"""
        try:
            classroom_id = data.get("classroom_id")
            building = data.get("building")
            
            async with get_db() as db:
                # Get current energy state
                current_usage = await crud.get_current_energy_usage(db, building)
                
                # Calculate potential savings
                empty_rooms = await crud.get_empty_classrooms(db, building)
                
                savings_actions = []
                total_savings = 0
                
                for room in empty_rooms:
                    # Simulate energy reduction actions
                    actions = [
                        "Reduce HVAC by 50%",
                        "Turn off lights",
                        "Disable non-critical equipment"
                    ]
                    
                    # Calculate estimated savings
                    estimated_saving = 2.5  # kWh per hour
                    total_savings += estimated_saving
                    
                    savings_actions.append({
                        "room": room.name,
                        "actions": actions,
                        "estimated_saving_kwh": estimated_saving
                    })
                
                # Log energy optimization
                await crud.create_energy_log(
                    db,
                    building=building,
                    action="empty_room_optimization",
                    savings_kwh=total_savings,
                    timestamp=datetime.utcnow()
                )
                
                # Cache the optimization result
                await redis_client.setex(
                    f"energy:optimization:{building}",
                    3600,
                    str(total_savings)
                )
                
                return {
                    "status": "success",
                    "data": {
                        "building": building,
                        "optimized_rooms": len(empty_rooms),
                        "actions": savings_actions,
                        "total_savings_kwh": total_savings,
                        "carbon_reduction_kg": total_savings * 0.4  # Approx CO2 per kWh
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Energy optimization failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def optimize_building_energy(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize building-wide energy based on schedule"""
        try:
            building = data.get("building")
            schedule = data.get("schedule", [])
            
            async with get_db() as db:
                # Get building occupancy forecast
                occupancy = await self.predict_occupancy(db, building, schedule)
                
                # Create energy optimization plan
                plan = []
                total_savings = 0
                
                for hour in range(24):
                    time_str = f"{hour:02d}:00"
                    occupants = occupancy.get(time_str, 0)
                    
                    if occupants == 0:
                        # Empty building period
                        plan.append({
                            "time": time_str,
                            "action": "Deep energy saving mode",
                            "hvac": "0%",
                            "lights": "0%",
                            "savings_kwh": 50
                        })
                        total_savings += 50
                    elif occupants < 10:
                        # Low occupancy
                        plan.append({
                            "time": time_str,
                            "action": "Reduced operation",
                            "hvac": "30%",
                            "lights": "20%",
                            "savings_kwh": 35
                        })
                        total_savings += 35
                    else:
                        # Normal operation
                        plan.append({
                            "time": time_str,
                            "action": "Normal operation",
                            "hvac": "100%",
                            "lights": "100%",
                            "savings_kwh": 0
                        })
                
                return {
                    "status": "success",
                    "data": {
                        "building": building,
                        "optimization_plan": plan,
                        "daily_savings_kwh": total_savings,
                        "monthly_savings_kwh": total_savings * 22  # Weekdays
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Building optimization failed: {str(e)}")
            return self.get_fallback_response(data)
    
    async def get_energy_insights(self) -> Dict[str, Any]:
        """Get comprehensive energy insights"""
        try:
            async with get_db() as db:
                # Get recent energy logs
                logs = await crud.get_recent_energy_logs(db, hours=24)
                
                # Calculate statistics
                total_savings = sum(log.savings_kwh for log in logs if log.savings_kwh)
                avg_savings = total_savings / len(logs) if logs else 0
                
                # Predict peak periods
                peak_periods = await self.predict_peak_periods(db)
                
                # Get cached optimizations
                cached_optimizations = []
                keys = await redis_client.keys("energy:optimization:*")
                for key in keys:
                    value = await redis_client.get(key)
                    cached_optimizations.append({key: value})
                
                return {
                    "status": "success",
                    "data": {
                        "total_savings_24h": total_savings,
                        "average_savings_per_action": avg_savings,
                        "peak_periods": peak_periods,
                        "cached_optimizations": cached_optimizations,
                        "recommendations": [
                            "Schedule heavy equipment use during off-peak hours",
                            "Enable power saving mode in empty labs",
                            "Consider upgrading to LED lighting in Building B"
                        ]
                    },
                    "fallback_used": False
                }
                
        except Exception as e:
            logger.error(f"Energy insights failed: {str(e)}")
            return self.get_fallback_response({})
    
    async def predict_occupancy(self, db, building: str, schedule: List) -> Dict[str, int]:
        """Predict building occupancy based on schedule"""
        occupancy = {f"{h:02d}:00": 0 for h in range(24)}
        
        for event in schedule:
            if event.get("building") == building:
                time_str = event.get("time")
                students = event.get("students", 0)
                
                if time_str in occupancy:
                    occupancy[time_str] += students
        
        return occupancy
    
    async def predict_peak_periods(self, db) -> List[Dict]:
        """Predict peak energy consumption periods"""
        # Get historical consumption
        historical = await crud.get_historical_energy(db, days=30)
        
        # Simple peak prediction based on historical averages
        peak_periods = []
        hourly_avg = {}
        
        for log in historical:
            hour = log.timestamp.hour
            if hour not in hourly_avg:
                hourly_avg[hour] = []
            hourly_avg[hour].append(log.consumption)
        
        for hour, consumptions in hourly_avg.items():
            avg = sum(consumptions) / len(consumptions)
            if avg > 100:  # Threshold for peak
                peak_periods.append({
                    "hour": f"{hour:02d}:00",
                    "average_consumption": avg,
                    "peak_likelihood": "high"
                })
        
        return peak_periods