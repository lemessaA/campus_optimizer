# src/database/crud.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from datetime import datetime, timedelta
from typing import List, Optional

from src.database.models import (
    Classroom, Course, Equipment, 
    EquipmentBooking, ClassroomBooking, EnergyLog
)

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
    # Implementation would query sensors/API
    return 100.0  # Mock value

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
        # Filter by date if provided
        query = query.where(ClassroomBooking.date == date)
    
    result = await db.execute(query)
    return result.scalars().all()