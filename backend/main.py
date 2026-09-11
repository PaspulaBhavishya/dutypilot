import io
import csv
import json
import os
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
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
    FacultyTimetableCreate, FacultyTimetableResponse,
    ExamCreate, ExamResponse,
    DutyAssignmentResponse, ExamWithAssignmentsResponse,
    SimulationToggle, ScenarioComparisonResponse
)
from .scheduler import solve_allocation
from .parsers import (
    parse_pdf_timetable,
    parse_docx_timetable,
    parse_excel_or_csv_timetable
)

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
            "class_name": item.class_name or "Lecture",
            "start_time": item.start_time,
            "end_time": item.end_time,
            "is_teaching": item.is_teaching
        })
    return res

@app.post("/api/timetable/{fac_id}/classes")
def add_faculty_class(fac_id: int, payload: dict, db: Session = Depends(get_db)):
    """Adds a new daily class period for a faculty member."""
    fac = db.query(Faculty).filter(Faculty.id == fac_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Faculty not found.")
        
    new_class = FacultyTimetable(
        faculty_id=fac_id,
        day_of_week=payload.get("day_of_week", "Monday"),
        class_name=payload.get("class_name", "Lecture"),
        start_time=payload.get("start_time", "09:30"),
        end_time=payload.get("end_time", "10:30"),
        is_teaching=True
    )
    db.add(new_class)
    db.commit()
    db.refresh(new_class)
    return {"detail": "Class period added successfully", "id": new_class.id}

@app.delete("/api/timetable/classes/{class_id}")
def delete_faculty_class(class_id: int, db: Session = Depends(get_db)):
    """Deletes a specific class period."""
    item = db.query(FacultyTimetable).filter(FacultyTimetable.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Class period not found.")
    db.delete(item)
    db.commit()
    return {"detail": "Class period deleted successfully"}

# Document Upload for Timetables (PDF, DOCX, XLSX, CSV)
@app.post("/api/timetable/upload")
async def upload_timetable_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    filename = file.filename.lower()
    
    extracted_classes = []
    try:
        if filename.endswith(".pdf"):
            extracted_classes = parse_pdf_timetable(contents)
        elif filename.endswith(".docx") or filename.endswith(".doc"):
            extracted_classes = parse_docx_timetable(contents)
        elif filename.endswith(".xlsx") or filename.endswith(".xls") or filename.endswith(".csv"):
            extracted_classes = parse_excel_or_csv_timetable(contents, filename)
        else:
            raise HTTPException(status_code=400, detail="Supported formats: .pdf, .docx, .xlsx, .csv")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse document: {str(e)}")
        
    if not extracted_classes:
        raise HTTPException(status_code=400, detail="No readable class timetable entries found in file.")
        
    # Match faculty and insert into database
    all_faculty = db.query(Faculty).all()
    inserted_count = 0
    
    for item in extracted_classes:
        fac_id_str = item["faculty_identifier"].strip().lower()
        
        # Match by email or name
        matched_fac = None
        for f in all_faculty:
            if f.email.lower() in fac_id_str or fac_id_str in f.email.lower():
                matched_fac = f
                break
            if f.name.lower() in fac_id_str or fac_id_str in f.name.lower():
                matched_fac = f
                break
                
        if matched_fac:
            tt = FacultyTimetable(
                faculty_id=matched_fac.id,
                day_of_week=item["day_of_week"],
                class_name=item["class_name"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                is_teaching=item["is_teaching"]
            )
            db.add(tt)
            inserted_count += 1
            
    db.commit()
    return {
        "detail": f"Successfully parsed and loaded {inserted_count} class periods across faculty schedules.",
        "total_parsed": len(extracted_classes),
        "inserted_count": inserted_count
    }

# --- Exam Endpoints ---
@app.get("/api/exams", response_model=List[ExamResponse])
def get_exams(db: Session = Depends(get_db)):
    return db.query(Exam).all()

@app.post("/api/exams", response_model=ExamResponse)
def create_exam(exam: ExamCreate, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == exam.slot_id).first()
    start_t = exam.start_time or (slot.start_time if slot else "08:15")
    end_t = exam.end_time or (slot.end_time if slot else "10:15")
    
    new_exam = Exam(
        course_code=exam.course_code,
        course_name=exam.course_name,
        department=exam.department,
        year=exam.year,
        date=exam.date,
        slot_id=exam.slot_id,
        start_time=start_t,
        end_time=end_t,
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
            start_time=e.start_time or (e.slot.start_time if e.slot else "08:15"),
            end_time=e.end_time or (e.slot.end_time if e.slot else "10:15"),
            required_invigilators=e.required_invigilators,
            assignments=assigns_res
        ))
    return res

@app.get("/api/allocations/export")
def export_roster(db: Session = Depends(get_db)):
    exams = db.query(Exam).all()
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow([
        "Exam Date", "Exam Time Window", "Time Slot", "Course Code", "Course Name", "Exam Dept", "Exam Year",
        "Faculty Name", "Faculty Role", "Faculty Dept", "Faculty Primary Year", 
        "Suitability Score", "Status", "Reason for Backup/Avoided"
    ])
    
    for e in exams:
        assignments = db.query(DutyAssignment).filter(DutyAssignment.exam_id == e.id).all()
        slot_name = e.slot.name if e.slot else f"Slot {e.slot_id}"
        e_start = e.start_time or (e.slot.start_time if e.slot else "")
        e_end = e.end_time or (e.slot.end_time if e.slot else "")
        time_window = f"{e_start} - {e_end}"
        
        for a in assignments:
            writer.writerow([
                e.date,
                time_window,
                slot_name,
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

# Sample Document Downloads
@app.get("/api/timetable/sample/{file_format}")
def download_sample_timetable(file_format: str):
    file_format = file_format.lower()
    path = f"sample_timetable.{file_format}"
    if os.path.exists(path):
        media_types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        }
        return FileResponse(path, media_type=media_types.get(file_format, "application/octet-stream"), filename=path)
    raise HTTPException(status_code=404, detail="Sample file not found.")

# Excel / CSV Full Dataset Upload
@app.post("/api/allocations/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    contents = await file.read()
    filename = file.filename.lower()
    
    try:
        if filename.endswith(".xlsx") or filename.endswith(".xls"):
            xls = pd.ExcelFile(io.BytesIO(contents))
            
            if "Faculty" in xls.sheet_names:
                df_fac = pd.read_excel(xls, "Faculty")
                unique_depts = df_fac["Department"].dropna().unique()
                for d_name in unique_depts:
                    d_name = str(d_name).strip()
                    if not db.query(Department).filter(Department.name == d_name).first():
                        db.add(Department(name=d_name))
                db.commit()
                
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
                
            if "Exams" in xls.sheet_names:
                df_ex = pd.read_excel(xls, "Exams")
                db.query(Exam).delete()
                db.commit()
                
                for _, row in df_ex.iterrows():
                    slot_name = str(row["Slot Name"]).strip()
                    db_slot = db.query(TimeSlot).filter(TimeSlot.name == slot_name).first()
                    if not db_slot:
                        db_slot = TimeSlot(name=slot_name, start_time="08:15", end_time="10:15")
                        db.add(db_slot)
                        db.commit()
                        db.refresh(db_slot)
                        
                    ex = Exam(
                        course_code=str(row["Course Code"]).strip(),
                        course_name=str(row["Course Name"]).strip(),
                        department=str(row["Department"]).strip(),
                        year=int(row["Year"]),
                        date=str(row["Date"]).split(" ")[0].strip(),
                        slot_id=db_slot.id,
                        start_time=db_slot.start_time,
                        end_time=db_slot.end_time,
                        required_invigilators=int(row["Required Invigilators"])
                    )
                    db.add(ex)
                db.commit()
                
            if "Timetable" in xls.sheet_names:
                df_tt = pd.read_excel(xls, "Timetable")
                for _, row in df_tt.iterrows():
                    email = str(row.get("Faculty Email", "")).strip()
                    day = str(row.get("Day of Week", "Monday")).strip()
                    subject = str(row.get("Subject", row.get("Class Name", "Lecture"))).strip()
                    st = str(row.get("Start Time", "09:30")).strip()
                    et = str(row.get("End Time", "10:30")).strip()
                    
                    fac = db.query(Faculty).filter(Faculty.email == email).first()
                    if fac:
                        tt = FacultyTimetable(
                            faculty_id=fac.id,
                            day_of_week=day,
                            class_name=subject,
                            start_time=st,
                            end_time=et,
                            is_teaching=True
                        )
                        db.add(tt)
                db.commit()
                
            return {"detail": "Excel file uploaded and parsed successfully."}
        else:
            raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported here.")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    try:
        with open("frontend/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>DutyPilot Dashboard index.html not found.</h1>")
