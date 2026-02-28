
# src/models/schemas.py
from pydantic import BaseModel, Field, validator
from datetime import datetime, time
from typing import Optional, List, Dict, Any
from enum import Enum

class EventType(str, Enum):
    COURSE_CREATED = "course_created"
    EQUIPMENT_BOOKING = "equipment_booking"
    CLASSROOM_EMPTY = "classroom_empty"
    TIMETABLE_UPDATED = "timetable_updated"
    ENERGY_OPTIMIZATION = "energy_optimization"

class CourseCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    students_count: int = Field(..., gt=0, lt=500)
    schedule_time: str
    duration_minutes: int = Field(..., gt=0, le=240)
    preferred_building: Optional[str] = None
    
    @validator('schedule_time')
    def validate_time_format(cls, v):
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError('schedule_time must be in HH:MM format')
        return v

class EquipmentBooking(BaseModel):
    equipment_id: int
    user_id: str
    time_slot: str
    duration_hours: float = Field(..., gt=0, le=8)
    
    @validator('time_slot')
    def validate_datetime(cls, v):
        try:
            datetime.fromisoformat(v)
        except ValueError:
            raise ValueError('time_slot must be ISO format datetime')
        return v

class Classroom(BaseModel):
    id: int
    name: str
    capacity: int
    building: str
    has_projector: bool = False
    has_lab_equipment: bool = False

class Equipment(BaseModel):
    id: int
    name: str
    lab: str
    status: str
    last_maintenance: Optional[datetime]

class AgentResponse(BaseModel):
    status: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    fallback_used: bool = False

class HealthCheck(BaseModel):
    status: str
    database: str
    redis: str
    agents: Dict[str, str]