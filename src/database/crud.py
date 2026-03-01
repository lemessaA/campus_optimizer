# src/database/crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta
from typing import List, Optional

from src.database.models import (
    Classroom, Course, Equipment, 
    EquipmentBooking, ClassroomBooking, EnergyLog,
    SupportTicket, TicketUpdate,
)


async def get_schedule_entries(
    db: AsyncSession,
    date: Optional[str] = None,
    building: Optional[str] = None,
    limit: int = 200,
) -> List[dict]:
    query = (
        select(ClassroomBooking, Classroom, Course)
        .join(Classroom, Classroom.id == ClassroomBooking.classroom_id)
        .join(Course, Course.id == ClassroomBooking.course_id)
    )

    if building:
        query = query.where(Classroom.building == building)

    if date:
        day = datetime.strptime(date, "%Y-%m-%d")
        start = day
        end = day + timedelta(days=1)
        query = query.where(and_(ClassroomBooking.date >= start, ClassroomBooking.date < end))

    query = query.order_by(ClassroomBooking.date.desc()).limit(limit)

    result = await db.execute(query)
    rows = result.all()

    entries: List[dict] = []
    for booking, classroom, course in rows:
        capacity = classroom.capacity or 0
        students = course.students_count or 0
        utilization = (students / capacity) if capacity else 0.0

        entries.append(
            {
                "time": booking.time_slot,
                "course_name": course.name,
                "classroom_name": classroom.name,
                "classroom_capacity": capacity,
                "building": classroom.building,
                "students_count": students,
                "utilization_rate": utilization,
            }
        )

    return entries

async def create_course(db: AsyncSession, course_data: dict) -> Course:
    """Create a new course"""
    course = Course(**course_data)
    db.add(course)
    await db.commit()
    await db.refresh(course)
    return course

async def get_available_classrooms(
    db: AsyncSession, 
    min_capacity: int,
    building: Optional[str] = None,
    time_slot: Optional[str] = None
) -> List[Classroom]:
    """Get available classrooms meeting criteria"""
    query = select(Classroom).where(Classroom.capacity >= min_capacity)
    
    if building:
        query = query.where(Classroom.building == building)
    
    # Check for conflicts if time_slot provided
    if time_slot:
        # Subquery for booked classrooms at this time
        booked = select(ClassroomBooking.classroom_id).where(
            ClassroomBooking.time_slot == time_slot
        )
        query = query.where(Classroom.id.not_in(booked))
    
    result = await db.execute(query)
    return result.scalars().all()


async def create_support_ticket(
    db: AsyncSession,
    user_id: str,
    category: str,
    description: str,
    priority: int,
    context: Optional[dict] = None,
) -> SupportTicket:
    ticket = SupportTicket(
        user_id=user_id,
        category=category,
        description=description,
        priority=priority,
        status="open",
        context=context,
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    update = TicketUpdate(
        ticket_id=ticket.id,
        message="Ticket created",
        update_type="status_change",
        created_by=user_id,
    )
    db.add(update)
    await db.commit()
    return ticket


async def get_ticket(db: AsyncSession, ticket_id: int) -> Optional[SupportTicket]:
    result = await db.execute(select(SupportTicket).where(SupportTicket.id == ticket_id))
    return result.scalar_one_or_none()


async def get_ticket_updates(db: AsyncSession, ticket_id: int) -> List[TicketUpdate]:
    result = await db.execute(
        select(TicketUpdate)
        .where(TicketUpdate.ticket_id == ticket_id)
        .order_by(TicketUpdate.created_at.desc())
    )
    return result.scalars().all()


async def create_ticket_update(
    db: AsyncSession,
    ticket_id: int,
    message: str,
    update_type: str = "comment",
    created_by: Optional[str] = None,
) -> TicketUpdate:
    update = TicketUpdate(
        ticket_id=ticket_id,
        message=message,
        update_type=update_type,
        created_by=created_by,
    )
    db.add(update)
    await db.commit()
    await db.refresh(update)
    return update


async def update_ticket_priority(db: AsyncSession, ticket_id: int, priority: int) -> None:
    ticket = await get_ticket(db, ticket_id)
    if ticket is None:
        return
    ticket.priority = priority
    ticket.updated_at = datetime.utcnow()
    await db.commit()


async def list_user_tickets(db: AsyncSession, user_id: str, limit: int = 50) -> List[SupportTicket]:
    result = await db.execute(
        select(SupportTicket)
        .where(SupportTicket.user_id == user_id)
        .order_by(SupportTicket.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def get_user_open_tickets(db: AsyncSession, user_id: str) -> List[SupportTicket]:
    result = await db.execute(
        select(SupportTicket).where(
            and_(SupportTicket.user_id == user_id, SupportTicket.status.in_(["open", "in_progress"]))
        )
    )
    return result.scalars().all()


async def get_user_recent_bookings(db: AsyncSession, user_id: str, days: int = 7) -> List[EquipmentBooking]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(EquipmentBooking).where(
            and_(EquipmentBooking.user_id == user_id, EquipmentBooking.start_time >= cutoff)
        )
    )
    return result.scalars().all()


async def get_user_courses(db: AsyncSession, user_id: str) -> List[Course]:
    # Courses currently have no user linkage in the schema.
    return []

async def create_classroom_booking(
    db: AsyncSession,
    classroom_id: int,
    course_id: int,
    time_slot: str
) -> ClassroomBooking:
    """Create a classroom booking"""
    booking = ClassroomBooking(
        classroom_id=classroom_id,
        course_id=course_id,
        time_slot=time_slot
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking

async def get_equipment(db: AsyncSession, equipment_id: int) -> Optional[Equipment]:
    """Get equipment by ID"""
    result = await db.execute(
        select(Equipment).where(Equipment.id == equipment_id)
    )
    return result.scalar_one_or_none()


async def list_equipment(db: AsyncSession, status: Optional[str] = None) -> List[dict]:
    query = select(Equipment)
    if status:
        query = query.where(Equipment.status == status)
    query = query.order_by(Equipment.lab.asc(), Equipment.name.asc())
    result = await db.execute(query)
    equipment_items = list(result.scalars().all())
    return [
        {
            "id": e.id,
            "name": e.name,
            "lab": e.lab,
            "status": e.status,
            "last_maintenance": e.last_maintenance,
        }
        for e in equipment_items
    ]


async def get_recent_equipment_bookings(
    db: AsyncSession,
    limit: int = 50,
    equipment_id: Optional[int] = None,
) -> List[dict]:
    query = select(EquipmentBooking, Equipment).join(Equipment, Equipment.id == EquipmentBooking.equipment_id)
    if equipment_id is not None:
        query = query.where(EquipmentBooking.equipment_id == equipment_id)
    query = query.order_by(EquipmentBooking.start_time.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    items: List[dict] = []
    for booking, equipment in rows:
        items.append(
            {
                "id": booking.id,
                "equipment_id": booking.equipment_id,
                "equipment_name": equipment.name,
                "user_id": booking.user_id,
                "start_time": booking.start_time,
                "end_time": booking.end_time,
            }
        )
    return items

async def check_equipment_conflicts(
    db: AsyncSession,
    equipment_id: int,
    start_time: datetime,
    end_time: datetime
) -> List[EquipmentBooking]:
    """Check for booking conflicts"""
    result = await db.execute(
        select(EquipmentBooking).where(
            and_(
                EquipmentBooking.equipment_id == equipment_id,
                or_(
                    and_(
                        EquipmentBooking.start_time <= start_time,
                        EquipmentBooking.end_time > start_time
                    ),
                    and_(
                        EquipmentBooking.start_time < end_time,
                        EquipmentBooking.end_time >= end_time
                    )
                )
            )
        )
    )
    return result.scalars().all()

async def create_equipment_booking(
    db: AsyncSession,
    equipment_id: int,
    user_id: str,
    start_time: datetime,
    end_time: datetime
) -> EquipmentBooking:
    """Create equipment booking"""
    booking = EquipmentBooking(
        equipment_id=equipment_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking

async def get_equipment_usage_count(
    db: AsyncSession,
    equipment_id: int,
    days: int = 30
) -> int:
    """Get equipment usage count for prediction"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(EquipmentBooking).where(
            and_(
                EquipmentBooking.equipment_id == equipment_id,
                EquipmentBooking.start_time >= cutoff
            )
        )
    )
    return len(result.scalars().all())

async def get_current_energy_usage(db: AsyncSession, building: str) -> float:
    """Get current energy usage for building"""
    cutoff = datetime.utcnow() - timedelta(hours=1)
    result = await db.execute(
        select(EnergyLog)
        .where(and_(EnergyLog.building == building, EnergyLog.timestamp >= cutoff))
        .order_by(EnergyLog.timestamp.desc())
        .limit(1)
    )
    log = result.scalars().first()
    if not log:
        return 0.0
    consumption = getattr(log, "consumption", None)
    return float(consumption) if consumption is not None else 0.0


async def get_energy_consumption_series(
    db: AsyncSession,
    hours: int = 24,
    building: Optional[str] = None,
) -> List[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = select(EnergyLog).where(EnergyLog.timestamp >= cutoff)
    if building:
        query = query.where(EnergyLog.building == building)
    query = query.order_by(EnergyLog.timestamp.asc())

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "timestamp": log.timestamp,
            "building": log.building,
            "consumption": float(getattr(log, "consumption", 0.0) or 0.0),
        }
        for log in logs
    ]


async def get_energy_log_entries(db: AsyncSession, hours: int = 24, limit: int = 200) -> List[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(EnergyLog)
        .where(EnergyLog.timestamp >= cutoff)
        .order_by(EnergyLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "timestamp": log.timestamp,
            "building": log.building,
            "consumption": float(getattr(log, "consumption", 0.0) or 0.0),
            "savings_kwh": float(getattr(log, "savings_kwh", 0.0) or 0.0),
            "action": log.action,
        }
        for log in logs
    ]

async def get_empty_classrooms(db: AsyncSession, building: str) -> List[Classroom]:
    """Get currently empty classrooms in building"""
    current_time = datetime.utcnow().strftime("%H:%M")
    
    # Find booked classrooms now
    booked = select(ClassroomBooking.classroom_id).where(
        ClassroomBooking.time_slot == current_time
    )
    
    result = await db.execute(
        select(Classroom).where(
            and_(
                Classroom.building == building,
                Classroom.id.not_in(booked)
            )
        )
    )
    return result.scalars().all()

async def create_energy_log(
    db: AsyncSession,
    building: str,
    action: str,
    savings_kwh: float
) -> EnergyLog:
    """Create energy optimization log"""
    log = EnergyLog(
        building=building,
        action=action,
        savings_kwh=savings_kwh
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log

async def get_recent_energy_logs(db: AsyncSession, hours: int = 24) -> List[EnergyLog]:
    """Get recent energy logs"""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    result = await db.execute(
        select(EnergyLog).where(EnergyLog.timestamp >= cutoff)
    )
    return result.scalars().all()

async def get_historical_energy(db: AsyncSession, days: int = 30) -> List[EnergyLog]:
    """Get historical energy data for prediction"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    result = await db.execute(
        select(EnergyLog).where(EnergyLog.timestamp >= cutoff)
    )
    return result.scalars().all()

async def get_optimized_schedule(
    db: AsyncSession,
    date: Optional[str] = None,
    building: Optional[str] = None
) -> List[Classroom]:
    """Get optimized classroom schedule"""
    query = select(Classroom).join(ClassroomBooking).join(Course)
    
    if building:
        query = query.where(Classroom.building == building)
    
    if date:
        # Filter by date (expects YYYY-MM-DD)
        day = datetime.strptime(date, "%Y-%m-%d")
        start = day
        end = day + timedelta(days=1)
        query = query.where(and_(ClassroomBooking.date >= start, ClassroomBooking.date < end))
    
    result = await db.execute(query)
    return result.scalars().all()