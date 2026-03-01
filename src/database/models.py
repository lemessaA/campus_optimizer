# src/database/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Classroom(Base):
    __tablename__ = "classrooms"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    capacity = Column(Integer, nullable=False)
    building = Column(String, nullable=False)
    has_projector = Column(Boolean, default=False)
    has_lab_equipment = Column(Boolean, default=False)
    
    bookings = relationship("ClassroomBooking", back_populates="classroom")

    def dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "capacity": self.capacity,
            "building": self.building,
            "has_projector": bool(self.has_projector),
            "has_lab_equipment": bool(self.has_lab_equipment),
        }

class Course(Base):
    __tablename__ = "courses"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    students_count = Column(Integer, nullable=False)
    schedule_time = Column(String, nullable=False)
    duration_minutes = Column(Integer, default=60)
    preferred_building = Column(String, nullable=True)
    
    bookings = relationship("ClassroomBooking", back_populates="course")

class ClassroomBooking(Base):
    __tablename__ = "classroom_bookings"
    
    id = Column(Integer, primary_key=True)
    classroom_id = Column(Integer, ForeignKey("classrooms.id"))
    course_id = Column(Integer, ForeignKey("courses.id"))
    time_slot = Column(String, nullable=False)
    date = Column(DateTime, default=datetime.utcnow)
    
    classroom = relationship("Classroom", back_populates="bookings")
    course = relationship("Course", back_populates="bookings")

class Equipment(Base):
    __tablename__ = "equipment"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    lab = Column(String, nullable=False)
    status = Column(String, default="available")
    last_maintenance = Column(DateTime, nullable=True)
    
    bookings = relationship("EquipmentBooking", back_populates="equipment")

class EquipmentBooking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id"))
    user_id = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    
    equipment = relationship("Equipment", back_populates="bookings")

class EnergyLog(Base):
    __tablename__ = "energy_logs"
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    building = Column(String, nullable=False)
    consumption = Column(Float, default=0.0)
    savings_kwh = Column(Float, default=0.0)
    action = Column(String, nullable=True)
# src/database/models.py (add these models)

class SupportTicket(Base):
    __tablename__ = "support_tickets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    description = Column(String, nullable=False)
    priority = Column(Integer, default=1)  # 1-4: low to urgent
    status = Column(String, default="open")  # open, in_progress, resolved, closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    assigned_to = Column(String, nullable=True)
    context = Column(JSON, nullable=True)  # Store context from other agents

class TicketUpdate(Base):
    __tablename__ = "ticket_updates"
    
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"))
    message = Column(String, nullable=False)
    update_type = Column(String, default="comment")  # comment, status_change, assignment, escalation
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=True)  # user or agent

class SupportFeedback(Base):
    __tablename__ = "support_feedback"
    
    id = Column(Integer, primary_key=True)
    query_id = Column(String, nullable=True)
    ticket_id = Column(Integer, ForeignKey("support_tickets.id"), nullable=True)
    rating = Column(Integer)  # 1-5
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)