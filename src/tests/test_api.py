# src/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_health_endpoint():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_create_course():
    """Test course creation endpoint"""
    course_data = {
        "name": "Test Course",
        "students_count": 50,
        "schedule_time": "10:00",
        "duration_minutes": 60
    }
    
    response = client.post("/api/v1/courses", json=course_data)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert "event_id" in response.json()["data"]

def test_equipment_booking():
    """Test equipment booking endpoint"""
    booking_data = {
        "equipment_id": 1,
        "user_id": "test_user",
        "time_slot": "2024-01-01T10:00:00",
        "duration_hours": 2
    }
    
    response = client.post("/api/v1/equipment/book", json=booking_data)
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"