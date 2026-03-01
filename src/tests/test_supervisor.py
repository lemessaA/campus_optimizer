# src/tests/test_supervisor.py
import pytest
from unittest.mock import AsyncMock

from src.agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
async def test_route_to_agent_support_event():
    supervisor = SupervisorAgent()

    state = {
        "event_id": "e1",
        "event_type": "support_query",
        "input_data": {"query": "help"},
        "agent_results": {},
        "current_agent": "supervisor",
        "errors": [],
        "fallback_used": False,
        "iteration_count": 0,
        "start_time": 0.0,
    }

    assert supervisor.route_to_agent(state) == "support"


@pytest.mark.asyncio
async def test_support_node_calls_support_agent():
    supervisor = SupervisorAgent()
    supervisor.support_agent.execute_with_retry = AsyncMock(return_value={"status": "success", "data": {}})

    state = {
        "event_id": "e1",
        "event_type": "support_query",
        "input_data": {"query": "how to book?", "user_id": "u1"},
        "agent_results": {},
        "current_agent": "supervisor",
        "errors": [],
        "fallback_used": False,
        "iteration_count": 0,
        "start_time": 0.0,
    }

    new_state = await supervisor.support_node(state)

    supervisor.support_agent.execute_with_retry.assert_awaited_once_with(
        {"request_type": "support_query", "query": "how to book?", "user_id": "u1"}
    )
    assert "support" in new_state["agent_results"]
    assert new_state["current_agent"] == "support"


@pytest.mark.asyncio
async def test_process_event_success_formats_response():
    supervisor = SupervisorAgent()

    final_state = {
        "event_id": "e1",
        "event_type": "course_created",
        "input_data": {},
        "agent_results": {"scheduling": {"status": "success", "data": {}}},
        "current_agent": "end",
        "errors": [],
        "fallback_used": False,
        "iteration_count": 1,
        "start_time": 0.0,
    }

    supervisor.graph.ainvoke = AsyncMock(return_value=final_state)

    resp = await supervisor.process_event("e1", "course_created", {})
    assert resp["event_id"] == "e1"
    assert resp["status"] == "completed"
    assert resp["errors"] == []
    assert resp["fallback_used"] is False
    assert "execution_time" in resp


@pytest.mark.asyncio
async def test_process_event_failure_returns_failed():
    supervisor = SupervisorAgent()
    supervisor.graph.ainvoke = AsyncMock(side_effect=RuntimeError("boom"))

    resp = await supervisor.process_event("e1", "course_created", {})
    assert resp["event_id"] == "e1"
    assert resp["status"] == "failed"
    assert resp["fallback_used"] is True
    assert "error" in resp
