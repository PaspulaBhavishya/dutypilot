from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict

# Department Schemas
class DepartmentBase(BaseModel):
    name: str

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: int

    class Config:
        from_attributes = True

# TimeSlot Schemas
class TimeSlotBase(BaseModel):
    name: str
    start_time: str
    end_time: str

class TimeSlotCreate(TimeSlotBase):
    pass

class TimeSlotResponse(TimeSlotBase):
    id: int

    class Config:
        from_attributes = True

# Faculty Timetable Schemas
class FacultyTimetableBase(BaseModel):
    day_of_week: str
    slot_id: int
    is_teaching: bool

class FacultyTimetableCreate(FacultyTimetableBase):
    pass

class FacultyTimetableResponse(FacultyTimetableBase):
    id: int
    slot: Optional[TimeSlotResponse] = None

    class Config:
        from_attributes = True

# Faculty Schemas
class FacultyBase(BaseModel):
    name: str
    email: str
    role: str # BOA, Senior, Fresher
    department: str
    primary_year: int
    experience_years: int

class FacultyCreate(FacultyBase):
    pass

class FacultyResponse(FacultyBase):
    id: int
    max_slots: int
    is_simulated_unavailable: bool
    timetable: List[FacultyTimetableResponse] = []

    class Config:
        from_attributes = True

# Exam Schemas
class ExamBase(BaseModel):
    course_code: str
    course_name: str
    department: str
    year: int
    date: str
    slot_id: int
    required_invigilators: int

class ExamCreate(ExamBase):
    pass

class ExamResponse(ExamBase):
    id: int
    slot: Optional[TimeSlotResponse] = None

    class Config:
        from_attributes = True

# Duty Assignment Schemas
class DutyAssignmentResponse(BaseModel):
    id: int
    exam_id: int
    faculty_id: int
    faculty_name: str
    faculty_role: str
    faculty_department: str
    faculty_primary_year: int
    suitability_score: int
    status: str # Assigned, Backup, Avoided
    rejection_reason: Optional[str] = None
    score_breakdown: Optional[Dict] = None

    class Config:
        from_attributes = True

class ExamWithAssignmentsResponse(BaseModel):
    id: int
    course_code: str
    course_name: str
    department: str
    year: int
    date: str
    slot: Optional[TimeSlotResponse] = None
    required_invigilators: int
    assignments: List[DutyAssignmentResponse] = []

    class Config:
        from_attributes = True

class SimulationToggle(BaseModel):
    faculty_ids: List[int]
    is_unavailable: bool

class ScenarioComparisonResponse(BaseModel):
    scenario_name: str
    total_exams: int
    assigned_count: int
    required_count: int
    success_rate: float
    conflicts_count: int
    cross_year_assignments: int
    shortages: Dict[str, int] # course_code -> missing count
    assignments: List[DutyAssignmentResponse] = []
