import io
import csv
import json
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import pandas as pd

from .database import engine, Base, get_db
from .models import Department, TimeSlot, Faculty, FacultyTimetable, Exam, DutyAssignment
from .schemas import (
    DepartmentCreate, DepartmentResponse,
    TimeSlotCreate, TimeSlotResponse,
    FacultyCreate, FacultyResponse,
    ExamCreate, ExamResponse,
    DutyAssignmentResponse, ExamWithAssignmentsResponse,
    SimulationToggle, ScenarioComparisonResponse
)
from .scheduler import solve_allocation

# Create Tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DutyPilot API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Department Endpoints ---
@app.get("/api/departments", response_model=List[DepartmentResponse])
def get_departments(db: Session = Depends(get_db)):
    return db.query(Department).all()

@app.post("/api/departments", response_model=DepartmentResponse)
def create_department(dept: DepartmentCreate, db: Session = Depends(get_db)):
    db_dept = db.query(Department).filter(Department.name == dept.name).first()
    if db_dept:
        raise HTTPException(status_code=400, detail="Department already exists.")
    new_dept = Department(name=dept.name)
    db.add(new_dept)
    db.commit()
    db.refresh(new_dept)
    return new_dept

@app.delete("/api/departments/{dept_id}")
def delete_department(dept_id: int, db: Session = Depends(get_db)):
    dept = db.query(Department).filter(Department.id == dept_id).first()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")
    db.delete(dept)
    db.commit()
    return {"detail": "Department deleted successfully"}

# --- Time Slot Endpoints ---
@app.get("/api/slots", response_model=List[TimeSlotResponse])
def get_slots(db: Session = Depends(get_db)):
    return db.query(TimeSlot).all()

@app.post("/api/slots", response_model=TimeSlotResponse)
def create_slot(slot: TimeSlotCreate, db: Session = Depends(get_db)):
    db_slot = db.query(TimeSlot).filter(TimeSlot.name == slot.name).first()
    if db_slot:
        raise HTTPException(status_code=400, detail="Time Slot already exists.")
    new_slot = TimeSlot(name=slot.name, start_time=slot.start_time, end_time=slot.end_time)
    db.add(new_slot)
    db.commit()
    db.refresh(new_slot)
    return new_slot

@app.delete("/api/slots/{slot_id}")
def delete_slot(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="Time Slot not found.")
    db.delete(slot)
    db.commit()
    return {"detail": "Time Slot deleted successfully"}

# --- Faculty Endpoints ---
@app.get("/api/faculty", response_model=List[FacultyResponse])
def get_faculty(db: Session = Depends(get_db)):
    return db.query(Faculty).all()

@app.post("/api/faculty", response_model=FacultyResponse)
def create_faculty(fac: FacultyCreate, db: Session = Depends(get_db)):
    # Calculate max slots based on role
    role_slots = {"BOA": 2, "Senior": 3, "Fresher": 4}
    max_slots = role_slots.get(fac.role, 3)
    
    new_fac = Faculty(
        name=fac.name,
        email=fac.email,
        role=fac.role,
        department=fac.department,
        primary_year=fac.primary_year,
        experience_years=fac.experience_years,
        max_slots=max_slots
    )
    db.add(new_fac)
    db.commit()
    db.refresh(new_fac)
    
    # Initialize timetable entries for all slots and week days
    slots = db.query(TimeSlot).all()
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    for day in days:
        for s in slots:
            tt = FacultyTimetable(faculty_id=new_fac.id, day_of_week=day, slot_id=s.id, is_teaching=False)
            db.add(tt)
    db.commit()
    db.refresh(new_fac)
    return new_fac

@app.delete("/api/faculty/{fac_id}")
def delete_faculty(fac_id: int, db: Session = Depends(get_db)):
    fac = db.query(Faculty).filter(Faculty.id == fac_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Faculty not found.")
    db.delete(fac)
    db.commit()
    return {"detail": "Faculty deleted successfully"}

# Toggle simulated unavailable status
@app.post("/api/faculty/toggle-simulation")
def toggle_simulation(payload: SimulationToggle, db: Session = Depends(get_db)):
    db.query(Faculty).filter(Faculty.id.in_(payload.faculty_ids)).update(
        {Faculty.is_simulated_unavailable: payload.is_unavailable},
        synchronize_session=False
    )
    db.commit()
    return {"detail": "Simulated unavailability updated."}

@app.post("/api/faculty/clear-simulation")
def clear_simulation(db: Session = Depends(get_db)):
    db.query(Faculty).update({Faculty.is_simulated_unavailable: False}, synchronize_session=False)
    db.commit()
    return {"detail": "Simulated unavailability cleared for all faculty."}

# --- Timetable Endpoints ---
@app.get("/api/timetable/{fac_id}")
def get_faculty_timetable(fac_id: int, db: Session = Depends(get_db)):
    timetable = db.query(FacultyTimetable).filter(FacultyTimetable.faculty_id == fac_id).all()
    res = []
    for item in timetable:
        res.append({
            "id": item.id,
            "day_of_week": item.day_of_week,
            "slot_id": item.slot_id,
            "slot_name": item.slot.name if item.slot else f"Slot {item.slot_id}",
            "is_teaching": item.is_teaching
        })
    return res

@app.put("/api/timetable/{fac_id}")
def update_faculty_timetable(fac_id: int, schedule: List[dict], db: Session = Depends(get_db)):
    # schedule contains: [{"day_of_week": "Monday", "slot_id": 1, "is_teaching": true}]
    for item in schedule:
        db.query(FacultyTimetable).filter(
            FacultyTimetable.faculty_id == fac_id,
            FacultyTimetable.day_of_week == item["day_of_week"],
            FacultyTimetable.slot_id == item["slot_id"]
        ).update({FacultyTimetable.is_teaching: item["is_teaching"]})
    db.commit()
    return {"detail": "Timetable updated successfully"}

# --- Exam Endpoints ---
@app.get("/api/exams", response_model=List[ExamResponse])
def get_exams(db: Session = Depends(get_db)):
    return db.query(Exam).all()

@app.post("/api/exams", response_model=ExamResponse)
def create_exam(exam: ExamCreate, db: Session = Depends(get_db)):
    new_exam = Exam(
        course_code=exam.course_code,
        course_name=exam.course_name,
        department=exam.department,
        year=exam.year,
        date=exam.date,
        slot_id=exam.slot_id,
        required_invigilators=exam.required_invigilators
    )
    db.add(new_exam)
    db.commit()
    db.refresh(new_exam)
    return new_exam

@app.delete("/api/exams/{exam_id}")
def delete_exam(exam_id: int, db: Session = Depends(get_db)):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found.")
    db.delete(exam)
    db.commit()
    return {"detail": "Exam deleted successfully"}

# --- Allocation/Optimization Endpoints ---
@app.post("/api/allocations/run")
def run_allocation(db: Session = Depends(get_db)):
    res = solve_allocation(db, is_simulation=False)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.post("/api/allocations/simulate")
def run_simulation(db: Session = Depends(get_db)):
    # Runs the solver in simulation mode respecting is_simulated_unavailable fields
    res = solve_allocation(db, is_simulation=True)
    if res["status"] == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@app.get("/api/allocations/current", response_model=List[ExamWithAssignmentsResponse])
def get_current_roster(db: Session = Depends(get_db)):
    exams = db.query(Exam).all()
    res = []
    for e in exams:
        assignments = db.query(DutyAssignment).filter(
            DutyAssignment.exam_id == e.id
        ).all()
        
        assigns_res = []
        for a in assignments:
            assigns_res.append(DutyAssignmentResponse(
                id=a.id,
                exam_id=a.exam_id,
                faculty_id=a.faculty_id,
                faculty_name=a.faculty.name if a.faculty else "Unknown",
                faculty_role=a.faculty.role if a.faculty else "Fresher",
                faculty_department=a.faculty.department if a.faculty else "ACSE",
                faculty_primary_year=a.faculty.primary_year if a.faculty else 1,
                suitability_score=a.suitability_score,
                status=a.status,
                rejection_reason=a.rejection_reason,
                score_breakdown=json.loads(a.score_breakdown) if a.score_breakdown else {}
            ))
            
        res.append(ExamWithAssignmentsResponse(
            id=e.id,
            course_code=e.course_code,
            course_name=e.course_name,
            department=e.department,
            year=e.year,
            date=e.date,
            slot=e.slot,
            required_invigilators=e.required_invigilators,
            assignments=assigns_res
        ))
    return res

@app.get("/api/allocations/export")
def export_roster(db: Session = Depends(get_db)):
    exams = db.query(Exam).all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write CSV Header
    writer.writerow([
        "Exam Date", "Time Slot", "Course Code", "Course Name", "Exam Dept", "Exam Year",
        "Faculty Name", "Faculty Role", "Faculty Dept", "Faculty Primary Year", 
        "Suitability Score", "Status", "Reason for Backup/Avoided"
    ])
    
    for e in exams:
        assignments = db.query(DutyAssignment).filter(DutyAssignment.exam_id == e.id).all()
        slot_name = e.slot.name if e.slot else f"Slot {e.slot_id}"
        slot_times = f"{e.slot.start_time}-{e.slot.end_time}" if e.slot else ""
        
        for a in assignments:
            writer.writerow([
                e.date,
                f"{slot_name} ({slot_times})",
                e.course_code,
                e.course_name,
                e.department,
                f"{e.year}rd/th Year" if e.year > 1 else f"{e.year}st/nd Year",
                a.faculty.name if a.faculty else "N/A",
                a.faculty.role if a.faculty else "N/A",
                a.faculty.department if a.faculty else "N/A",
                a.faculty.primary_year if a.faculty else "N/A",
                a.suitability_score,
                a.status,
                a.rejection_reason or ""
            ])
            
    output.seek(0)
    headers = {
        "Content-Disposition": 'attachment; filename="dutypilot_invigilation_roster.csv"'
    }
    return StreamingResponse(output, media_type="text/csv", headers=headers)

# --- Excel / CSV Upload Endpoint ---
@app.post("/api/allocations/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    filename = file.filename.lower()
    
    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            # Excel file with sheets: "Faculty", "Exams", "Timetable"
            xls = pd.ExcelFile(io.BytesIO(contents))
            
            # 1. Parse Departments if sheet exists, or extract from faculty
            if "Faculty" in xls.sheet_names:
                df_fac = pd.read_excel(xls, "Faculty")
                # Seed departments from the unique values in Excel
                unique_depts = df_fac["Department"].dropna().unique()
                for d_name in unique_depts:
                    d_name = str(d_name).strip()
                    if not db.query(Department).filter(Department.name == d_name).first():
                        db.add(Department(name=d_name))
                db.commit()
                
                # Delete existing faculty and timetables before reloading
                db.query(FacultyTimetable).delete()
                db.query(DutyAssignment).delete()
                db.query(Faculty).delete()
                db.commit()
                
                role_slots = {"BOA": 2, "Senior": 3, "Fresher": 4}
                for _, row in df_fac.iterrows():
                    role = str(row["Role"]).strip()
                    max_slots = role_slots.get(role, 3)
                    
                    fac = Faculty(
                        name=str(row["Name"]).strip(),
                        email=str(row["Email"]).strip(),
                        role=role,
                        department=str(row["Department"]).strip(),
                        primary_year=int(row["Primary Year"]),
                        experience_years=int(row["Experience Years"]),
                        max_slots=max_slots
                    )
                    db.add(fac)
                db.commit()
                
            # 2. Parse Exams
            if "Exams" in xls.sheet_names:
                df_ex = pd.read_excel(xls, "Exams")
                # Make sure we clear existing exams
                db.query(Exam).delete()
                db.commit()
                
                for _, row in df_ex.iterrows():
                    slot_name = str(row["Slot Name"]).strip()
                    # Check if slot exists or create dynamic timeslot
                    db_slot = db.query(TimeSlot).filter(TimeSlot.name == slot_name).first()
                    if not db_slot:
                        # Define a default range if it's missing from db
                        db_slot = TimeSlot(name=slot_name, start_time="08:15", end_time="10:15")
                        db.add(db_slot)
                        db.commit()
                        db.refresh(db_slot)
                        
                    ex = Exam(
                        course_code=str(row["Course Code"]).strip(),
                        course_name=str(row["Course Name"]).strip(),
                        department=str(row["Department"]).strip(),
                        year=int(row["Year"]),
                        date=str(row["Date"]).split(" ")[0].strip(), # YYYY-MM-DD format
                        slot_id=db_slot.id,
                        required_invigilators=int(row["Required Invigilators"])
                    )
                    db.add(ex)
                db.commit()
                
            # 3. Parse Timetables
            # Initialize default (empty) timetable slots for all loaded faculty
            all_faculty = db.query(Faculty).all()
            all_slots = db.query(TimeSlot).all()
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            for f in all_faculty:
                for day in days:
                    for s in all_slots:
                        tt = FacultyTimetable(faculty_id=f.id, day_of_week=day, slot_id=s.id, is_teaching=False)
                        db.add(tt)
            db.commit()

            if "Timetable" in xls.sheet_names:
                df_tt = pd.read_excel(xls, "Timetable")
                # Expects columns: Faculty Email, Day of Week, Slot Name, Is Teaching (1/0 or Yes/No)
                for _, row in df_tt.iterrows():
                    email = str(row["Faculty Email"]).strip()
                    day = str(row["Day of Week"]).strip()
                    slot_n = str(row["Slot Name"]).strip()
                    is_t = str(row["Is Teaching"]).strip().lower() in ("1", "1.0", "true", "yes", "teaching")
                    
                    fac = db.query(Faculty).filter(Faculty.email == email).first()
                    slot = db.query(TimeSlot).filter(TimeSlot.name == slot_n).first()
                    if fac and slot:
                        db.query(FacultyTimetable).filter(
                            FacultyTimetable.faculty_id == fac.id,
                            FacultyTimetable.day_of_week == day,
                            FacultyTimetable.slot_id == slot.id
                        ).update({FacultyTimetable.is_teaching: is_t})
                db.commit()
                
            return {"detail": "Excel file uploaded and parsed successfully."}
            
        else:
            raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are currently supported.")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

# Mount frontend files at the root
# In standard deployment, the HTML dashboard will be served directly by FastAPI.
# We will read index.html and return it.
@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>DutyPilot Dashboard index.html not found.</h1><p>Ensure it exists under frontend/index.html</p>")
