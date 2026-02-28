# src/api/dependencies.py
from typing import AsyncGenerator, Optional
from fastapi import Depends

from src.agents.supervisor_agent import SupervisorAgent

# Global supervisor instance - will be set in main.py
supervisor_agent: Optional[SupervisorAgent] = None

async def get_supervisor() -> SupervisorAgent:
    """Dependency to get supervisor agent instance"""
    if supervisor_agent is None:
        raise RuntimeError("Supervisor agent not initialized")
    return supervisor_agent

def set_supervisor(agent: SupervisorAgent):
    """Set the global supervisor agent instance"""
    global supervisor_agent
    supervisor_agent = agent