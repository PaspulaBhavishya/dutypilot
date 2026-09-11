from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

class TimeSlot(Base):
    __tablename__ = "time_slots"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    start_time = Column(String, nullable=False) # e.g., "08:15"
    end_time = Column(String, nullable=False)   # e.g., "10:15"

class Faculty(Base):
    __tablename__ = "faculty"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False) # BOA, Senior, Fresher
    department = Column(String, nullable=False)
    primary_year = Column(Integer, nullable=False) # 1, 2, 3, 4
    experience_years = Column(Integer, nullable=False)
    max_slots = Column(Integer, nullable=False) # derived (e.g. 2, 3, 4)
    is_simulated_unavailable = Column(Boolean, default=False, nullable=False)

    timetable = relationship("FacultyTimetable", back_populates="faculty", cascade="all, delete-orphan")
    duties = relationship("DutyAssignment", back_populates="faculty", cascade="all, delete-orphan")

class FacultyTimetable(Base):
    __tablename__ = "faculty_timetable"

    id = Column(Integer, primary_key=True, index=True)
    faculty_id = Column(Integer, ForeignKey("faculty.id"), nullable=False)
    day_of_week = Column(String, nullable=False) # Monday, Tuesday, ...
    class_name = Column(String, default="Lecture", nullable=True)
    start_time = Column(String, nullable=False) # e.g. "09:30" (24hr format)
    end_time = Column(String, nullable=False)   # e.g. "10:30" (24hr format)
    slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=True) # Optional legacy mapping
    is_teaching = Column(Boolean, default=True, nullable=False)

    faculty = relationship("Faculty", back_populates="timetable")
    slot = relationship("TimeSlot")

class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    course_code = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    year = Column(Integer, nullable=False) # 1, 2, 3, 4
    date = Column(String, nullable=False) # YYYY-MM-DD
    slot_id = Column(Integer, ForeignKey("time_slots.id"), nullable=False)
    start_time = Column(String, nullable=True) # e.g. "09:30", falls back to slot.start_time
    end_time = Column(String, nullable=True)   # e.g. "12:30", falls back to slot.end_time
    required_invigilators = Column(Integer, nullable=False)

    slot = relationship("TimeSlot")
    assignments = relationship("DutyAssignment", back_populates="exam", cascade="all, delete-orphan")

class DutyAssignment(Base):
    __tablename__ = "duty_assignments"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    faculty_id = Column(Integer, ForeignKey("faculty.id"), nullable=False)
    suitability_score = Column(Integer, nullable=False)
    status = Column(String, nullable=False) # Assigned, Backup, Avoided
    rejection_reason = Column(String, nullable=True)
    score_breakdown = Column(String, nullable=True) # JSON String: {"tier_score": 70, ...}

    exam = relationship("Exam", back_populates="assignments")
    faculty = relationship("Faculty", back_populates="duties")
