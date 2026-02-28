# src/api/routes.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
import uuid

from src.models.schemas import (
    CourseCreate, EquipmentBooking, AgentResponse,
    EventType, Classroom, HealthCheck
)
from src.agents.supervisor_agent import SupervisorAgent
from src.services.database import get_db
from src.database import crud
from src.services.monitoring import logger
from src.api.dependencies import get_supervisor

router = APIRouter()

@router.post("/courses", response_model=AgentResponse)
async def create_course(
    course: CourseCreate,
    background_tasks: BackgroundTasks,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Add a new course and trigger scheduling optimization"""
    try:
        # Generate event ID
        event_id = str(uuid.uuid4())
        
        # Store course in database
        async with get_db() as db:
            db_course = await crud.create_course(db, course.dict())
        
        # Process event in background
        background_tasks.add_task(
            supervisor.process_event,
            event_id=event_id,
            event_type=EventType.COURSE_CREATED,
            input_data={"course": db_course.dict()}
        )
        
        return AgentResponse(
            status="accepted",
            data={ 
                "event_id": event_id,
                "course_id": db_course.id,
                "message": "Course creation submitted for optimization"
            }
        )
        
    except Exception as e:
        logger.error(f"Course creation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/schedule", response_model=List[Classroom])
async def get_schedule(
    date: Optional[str] = None,
    building: Optional[str] = None,
    db = Depends(get_db)
):
    """Get optimized classroom schedule"""
    try:
        schedule = await crud.get_optimized_schedule(db, date, building)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/equipment/book", response_model=AgentResponse)
async def book_equipment(
    booking: EquipmentBooking,
    background_tasks: BackgroundTasks,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Request equipment booking"""
    try:
        event_id = str(uuid.uuid4())
        
        # Process event in background
        background_tasks.add_task(
            supervisor.process_event,
            event_id=event_id,
            event_type=EventType.EQUIPMENT_BOOKING,
            input_data={"booking": booking.dict()}
        )
        
        return AgentResponse(
            status="accepted",
            data={
                "event_id": event_id,
                "message": "Booking request submitted for processing"
            }
        )
        
    except Exception as e:
        logger.error(f"Equipment booking failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/energy/insights", response_model=AgentResponse)
async def get_energy_insights(
    background_tasks: BackgroundTasks,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Get energy optimization report"""
    try:
        event_id = str(uuid.uuid4())
        
        result = await supervisor.process_event(
            event_id=event_id,
            event_type=EventType.ENERGY_OPTIMIZATION,
            input_data={}
        )
        
        return AgentResponse(
            status="success",
            data=result
        )
        
    except Exception as e:
        logger.error(f"Energy insights failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/events", response_model=AgentResponse)
async def trigger_event(
    event_type: EventType,
    payload: dict,
    background_tasks: BackgroundTasks,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Trigger custom agent workflow"""
    try:
        event_id = str(uuid.uuid4())
        
        background_tasks.add_task(
            supervisor.process_event,
            event_id=event_id,
            event_type=event_type,
            input_data=payload
        )
        
        return AgentResponse(
            status="accepted",
            data={
                "event_id": event_id,
                "message": f"Event {event_type} triggered"
            }
        )
        
    except Exception as e:
        logger.error(f"Event trigger failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))