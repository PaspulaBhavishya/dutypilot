from sqlalchemy.orm import Session
from .database import engine, Base, SessionLocal
from .models import Department, TimeSlot, Faculty, FacultyTimetable, Exam, DutyAssignment

def seed_database():
    db = SessionLocal()
    
    # 1. Clear database
    print("Recreating database tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # 2. Seed Departments
    print("Seeding departments...")
    departments = ["ACSE", "ECE", "EEE", "MECH"]
    for dept_name in departments:
        db.add(Department(name=dept_name))
    db.commit()

    # 3. Seed Time Slots (8:15 AM to 4:00 PM, 4 slots)
    print("Seeding slots...")
    slots_data = [
        {"name": "Slot 1", "start_time": "08:15", "end_time": "10:15"},
        {"name": "Slot 2", "start_time": "10:15", "end_time": "12:15"},
        {"name": "Slot 3", "start_time": "12:15", "end_time": "14:15"},
        {"name": "Slot 4", "start_time": "14:15", "end_time": "16:00"},
    ]
    slots = []
    for s_data in slots_data:
        slot = TimeSlot(**s_data)
        db.add(slot)
        slots.append(slot)
    db.commit()
    # Refresh slots to get IDs
    slots = db.query(TimeSlot).all()

    # 4. Seed Faculty (16 faculty members)
    print("Seeding faculty...")
    # Roles: BOA (max 2 slots), Senior (max 3 slots), Fresher (max 4 slots)
    faculty_data = [
        # ACSE Faculty (7 available)
        {"name": "Dr. Ramesh (ACSE)", "email": "ramesh@acse.edu", "role": "BOA", "department": "ACSE", "primary_year": 3, "experience_years": 15, "max_slots": 2},
        {"name": "Dr. Sunitha (ACSE)", "email": "sunitha@acse.edu", "role": "Senior", "department": "ACSE", "primary_year": 3, "experience_years": 8, "max_slots": 3},
        {"name": "Mr. Anil (ACSE)", "email": "anil@acse.edu", "role": "Fresher", "department": "ACSE", "primary_year": 3, "experience_years": 2, "max_slots": 4},
        {"name": "Dr. Prasad (ACSE)", "email": "prasad@acse.edu", "role": "Senior", "department": "ACSE", "primary_year": 2, "experience_years": 6, "max_slots": 3},
        {"name": "Mrs. Priya (ACSE)", "email": "priya@acse.edu", "role": "Fresher", "department": "ACSE", "primary_year": 2, "experience_years": 3, "max_slots": 4},
        {"name": "Mr. Vikram (ACSE)", "email": "vikram@acse.edu", "role": "Fresher", "department": "ACSE", "primary_year": 1, "experience_years": 1, "max_slots": 4},
        {"name": "Dr. Geeta (ACSE)", "email": "geeta@acse.edu", "role": "BOA", "department": "ACSE", "primary_year": 4, "experience_years": 12, "max_slots": 2},
        
        # ECE Faculty (4 available)
        {"name": "Dr. Madhav (ECE)", "email": "madhav@ece.edu", "role": "Senior", "department": "ECE", "primary_year": 2, "experience_years": 9, "max_slots": 3},
        {"name": "Mrs. Sravani (ECE)", "email": "sravani@ece.edu", "role": "Fresher", "department": "ECE", "primary_year": 2, "experience_years": 3, "max_slots": 4},
        {"name": "Dr. Krishna (ECE)", "email": "krishna@ece.edu", "role": "BOA", "department": "ECE", "primary_year": 4, "experience_years": 18, "max_slots": 2},
        {"name": "Mr. Sandeep (ECE)", "email": "sandeep@ece.edu", "role": "Fresher", "department": "ECE", "primary_year": 1, "experience_years": 2, "max_slots": 4},
        
        # EEE Faculty (3 available)
        {"name": "Dr. Raghav (EEE)", "email": "raghav@eee.edu", "role": "Senior", "department": "EEE", "primary_year": 3, "experience_years": 7, "max_slots": 3},
        {"name": "Mr. Karthik (EEE)", "email": "karthik@eee.edu", "role": "Fresher", "department": "EEE", "primary_year": 1, "experience_years": 1, "max_slots": 4},
        {"name": "Mrs. Divya (EEE)", "email": "divya@eee.edu", "role": "Senior", "department": "EEE", "primary_year": 4, "experience_years": 5, "max_slots": 3},
        
        # MECH Faculty (2 available)
        {"name": "Dr. Sekhar (MECH)", "email": "sekhar@mech.edu", "role": "Senior", "department": "MECH", "primary_year": 1, "experience_years": 10, "max_slots": 3},
        {"name": "Mr. Tarun (MECH)", "email": "tarun@mech.edu", "role": "Fresher", "department": "MECH", "primary_year": 3, "experience_years": 2, "max_slots": 4},
    ]
    
    faculty_instances = []
    for f_data in faculty_data:
        fac = Faculty(**f_data)
        db.add(fac)
        faculty_instances.append(fac)
    db.commit()
    
    # Reload instances
    faculty_instances = db.query(Faculty).all()

    # 5. Seed Faculty Timetable Schedules (Class conflicts)
    print("Seeding timetables...")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    
    # By default, everyone is free
    for f in faculty_instances:
        for day in days:
            for s in slots:
                is_teaching = False
                
                # Introduce specific teaching conflicts to show constraints in action:
                # Monday Slot 1 (08:15 - 10:15) conflicts:
                if day == "Monday" and s.name == "Slot 1":
                    if f.name in ("Dr. Ramesh (ACSE)", "Dr. Madhav (ECE)", "Dr. Raghav (EEE)"):
                        is_teaching = True
                
                # Monday Slot 2 (10:15 - 12:15) conflicts:
                if day == "Monday" and s.name == "Slot 2":
                    if f.name in ("Mr. Anil (ACSE)", "Mrs. Sravani (ECE)", "Mrs. Divya (EEE)"):
                        is_teaching = True
                        
                # Tuesday Slot 1 conflicts:
                if day == "Tuesday" and s.name == "Slot 1":
                    if f.name in ("Dr. Sunitha (ACSE)", "Dr. Geeta (ACSE)"):
                        is_teaching = True
                
                tt = FacultyTimetable(
                    faculty_id=f.id,
                    day_of_week=day,
                    slot_id=s.id,
                    is_teaching=is_teaching
                )
                db.add(tt)
    db.commit()

    # 6. Seed Exams (6 exams)
    # Day 1: Monday, 2026-09-15
    # Day 2: Tuesday, 2026-09-16
    print("Seeding exams...")
    exams_data = [
        # Monday (2026-09-15) - Day 1
        {
            "course_code": "ACSE301",
            "course_name": "Database Management Systems",
            "department": "ACSE",
            "year": 3,
            "date": "2026-09-15",
            "slot_id": slots[0].id, # Slot 1 (Monday)
            "required_invigilators": 3
        },
        {
            "course_code": "ECE201",
            "course_name": "Digital Logic Design",
            "department": "ECE",
            "year": 2,
            "date": "2026-09-15",
            "slot_id": slots[0].id, # Slot 1 (Monday)
            "required_invigilators": 2
        },
        {
            "course_code": "ACSE401",
            "course_name": "Artificial Intelligence & ML",
            "department": "ACSE",
            "year": 4,
            "date": "2026-09-15",
            "slot_id": slots[1].id, # Slot 2 (Monday)
            "required_invigilators": 3
        },
        
        # Tuesday (2026-09-16) - Day 2
        # Severe shortage test: ACSE 3rd Year exam needs 12 invigilators!
        # CSE/ACSE only has 7 faculty. Some of them have class conflicts on Tuesday Slot 1!
        # Specifically, Dr. Sunitha (ACSE) and Dr. Geeta (ACSE) have class on Tuesday Slot 1.
        # This leaves only 5 ACSE faculty available.
        # To get 12 invigilators, the system MUST fallback to ECE, EEE, and MECH available faculty
        # and calculate suitability scores for cross-department backups.
        {
            "course_code": "ACSE302",
            "course_name": "Design & Analysis of Algorithms",
            "department": "ACSE",
            "year": 3,
            "date": "2026-09-16",
            "slot_id": slots[0].id, # Slot 1 (Tuesday)
            "required_invigilators": 12
        },
        {
            "course_code": "EEE101",
            "course_name": "Basic Electrical Engineering",
            "department": "EEE",
            "year": 1,
            "date": "2026-09-16",
            "slot_id": slots[1].id, # Slot 2 (Tuesday)
            "required_invigilators": 2
        },
        {
            "course_code": "MECH401",
            "course_name": "Robotics & Automation",
            "department": "MECH",
            "year": 4,
            "date": "2026-09-16",
            "slot_id": slots[1].id, # Slot 2 (Tuesday)
            "required_invigilators": 2
        }
    ]

    for ex_data in exams_data:
        exam = Exam(**ex_data)
        db.add(exam)
    db.commit()
    
    print("Database successfully seeded!")
    db.close()

if __name__ == "__main__":
    seed_database()
