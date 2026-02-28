# src/agents/supervisor_agent.py
from typing import Dict, Any, List, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from src.agents.scheduling_agent import SchedulingAgent
from src.agents.equipment_agent import EquipmentAgent
from src.agents.energy_agent import EnergyAgent
from src.agents.notification_agent import NotificationAgent
from src.core.config import settings
from src.services.monitoring import logger
import time

class AgentState(TypedDict):
    """State schema for LangGraph workflow"""
    event_id: str
    event_type: str
    input_data: Dict[str, Any]
    agent_results: Dict[str, Any]
    current_agent: str
    errors: List[str]
    fallback_used: bool
    iteration_count: int
    start_time: float

class SupervisorAgent:
    """Central orchestrator using LangGraph"""
    
    def __init__(self):
        self.scheduling_agent = SchedulingAgent()
        self.equipment_agent = EquipmentAgent()
        self.energy_agent = EnergyAgent()
        self.notification_agent = NotificationAgent()
        
        # Initialize LangGraph workflow
        self.workflow = self._create_workflow()
        self.graph = self.workflow.compile()
    
    def _create_workflow(self) -> StateGraph:
        """Create the LangGraph workflow"""
        
        # Initialize the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes for each agent
        workflow.add_node("supervisor", self.supervisor_node)
        workflow.add_node("scheduling", self.scheduling_node)
        workflow.add_node("equipment", self.equipment_node)
        workflow.add_node("energy", self.energy_node)
        workflow.add_node("notification", self.notification_node)
        
        # Set entry point
        workflow.set_entry_point("supervisor")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "supervisor",
            self.route_to_agent,
            {
                "scheduling": "scheduling",
                "equipment": "equipment",
                "energy": "energy",
                "notification": "notification",
                "end": END
            }
        )
        
        # Add edges from agents back to supervisor
        workflow.add_edge("scheduling", "supervisor")
        workflow.add_edge("equipment", "supervisor")
        workflow.add_edge("energy", "supervisor")
        workflow.add_edge("notification", "supervisor")
        
        return workflow
    
    async def supervisor_node(self, state: AgentState) -> AgentState:
        """Supervisor node - coordinates agent execution"""
        
        # Check iteration limit
        if state["iteration_count"] >= settings.MAX_ITERATIONS:
            logger.warning(f"Max iterations reached for event {state['event_id']}")
            state["errors"].append("Max iterations exceeded")
            state["current_agent"] = "end"
            return state
        
        # Increment iteration count
        state["iteration_count"] += 1
        
        # Check timeout
        elapsed = time.time() - state["start_time"]
        if elapsed > settings.AGENT_TIMEOUT:
            logger.warning(f"Timeout reached for event {state['event_id']}")
            state["errors"].append("Workflow timeout")
            state["current_agent"] = "end"
        
        return state
    
    def route_to_agent(self, state: AgentState) -> str:
        """Determine which agent to run next"""
        
        # If we have errors and should end
        if len(state["errors"]) > 3 or state["current_agent"] == "end":
            return "end"
        
        # Route based on event type and current state
        event_type = state["event_type"]
        current = state["current_agent"]
        
        # Initial routing
        if current == "supervisor":
            if event_type in ["course_created", "timetable_updated"]:
                return "scheduling"
            elif event_type == "equipment_booking":
                return "equipment"
            elif event_type in ["classroom_empty", "energy_optimization"]:
                return "energy"
            else:
                return "notification"
        
        # Subsequent routing (chain of agents)
        if current == "scheduling":
            return "energy"  # After scheduling, optimize energy
        elif current == "energy":
            return "notification"  # After energy, notify
        elif current == "equipment":
            return "notification"  # After equipment, notify
        elif current == "notification":
            return "end"  # Done
        
        return "end"
    
    async def scheduling_node(self, state: AgentState) -> AgentState:
        """Execute scheduling agent"""
        try:
            result = await self.scheduling_agent.execute_with_retry({
                "event_type": state["event_type"],
                **state["input_data"]
            })
            
            state["agent_results"]["scheduling"] = result
            
            if result["status"] == "error":
                state["errors"].append(f"Scheduling error: {result.get('error')}")
                state["fallback_used"] = state["fallback_used"] or result.get("fallback_used", False)
            
        except Exception as e:
            logger.error(f"Scheduling node failed: {str(e)}")
            state["errors"].append(f"Scheduling exception: {str(e)}")
        
        state["current_agent"] = "scheduling"
        return state
    
    async def equipment_node(self, state: AgentState) -> AgentState:
        """Execute equipment agent"""
        try:
            result = await self.equipment_agent.execute_with_retry({
                "event_type": state["event_type"],
                **state["input_data"]
            })
            
            state["agent_results"]["equipment"] = result
            
            if result["status"] == "error":
                state["errors"].append(f"Equipment error: {result.get('error')}")
                state["fallback_used"] = state["fallback_used"] or result.get("fallback_used", False)
            
        except Exception as e:
            logger.error(f"Equipment node failed: {str(e)}")
            state["errors"].append(f"Equipment exception: {str(e)}")
        
        state["current_agent"] = "equipment"
        return state
    
    async def energy_node(self, state: AgentState) -> AgentState:
        """Execute energy agent"""
        try:
            result = await self.energy_agent.execute_with_retry({
                "event_type": state["event_type"],
                **state["input_data"]
            })
            
            state["agent_results"]["energy"] = result
            
            if result["status"] == "error":
                state["errors"].append(f"Energy error: {result.get('error')}")
                state["fallback_used"] = state["fallback_used"] or result.get("fallback_used", False)
            
        except Exception as e:
            logger.error(f"Energy node failed: {str(e)}")
            state["errors"].append(f"Energy exception: {str(e)}")
        
        state["current_agent"] = "energy"
        return state
    
    async def notification_node(self, state: AgentState) -> AgentState:
        """Execute notification agent"""
        try:
            # Prepare notification message based on results
            message = self.prepare_notification(state)
            
            result = await self.notification_agent.execute_with_retry({
                "notification_type": state["event_type"],
                "recipient": "dashboard",
                "message": message
            })
            
            state["agent_results"]["notification"] = result
            
        except Exception as e:
            logger.error(f"Notification node failed: {str(e)}")
            state["errors"].append(f"Notification exception: {str(e)}")
        
        state["current_agent"] = "notification"
        return state
    
    def prepare_notification(self, state: AgentState) -> Dict[str, Any]:
        """Prepare user-friendly notification message"""
        message = {
            "event_id": state["event_id"],
            "event_type": state["event_type"],
            "timestamp": time.time(),
            "results": {},
            "warnings": [],
            "success": len(state["errors"]) == 0
        }
        
        # Add agent results
        for agent, result in state["agent_results"].items():
            if result.get("status") == "success":
                message["results"][agent] = result.get("data", {})
            else:
                message["warnings"].append(f"{agent} had issues: {result.get('error', 'unknown')}")
        
        # Add fallback warning
        if state["fallback_used"]:
            message["warnings"].append("Some operations used fallback logic")
        
        return message
    
    async def process_event(self, event_id: str, event_type: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process an event through the multi-agent workflow"""
        
        # Initialize state
        initial_state = AgentState(
            event_id=event_id,
            event_type=event_type,
            input_data=input_data,
            agent_results={},
            current_agent="supervisor",
            errors=[],
            fallback_used=False,
            iteration_count=0,
            start_time=time.time()
        )
        
        try:
            # Run the workflow
            final_state = await self.graph.ainvoke(initial_state)
            
            # Prepare response
            response = {
                "event_id": event_id,
                "status": "completed" if len(final_state["errors"]) == 0 else "completed_with_errors",
                "results": final_state["agent_results"],
                "errors": final_state["errors"],
                "fallback_used": final_state["fallback_used"],
                "execution_time": time.time() - initial_state["start_time"]
            }
            
            logger.info(f"Event {event_id} processed", 
                       extra={"status": response["status"], "errors": len(response["errors"])})
            
            return response
            
        except Exception as e:
            logger.error(f"Workflow failed for event {event_id}: {str(e)}", exc_info=True)
            return {
                "event_id": event_id,
                "status": "failed",
                "error": str(e),
                "fallback_used": True
            }