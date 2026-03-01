# src/agents/base_agent.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain.tools import BaseTool
from langchain_classic.memory import ConversationBufferMemory
from src.core.config import settings
from src.services.retry import with_retry
from src.services.monitoring import logger
import time

class BaseAgent(ABC):
    """Base class for all agents with common functionality"""
    
    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type
        self.memory = ConversationBufferMemory()
        self.tools: list[BaseTool] = []
        self.setup_tools()
    
    @abstractmethod
    def setup_tools(self):
        """Initialize agent-specific tools"""
        pass
    
    @abstractmethod
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main processing method to be implemented by each agent"""
        pass
    
    @with_retry(max_retries=settings.MAX_RETRIES)
    async def execute_with_retry(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent task with retry logic"""
        start_time = time.time()
        event_type = input_data.get("event_type") or input_data.get("request_type") or "unknown"

        try:
            logger.info(f"Agent {self.name} started processing",
                       extra={"agent_type": self.agent_type, "input": input_data})

            result = await self.process(input_data)

            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Agent {self.name} completed in {elapsed_ms:.0f}ms",
                       extra={"result_status": result.get("status")})

            # Record metrics for analytics
            try:
                from src.services.agent_metrics import record_agent_execution
                status = result.get("status", "unknown")
                if result.get("fallback_used"):
                    status = "fallback"
                await record_agent_execution(
                    self.agent_type, status, elapsed_ms, str(event_type)
                )
            except Exception:
                pass

            return result

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Agent {self.name} failed: {str(e)}", exc_info=True)
            try:
                from src.services.agent_metrics import record_agent_execution
                await record_agent_execution(self.agent_type, "error", elapsed_ms, str(event_type))
            except Exception:
                pass
            return {
                "status": "error",
                "data": None,
                "error": str(e),
                "fallback_used": False
            }
    
    def get_fallback_response(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Provide fallback response when agent fails"""
        return {
            "status": "fallback",
            "data": None,
            "error": "Agent unavailable, using fallback logic",
            "fallback_used": True
        }