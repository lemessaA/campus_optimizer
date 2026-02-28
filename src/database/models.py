# src/database/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Float
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