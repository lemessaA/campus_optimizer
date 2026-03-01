# src/api/routes.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from datetime import datetime
import uuid
import json

from src.models.schemas import (
    CourseCreate, EquipmentBooking, AgentResponse,
    EventType, Classroom, HealthCheck, EventPayload,
    ScheduleEntry, Equipment, EquipmentBookingEntry,
    EnergyLogEntry, EnergyConsumptionPoint,
    SupportQueryRequest, TicketCreateRequest, TicketEscalateRequest,
    SupportTicketEntry, FAQEntry,
)
from src.agents.supervisor_agent import SupervisorAgent
from src.agents.analytics_agent import AnalyticsAgent
from src.agents.health_agent import HealthAgent
from src.agents.insights_agent import InsightsAgent
from src.services.database import get_db, get_db_session
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
            input_data={"course": {"id": db_course.id, "name": db_course.name, "students_count": db_course.students_count, "schedule_time": db_course.schedule_time, "duration_minutes": db_course.duration_minutes, "preferred_building": db_course.preferred_building}}
        )
        
        return AgentResponse(
            status="accepted",
            data={ 
                "event_id": event_id,
                "course_id": db_course.id,
                "message": "Course creation submitted for optimization"
            },
            error=None
        )
        
    except Exception as e:
        logger.error(f"Course creation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/schedule", response_model=List[Classroom])
async def get_schedule(
    date: Optional[str] = None,
    building: Optional[str] = None,
    db = Depends(get_db_session)
):
    """Get optimized classroom schedule"""
    try:
        schedule = await crud.get_optimized_schedule(db, date, building)
        return schedule
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/support/tickets", response_model=List[SupportTicketEntry])
async def list_tickets(
    user_id: str,
    limit: int = 50,
    db = Depends(get_db_session),
):
    """List user tickets from database"""
    try:
        tickets = await crud.list_user_tickets(db, user_id=user_id, limit=limit)
        return [
            {
                "id": t.id,
                "category": t.category,
                "status": t.status,
                "priority": t.priority,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t in tickets
        ]
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/support/tickets/{ticket_id}/escalate", response_model=AgentResponse)
async def escalate_ticket(
    ticket_id: int,
    payload: TicketEscalateRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor),
):
    """Escalate a ticket"""
    try:
        event_id = str(uuid.uuid4())
        result = await supervisor.process_event(
            event_id=event_id,
            event_type="ticket_escalation",
            input_data={
                "request_type": "escalate",
                "ticket_id": ticket_id,
                "reason": payload.reason,
                "user_id": payload.user_id,
            },
        )

        return AgentResponse(status="success", data=result, error=None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/support/faqs", response_model=List[FAQEntry])
async def get_faqs():
    """List FAQs from Redis knowledge base"""
    try:
        from src.services.cache import redis_client

        if not redis_client:
            return []

        raw = await redis_client.get("support:faqs")
        if not raw:
            return []

        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")

        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            items = []
            for faq_id, faq in data.items():
                items.append({"id": str(faq_id), **faq})
            return items
        return []
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/schedule/entries", response_model=List[ScheduleEntry])
async def get_schedule_entries(
    date: Optional[str] = None,
    building: Optional[str] = None,
    limit: int = 200,
    db = Depends(get_db_session),
):
    """Get schedule rows (course + classroom + utilization)"""
    try:
        entries = await crud.get_schedule_entries(db, date=date, building=building, limit=limit)
        return entries
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
            },
            error=None
        )
        
    except Exception as e:
        logger.error(f"Equipment booking failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/equipment", response_model=List[Equipment])
async def get_equipment_list(
    status: Optional[str] = None,
    db = Depends(get_db_session),
):
    """List equipment from database"""
    try:
        items = await crud.list_equipment(db, status=status)
        return items
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/equipment/bookings", response_model=List[EquipmentBookingEntry])
async def get_equipment_bookings(
    equipment_id: Optional[int] = None,
    limit: int = 50,
    db = Depends(get_db_session),
):
    """Get recent equipment bookings"""
    try:
        bookings = await crud.get_recent_equipment_bookings(db, limit=limit, equipment_id=equipment_id)
        return bookings
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
# src/api/routes.py (add these endpoints)

@router.post("/support/query", response_model=AgentResponse)
async def support_query(
    payload: SupportQueryRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Submit a support query"""
    try:
        event_id = str(uuid.uuid4())
        
        result = await supervisor.process_event(
            event_id=event_id,
            event_type="support_query",
            input_data={
                "request_type": "faq_query",
                "query": payload.query,
                "user_id": payload.user_id,
            },
        )

        return AgentResponse(status="success", data=result, error=None)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/support/tickets", response_model=AgentResponse)
async def create_ticket(
    ticket_data: TicketCreateRequest,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Create a support ticket"""
    try:
        event_id = str(uuid.uuid4())
        
        result = await supervisor.process_event(
            event_id=event_id,
            event_type="ticket_creation",
            input_data={
                "request_type": "create_ticket",
                **ticket_data.dict(),
            },
        )

        return AgentResponse(status="success", data=result, error=None)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/support/tickets/{ticket_id}", response_model=AgentResponse)
async def get_ticket_status(
    ticket_id: int,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Get ticket status"""
    try:
        event_id = str(uuid.uuid4())
        
        result = await supervisor.process_event(
            event_id=event_id,
            event_type="ticket_status",
            input_data={
                "request_type": "check_status",
                "ticket_id": ticket_id
            }
        )
        
        return AgentResponse(
            status="success",
            data=result,
            error=None,
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/support/suggestions", response_model=AgentResponse)
async def get_suggestions(
    user_id: str,
    current_page: Optional[str] = None,
    supervisor: SupervisorAgent = Depends(get_supervisor)
):
    """Get contextual suggestions for user"""
    try:
        event_id = str(uuid.uuid4())
        
        result = await supervisor.process_event(
            event_id=event_id,
            event_type="suggestions",
            input_data={
                "request_type": "get_suggestions",
                "user_id": user_id,
                "current_page": current_page
            }
        )
        
        return AgentResponse(
            status="success",
            data=result,
            error=None,
        )
        
    except Exception as e:
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
            data=result,
            error=None
        )
        
    except Exception as e:
        logger.error(f"Energy insights failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/energy/consumption", response_model=List[EnergyConsumptionPoint])
async def get_energy_consumption(
    hours: int = 24,
    building: Optional[str] = None,
    db = Depends(get_db_session),
):
    """Get raw energy consumption points from DB for charting"""
    try:
        return await crud.get_energy_consumption_series(db, hours=hours, building=building)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/energy/logs", response_model=List[EnergyLogEntry])
async def get_energy_logs(
    hours: int = 24,
    limit: int = 200,
    db = Depends(get_db_session),
):
    """Get recent energy optimization logs"""
    try:
        return await crud.get_energy_log_entries(db, hours=hours, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/events", response_model=AgentResponse)
async def trigger_event(
    event_type: EventType,
    background_tasks: BackgroundTasks,
    supervisor: SupervisorAgent = Depends(get_supervisor),
    payload: Optional[EventPayload] = None,
):
    """Trigger custom agent workflow or analysis agents."""
    try:
        event_id = str(uuid.uuid4())

        # Analysis agents run synchronously and return results immediately
        _p = payload.model_dump(exclude_none=True) if payload else {}
        if event_type == EventType.ANALYTICS_REPORT:
            agent = AnalyticsAgent()
            result = await agent.execute_with_retry(
                {"report_type": _p.get("report_type", "full"), **_p}
            )
            return AgentResponse(
                status=result.get("status", "success"),
                data={"event_id": event_id, **result},
                error=result.get("error"),
                fallback_used=result.get("fallback_used", False),
            )
        if event_type == EventType.HEALTH_CHECK:
            agent = HealthAgent()
            result = await agent.execute_with_retry(
                {"report_type": _p.get("report_type", "full"), **_p}
            )
            return AgentResponse(
                status=result.get("status", "success"),
                data={"event_id": event_id, **result},
                error=result.get("error"),
                fallback_used=result.get("fallback_used", False),
            )
        if event_type == EventType.INSIGHTS_REPORT:
            agent = InsightsAgent()
            result = await agent.execute_with_retry(
                {"domain": _p.get("domain", "all"), **_p}
            )
            return AgentResponse(
                status=result.get("status", "success"),
                data={"event_id": event_id, **result},
                error=result.get("error"),
                fallback_used=result.get("fallback_used", False),
            )

        # Other events go through supervisor (background)
        background_tasks.add_task(
            supervisor.process_event,
            event_id=event_id,
            event_type=event_type,
            input_data=_p
        )

        return AgentResponse(
            status="accepted",
            data={
                "event_id": event_id,
                "message": f"Event {event_type} triggered"
            },
            error=None
        )

    except Exception as e:
        logger.error(f"Event trigger failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Dashboard (real data from DB/cache) ----------

@router.get("/dashboard/metrics")
async def get_dashboard_metrics(db=Depends(get_db_session)):
    """Production metrics: classrooms booked today, equipment available, energy savings, agent status."""
    from datetime import date
    from src.services.database import check_db_connection
    from src.services.cache import check_redis_connection

    try:
        today = date.today().isoformat()
        schedule_entries = await crud.get_schedule_entries(db, date=today, limit=500)
        classrooms_booked_today = len(schedule_entries)

        equipment_list = await crud.list_equipment(db, status="available")
        equipment_available = len(equipment_list)

        energy_logs = await crud.get_energy_log_entries(db, hours=24, limit=500)
        energy_savings_today_kwh = sum(
            float(e.get("savings_kwh") or 0) for e in energy_logs
        )

        db_ok = await check_db_connection()
        redis_ok = await check_redis_connection()
        agents = {
            "supervisor": "active",
            "scheduling": "active",
            "equipment": "active",
            "energy": "active",
            "notification": "active",
        }

        # Include analysis agent status
        agents["analytics"] = "active"
        agents["health"] = "active"
        agents["insights"] = "active"

        return {
            "classrooms_booked_today": classrooms_booked_today,
            "equipment_available": equipment_available,
            "energy_savings_today_kwh": round(energy_savings_today_kwh, 1),
            "agents": agents,
            "database": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        }
    except Exception as e:
        logger.error(f"Dashboard metrics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Analysis Agents (Analytics, Health, Insights) ----------

@router.get("/analytics/report", response_model=AgentResponse)
async def get_analytics_report(
    report_type: Optional[str] = None,
):
    """Get analytics report: full, usage, performance, or trends."""
    try:
        agent = AnalyticsAgent()
        result = await agent.execute_with_retry({"report_type": report_type or "full"})
        return AgentResponse(
            status=result.get("status", "success"),
            data=result.get("data"),
            error=result.get("error"),
            fallback_used=result.get("fallback_used", False),
        )
    except Exception as e:
        logger.error(f"Analytics report failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/report", response_model=AgentResponse)
async def get_health_report(
    report_type: Optional[str] = None,
):
    """Get system health report: full, agents, or infrastructure."""
    try:
        agent = HealthAgent()
        result = await agent.execute_with_retry({"report_type": report_type or "full"})
        return AgentResponse(
            status=result.get("status", "success"),
            data=result.get("data"),
            error=result.get("error"),
            fallback_used=result.get("fallback_used", False),
        )
    except Exception as e:
        logger.error(f"Health report failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights", response_model=AgentResponse)
async def get_insights(
    domain: Optional[str] = None,
):
    """Get predictive insights: all, scheduling, energy, or equipment."""
    try:
        agent = InsightsAgent()
        result = await agent.execute_with_retry({"domain": domain or "all"})
        return AgentResponse(
            status=result.get("status", "success"),
            data=result.get("data"),
            error=result.get("error"),
            fallback_used=result.get("fallback_used", False),
        )
    except Exception as e:
        logger.error(f"Insights failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/recent_activity")
async def get_dashboard_recent_activity(db=Depends(get_db_session)):
    """Recent activity from schedule, equipment bookings, and energy logs (real data)."""
    from datetime import date

    try:
        today = date.today().isoformat()
        schedule_entries = await crud.get_schedule_entries(db, date=today, limit=10)
        equipment_bookings = await crud.get_recent_equipment_bookings(db, limit=10)
        energy_logs = await crud.get_energy_log_entries(db, hours=24, limit=10)

        activities = []
        for e in schedule_entries:
            t = e.get("time")
            time_str = t.strftime("%H:%M") if t and hasattr(t, "strftime") else str(t or "")
            activities.append({
                "time": time_str,
                "event": f"Course Scheduled: {e.get('course_name', 'N/A')}",
                "status": "Scheduled",
                "agent": "Scheduling",
                "_sort": time_str,
            })
        for b in equipment_bookings:
            t = b.get("start_time")
            time_str = t.strftime("%H:%M") if t and hasattr(t, "strftime") else str(t or "")
            iso = t.isoformat() if t and hasattr(t, "isoformat") else time_str
            activities.append({
                "time": time_str,
                "event": f"Equipment Booked: {b.get('equipment_name', 'N/A')}",
                "status": "Approved",
                "agent": "Equipment",
                "_sort": iso,
            })
        for log in energy_logs:
            ts = log.get("timestamp")
            time_str = ts.strftime("%H:%M") if ts and hasattr(ts, "strftime") else str(ts or "")
            iso = ts.isoformat() if ts and hasattr(ts, "isoformat") else time_str
            activities.append({
                "time": time_str,
                "event": f"Energy optimization: {log.get('building', 'N/A')}",
                "status": "Completed",
                "agent": "Energy",
                "_sort": iso,
            })

        activities.sort(key=lambda x: x.get("_sort", ""), reverse=True)
        for a in activities:
            a.pop("_sort", None)
        return {"activities": activities[:20]}
    except Exception as e:
        logger.error(f"Dashboard recent activity failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/analysis")
async def get_dashboard_analysis():
    """Aggregated analysis for dashboard: analytics summary, health, and top insights."""
    try:
        analytics_agent = AnalyticsAgent()
        health_agent = HealthAgent()
        insights_agent = InsightsAgent()

        analytics_result = await analytics_agent.execute_with_retry({"report_type": "usage"})
        health_result = await health_agent.execute_with_retry({"report_type": "agents"})
        insights_result = await insights_agent.execute_with_retry({"domain": "all"})

        return {
            "analytics": analytics_result.get("data", {}),
            "health": health_result.get("data", {}),
            "insights": insights_result.get("data", {}),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Dashboard analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))