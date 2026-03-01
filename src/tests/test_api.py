# src/tests/test_api.py
from unittest.mock import AsyncMock

def test_health_endpoint(api_client):
    """Test health check endpoint"""
    response = api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] in {"connected", "disconnected"}
    assert body["redis"] in {"connected", "disconnected"}
    assert "agents" in body

def test_create_course(api_client):
    """Test course creation endpoint"""
    from src.database import crud

    crud.create_course = AsyncMock(
        return_value=type(
            "CourseObj",
            (),
            {
                "id": 1,
                "name": "Test Course",
                "students_count": 50,
                "schedule_time": "10:00",
                "duration_minutes": 60,
                "preferred_building": None,
            },
        )()
    )

    course_data = {
        "name": "Test Course",
        "students_count": 50,
        "schedule_time": "10:00",
        "duration_minutes": 60
    }
    
    response = api_client.post("/api/v1/courses", json=course_data)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert "event_id" in body["data"]
    assert body.get("error") is None


def test_create_course_validation_error(api_client):
    course_data = {
        "name": "Te",
        "students_count": 50,
        "schedule_time": "10:00",
        "duration_minutes": 60,
    }
    response = api_client.post("/api/v1/courses", json=course_data)
    assert response.status_code == 422

def test_equipment_booking(api_client):
    """Test equipment booking endpoint"""
    booking_data = {
        "equipment_id": 1,
        "user_id": "test_user",
        "time_slot": "2024-01-01T10:00:00",
        "duration_hours": 2
    }
    
    response = api_client.post("/api/v1/equipment/book", json=booking_data)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert "event_id" in body["data"]
    assert body.get("error") is None


def test_energy_insights(api_client):
    response = api_client.get("/api/v1/energy/insights")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body.get("error") is None


def test_trigger_event(api_client):
    response = api_client.post(
        "/api/v1/events",
        params={"event_type": "energy_optimization"},
        json={"building": "Engineering"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert "event_id" in body["data"]
    assert body.get("error") is None


def test_support_suggestions(api_client):
    response = api_client.post(
        "/api/v1/support/suggestions",
        params={"user_id": "u1", "current_page": "dashboard"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body.get("error") is None