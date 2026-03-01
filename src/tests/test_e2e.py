# src/tests/test_e2e.py
"""End-to-end tests: API flow and supervisor workflow."""
import pytest
from unittest.mock import AsyncMock, patch

from src.agents.supervisor_agent import SupervisorAgent


def test_e2e_api_flow(api_client):
    """Run a full API flow: health → course → equipment → support → energy."""
    # 1. Health check
    health = api_client.get("/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert "agents" in data

    # 2. Create course (accepted, background processing)
    course_resp = api_client.post(
        "/api/v1/courses",
        json={
            "name": "E2E Test Course",
            "students_count": 40,
            "schedule_time": "14:00",
            "duration_minutes": 90,
        },
    )
    assert course_resp.status_code == 200
    course_body = course_resp.json()
    assert course_body["status"] == "accepted"
    assert "event_id" in course_body["data"]
    assert "course_id" in course_body["data"]

    # 3. Equipment booking (accepted)
    book_resp = api_client.post(
        "/api/v1/equipment/book",
        json={
            "equipment_id": 1,
            "user_id": "e2e_user",
            "time_slot": "2025-06-01T10:00:00",
            "duration_hours": 2,
        },
    )
    assert book_resp.status_code == 200
    book_body = book_resp.json()
    assert book_body["status"] == "accepted"
    assert "event_id" in book_body["data"]

    # 4. Support suggestions (synchronous, returns result)
    support_resp = api_client.post(
        "/api/v1/support/suggestions",
        params={"user_id": "e2e_user", "current_page": "dashboard"},
    )
    assert support_resp.status_code == 200
    support_body = support_resp.json()
    assert support_body["status"] == "success"
    assert support_body.get("error") is None

    # 5. Energy insights (synchronous)
    energy_resp = api_client.get("/api/v1/energy/insights")
    assert energy_resp.status_code == 200
    energy_body = energy_resp.json()
    assert energy_body["status"] == "success"
    assert energy_body.get("error") is None

    # 6. Trigger generic event (accepted)
    event_resp = api_client.post(
        "/api/v1/events",
        params={"event_type": "energy_optimization"},
        json={"building": "Engineering"},
    )
    assert event_resp.status_code == 200
    assert event_resp.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_e2e_supervisor_process_event_full_flow():
    """Full process_event path: real SupervisorAgent, sub-agents mocked so graph runs without I/O."""
    success_result = {
        "status": "success",
        "data": {"classroom": {"name": "Room 101", "capacity": 60}},
        "fallback_used": False,
    }

    with (
        patch("src.agents.supervisor_agent.SchedulingAgent") as mock_sched_cls,
        patch("src.agents.supervisor_agent.EquipmentAgent") as mock_equip_cls,
        patch("src.agents.supervisor_agent.EnergyAgent") as mock_energy_cls,
        patch("src.agents.supervisor_agent.NotificationAgent") as mock_notif_cls,
        patch("src.agents.supervisor_agent.SupportAgent") as mock_support_cls,
    ):
        mock_sched = AsyncMock()
        mock_sched.execute_with_retry = AsyncMock(return_value=success_result)
        mock_sched_cls.return_value = mock_sched
        mock_energy = AsyncMock()
        mock_energy.execute_with_retry = AsyncMock(return_value=success_result)
        mock_energy_cls.return_value = mock_energy
        mock_notif = AsyncMock()
        mock_notif.execute_with_retry = AsyncMock(return_value=success_result)
        mock_notif_cls.return_value = mock_notif
        mock_support = AsyncMock()
        mock_support.execute_with_retry = AsyncMock(return_value=success_result)
        mock_support_cls.return_value = mock_support
        mock_equip = AsyncMock()
        mock_equip_cls.return_value = mock_equip

        supervisor = SupervisorAgent()

    resp = await supervisor.process_event(
        "e2e-process-1",
        "course_created",
        {
            "course": {
                "name": "E2E Course",
                "students_count": 50,
                "schedule_time": "10:00",
                "preferred_building": "Engineering",
            }
        },
    )

    assert resp["event_id"] == "e2e-process-1"
    assert resp["status"] in ("completed", "completed_with_errors")
    assert "results" in resp
    assert "execution_time" in resp
    assert "scheduling" in resp.get("results", {})
    assert resp["results"]["scheduling"]["status"] == "success"
