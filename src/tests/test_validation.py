# src/tests/test_validation.py
"""Tests for input validation and schema constraints."""
import pytest
from pydantic import ValidationError

from src.models.schemas import (
    CourseCreate,
    EquipmentBooking,
    SupportQueryRequest,
    TicketCreateRequest,
    EventPayload,
)


def test_course_create_valid():
    c = CourseCreate(
        name="CS101",
        students_count=50,
        schedule_time="10:00",
        duration_minutes=60,
    )
    assert c.name == "CS101"
    assert c.schedule_time == "10:00"


def test_course_create_invalid_time():
    with pytest.raises(ValidationError):
        CourseCreate(
            name="CS101",
            students_count=50,
            schedule_time="25:00",
            duration_minutes=60,
        )


def test_course_create_name_too_short():
    with pytest.raises(ValidationError):
        CourseCreate(
            name="AB",
            students_count=50,
            schedule_time="10:00",
            duration_minutes=60,
        )


def test_equipment_booking_valid():
    b = EquipmentBooking(
        equipment_id=1,
        user_id="user1",
        time_slot="2024-01-15T10:00:00",
        duration_hours=2,
    )
    assert b.equipment_id == 1


def test_equipment_booking_invalid_timeslot():
    with pytest.raises(ValidationError):
        EquipmentBooking(
            equipment_id=1,
            user_id="user1",
            time_slot="invalid",
            duration_hours=2,
        )


def test_support_query_request_max_length():
    with pytest.raises(ValidationError):
        SupportQueryRequest(query="")  # min_length=1


def test_ticket_create_request_validation():
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            user_id="",
            category="scheduling",
            description="Test",
        )


def test_event_payload_extra_fields():
    p = EventPayload(building="Engineering", custom_field="allowed")
    assert p.building == "Engineering"
    assert p.model_dump().get("custom_field") == "allowed"
