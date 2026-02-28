# src/tests/conftest.py
import pytest
from unittest.mock import AsyncMock
from src.agents.supervisor_agent import SupervisorAgent

@pytest.fixture
def mock_supervisor():
    """Mock supervisor agent for testing"""
    supervisor = AsyncMock(spec=SupervisorAgent)
    supervisor.process_event.return_value = {
        "event_id": "test-123",
        "status": "completed",
        "results": {}
    }
    return supervisor