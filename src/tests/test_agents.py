# src/tests/test_agents.py
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from src.agents.scheduling_agent import SchedulingAgent
from src.agents.equipment_agent import EquipmentAgent
from src.agents.energy_agent import EnergyAgent

@pytest.mark.asyncio
async def test_scheduling_agent_success():
    """Test successful classroom allocation"""
    agent = SchedulingAgent()
    
    input_data = {
        "event_type": "course_created",
        "course": {
            "name": "CS101",
            "students_count": 50,
            "schedule_time": "10:00",
            "preferred_building": "Engineering"
        }
    }
    
    with patch('src.database.crud.get_available_classrooms') as mock_get:
        mock_get.return_value = [
            Mock(id=1, name="Room 101", capacity=60, building="Engineering")
        ]
        
        with patch('src.database.crud.create_classroom_booking') as mock_create:
            mock_create.return_value = Mock(id=123)
            
            result = await agent.process(input_data)
            
            assert result["status"] == "success"
            assert result["data"]["classroom"]["capacity"] >= 50
            assert result["fallback_used"] is False

@pytest.mark.asyncio
async def test_scheduling_agent_fallback():
    """Test scheduling agent fallback when no rooms available"""
    agent = SchedulingAgent()
    
    input_data = {
        "event_type": "course_created",
        "course": {
            "name": "CS101",
            "students_count": 200,
            "schedule_time": "10:00"
        }
    }
    
    with patch('src.database.crud.get_available_classrooms') as mock_get:
        mock_get.return_value = []  # No rooms available
        
        result = await agent.process(input_data)
        
        assert result["status"] == "error"
        assert result["fallback_used"] is True

@pytest.mark.asyncio
async def test_equipment_agent_booking():
    """Test equipment booking with conflict check"""
    agent = EquipmentAgent()
    
    input_data = {
        "event_type": "equipment_booking",
        "booking": {
            "equipment_id": 1,
            "user_id": "user123",
            "time_slot": datetime.now().isoformat(),
            "duration_hours": 2
        }
    }
    
    with patch('src.database.crud.get_equipment') as mock_get:
        mock_get.return_value = Mock(
            id=1, 
            name="Microscope", 
            status="available",
            last_maintenance=datetime.now() - timedelta(days=30)
        )
        
        with patch('src.database.crud.check_equipment_conflicts') as mock_check:
            mock_check.return_value = []  # No conflicts
            
            with patch('src.database.crud.create_equipment_booking') as mock_create:
                mock_create.return_value = Mock(id=456)
                
                result = await agent.process(input_data)
                
                assert result["status"] == "success"
                assert result["data"]["booking_id"] == 456

@pytest.mark.asyncio
async def test_energy_agent_optimization():
    """Test energy optimization for empty rooms"""
    agent = EnergyAgent()
    
    input_data = {
        "event_type": "classroom_empty",
        "building": "Engineering",
        "classroom_id": 1
    }
    
    with patch('src.database.crud.get_empty_classrooms') as mock_get:
        mock_get.return_value = [
            Mock(id=1, name="Room 101", building="Engineering"),
            Mock(id=2, name="Room 102", building="Engineering")
        ]
        
        with patch('src.database.crud.create_energy_log') as mock_log:
            result = await agent.process(input_data)
            
            assert result["status"] == "success"
            assert result["data"]["optimized_rooms"] == 2
            assert result["data"]["total_savings_kwh"] > 0