# src/tests/conftest.py
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient

@pytest.fixture
def mock_supervisor():
    """Mock supervisor agent for testing"""
    supervisor = AsyncMock()
    supervisor.process_event.return_value = {
        "event_id": "test-123",
        "status": "completed",
        "results": {}
    }
    return supervisor


@pytest.fixture
def mock_db_ctx():
    """Async context manager that yields a dummy db session object."""
    db = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield db

    return _ctx


@pytest.fixture
def api_client(monkeypatch, mock_supervisor, mock_db_ctx):
    """TestClient with external services mocked and supervisor initialized."""
    from src import main as main_module
    from src.api import dependencies as deps
    from src.api import routes as routes_module
    from src.services import database as database_module
    from src.services import cache as cache_module

    # Prevent real DB/Redis initialization during app lifespan
    monkeypatch.setattr(main_module, "init_db", AsyncMock())
    monkeypatch.setattr(main_module, "init_redis", AsyncMock())
    monkeypatch.setattr(main_module, "close_db", AsyncMock())
    monkeypatch.setattr(main_module, "close_redis", AsyncMock())

    # Use mock supervisor in lifespan so SupervisorAgent() is never constructed (avoids LLM/embeddings)
    monkeypatch.setattr(main_module, "SupervisorAgent", lambda: mock_supervisor)

    # Ensure /health doesn't touch real DB/Redis clients
    monkeypatch.setattr(database_module, "check_db_connection", AsyncMock(return_value=True))
    monkeypatch.setattr(cache_module, "check_redis_connection", AsyncMock(return_value=True))

    # Patch DB context manager imported into routes module
    monkeypatch.setattr(routes_module, "get_db", mock_db_ctx)

    with TestClient(main_module.app) as client:
        yield client