
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
    ANALYTICS_REPORT = "analytics_report"
    HEALTH_CHECK = "health_check"
    INSIGHTS_REPORT = "insights_report"

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


class ScheduleEntry(BaseModel):
    time: str
    course_name: str
    classroom_name: str
    classroom_capacity: int
    building: str
    students_count: int
    utilization_rate: float

class Equipment(BaseModel):
    id: int
    name: str
    lab: str
    status: str
    last_maintenance: Optional[datetime]


class EquipmentBookingEntry(BaseModel):
    id: int
    equipment_id: int
    equipment_name: str
    user_id: str
    start_time: datetime
    end_time: datetime


class EnergyLogEntry(BaseModel):
    timestamp: datetime
    building: str
    consumption: float
    savings_kwh: float
    action: Optional[str] = None


class EnergyConsumptionPoint(BaseModel):
    timestamp: datetime
    building: str
    consumption: float


class TicketUpdateEntry(BaseModel):
    timestamp: datetime
    message: str
    type: str


class SupportTicketEntry(BaseModel):
    id: int
    category: str
    status: str
    priority: int
    created_at: datetime
    updated_at: datetime


class SupportQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = Field(None, max_length=100)


class TicketCategory(str, Enum):
    SCHEDULING = "scheduling"
    EQUIPMENT = "equipment"
    FACILITIES = "facilities"
    ENERGY = "energy"
    ACCOUNT = "account"
    GENERAL = "general"


class TicketCreateRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=5000)
    priority: Optional[int] = Field(None, ge=1, le=4)


class TicketEscalateRequest(BaseModel):
    reason: str
    user_id: Optional[str] = None


class FAQEntry(BaseModel):
    id: str
    question: str
    answer: str
    category: str

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


class EventPayload(BaseModel):
    """Validated payload for POST /events. Extensible per event_type."""
    report_type: Optional[str] = Field(None, max_length=50)
    domain: Optional[str] = Field(None, max_length=50)
    building: Optional[str] = Field(None, max_length=100)
    # Allow extra fields for event-specific data (e.g. course, booking)
    class Config:
        extra = "allow"