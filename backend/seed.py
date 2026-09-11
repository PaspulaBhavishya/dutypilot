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
    slots = db.query(TimeSlot).all()

    # 4. Seed Faculty (16 faculty members)
    print("Seeding faculty...")
    faculty_data = [
        {"name": "Dr. Ramesh (ACSE)", "email": "ramesh@acse.edu", "role": "BOA", "department": "ACSE", "primary_year": 3, "experience_years": 15, "max_slots": 2},
        {"name": "Dr. Sunitha (ACSE)", "email": "sunitha@acse.edu", "role": "Senior", "department": "ACSE", "primary_year": 3, "experience_years": 8, "max_slots": 3},
        {"name": "Mr. Anil (ACSE)", "email": "anil@acse.edu", "role": "Fresher", "department": "ACSE", "primary_year": 3, "experience_years": 2, "max_slots": 4},
        {"name": "Dr. Prasad (ACSE)", "email": "prasad@acse.edu", "role": "Senior", "department": "ACSE", "primary_year": 2, "experience_years": 6, "max_slots": 3},
        {"name": "Mrs. Priya (ACSE)", "email": "priya@acse.edu", "role": "Fresher", "department": "ACSE", "primary_year": 2, "experience_years": 3, "max_slots": 4},
        {"name": "Mr. Vikram (ACSE)", "email": "vikram@acse.edu", "role": "Fresher", "department": "ACSE", "primary_year": 1, "experience_years": 1, "max_slots": 4},
        {"name": "Dr. Geeta (ACSE)", "email": "geeta@acse.edu", "role": "BOA", "department": "ACSE", "primary_year": 4, "experience_years": 12, "max_slots": 2},
        
        {"name": "Dr. Madhav (ECE)", "email": "madhav@ece.edu", "role": "Senior", "department": "ECE", "primary_year": 2, "experience_years": 9, "max_slots": 3},
        {"name": "Mrs. Sravani (ECE)", "email": "sravani@ece.edu", "role": "Fresher", "department": "ECE", "primary_year": 2, "experience_years": 3, "max_slots": 4},
        {"name": "Dr. Krishna (ECE)", "email": "krishna@ece.edu", "role": "BOA", "department": "ECE", "primary_year": 4, "experience_years": 18, "max_slots": 2},
        {"name": "Mr. Sandeep (ECE)", "email": "sandeep@ece.edu", "role": "Fresher", "department": "ECE", "primary_year": 1, "experience_years": 2, "max_slots": 4},
        
        {"name": "Dr. Raghav (EEE)", "email": "raghav@eee.edu", "role": "Senior", "department": "EEE", "primary_year": 3, "experience_years": 7, "max_slots": 3},
        {"name": "Mr. Karthik (EEE)", "email": "karthik@eee.edu", "role": "Fresher", "department": "EEE", "primary_year": 1, "experience_years": 1, "max_slots": 4},
        {"name": "Mrs. Divya (EEE)", "email": "divya@eee.edu", "role": "Senior", "department": "EEE", "primary_year": 4, "experience_years": 5, "max_slots": 3},
        
        {"name": "Dr. Sekhar (MECH)", "email": "sekhar@mech.edu", "role": "Senior", "department": "MECH", "primary_year": 1, "experience_years": 10, "max_slots": 3},
        {"name": "Mr. Tarun (MECH)", "email": "tarun@mech.edu", "role": "Fresher", "department": "MECH", "primary_year": 3, "experience_years": 2, "max_slots": 4},
    ]
    
    fac_map = {}
    for f_data in faculty_data:
        fac = Faculty(**f_data)
        db.add(fac)
        db.flush()
        fac_map[fac.name] = fac
    db.commit()

    # 5. Seed Daily Class Periods (Minute-to-Minute Timetables)
    print("Seeding daily class periods...")
    classes_to_seed = [
        # Monday classes overlapping with Slot 1 (08:15 - 10:15)
        {"faculty": "Dr. Ramesh (ACSE)", "day": "Monday", "start": "08:30", "end": "09:30", "subject": "Database Systems Lecture"},
        {"faculty": "Dr. Madhav (ECE)", "day": "Monday", "start": "09:00", "end": "10:00", "subject": "DSP Architecture"},
        {"faculty": "Dr. Raghav (EEE)", "day": "Monday", "start": "08:30", "end": "09:30", "subject": "Power Grid Modeling"},
        
        # Monday classes overlapping with Slot 2 (10:15 - 12:15)
        {"faculty": "Mr. Anil (ACSE)", "day": "Monday", "start": "10:30", "end": "11:30", "subject": "Data Structures Lab"},
        {"faculty": "Mrs. Sravani (ECE)", "day": "Monday", "start": "10:45", "end": "11:45", "subject": "Microcontrollers"},
        {"faculty": "Mrs. Divya (EEE)", "day": "Monday", "start": "11:00", "end": "12:00", "subject": "Control Systems"},
        
        # Tuesday classes overlapping with Slot 1 (08:15 - 10:15)
        {"faculty": "Dr. Sunitha (ACSE)", "day": "Tuesday", "start": "09:00", "end": "10:00", "subject": "Software Engineering"},
        {"faculty": "Dr. Geeta (ACSE)", "day": "Tuesday", "start": "08:45", "end": "09:45", "subject": "Cloud Computing"},
        
        # Afternoon non-overlapping classes (14:00 - 15:30)
        {"faculty": "Dr. Prasad (ACSE)", "day": "Monday", "start": "14:00", "end": "15:00", "subject": "Algorithms Tutorial"},
        {"faculty": "Mrs. Priya (ACSE)", "day": "Monday", "start": "14:30", "end": "15:30", "subject": "Web Tech Lab"},
        {"faculty": "Dr. Sekhar (MECH)", "day": "Tuesday", "start": "14:00", "end": "15:00", "subject": "Thermodynamics"},
    ]

    for item in classes_to_seed:
        fac = fac_map.get(item["faculty"])
        if fac:
            tt = FacultyTimetable(
                faculty_id=fac.id,
                day_of_week=item["day"],
                class_name=item["subject"],
                start_time=item["start"],
                end_time=item["end"],
                is_teaching=True
            )
            db.add(tt)
    db.commit()

    # 6. Seed Exams
    print("Seeding exams...")
    exams_data = [
        # Monday (2026-09-15) - Day 1
        {
            "course_code": "ACSE301",
            "course_name": "Database Management Systems",
            "department": "ACSE",
            "year": 3,
            "date": "2026-09-15",
            "slot_id": slots[0].id,
            "start_time": slots[0].start_time,
            "end_time": slots[0].end_time,
            "required_invigilators": 3
        },
        {
            "course_code": "ECE201",
            "course_name": "Digital Logic Design",
            "department": "ECE",
            "year": 2,
            "date": "2026-09-15",
            "slot_id": slots[0].id,
            "start_time": slots[0].start_time,
            "end_time": slots[0].end_time,
            "required_invigilators": 2
        },
        {
            "course_code": "ACSE401",
            "course_name": "Artificial Intelligence & ML",
            "department": "ACSE",
            "year": 4,
            "date": "2026-09-15",
            "slot_id": slots[1].id,
            "start_time": slots[1].start_time,
            "end_time": slots[1].end_time,
            "required_invigilators": 3
        },
        
        # Tuesday (2026-09-16) - Day 2
        {
            "course_code": "ACSE302",
            "course_name": "Design & Analysis of Algorithms",
            "department": "ACSE",
            "year": 3,
            "date": "2026-09-16",
            "slot_id": slots[0].id,
            "start_time": slots[0].start_time,
            "end_time": slots[0].end_time,
            "required_invigilators": 12
        },
        {
            "course_code": "EEE101",
            "course_name": "Basic Electrical Engineering",
            "department": "EEE",
            "year": 1,
            "date": "2026-09-16",
            "slot_id": slots[1].id,
            "start_time": slots[1].start_time,
            "end_time": slots[1].end_time,
            "required_invigilators": 2
        },
        {
            "course_code": "MECH401",
            "course_name": "Robotics & Automation",
            "department": "MECH",
            "year": 4,
            "date": "2026-09-16",
            "slot_id": slots[1].id,
            "start_time": slots[1].start_time,
            "end_time": slots[1].end_time,
            "required_invigilators": 2
        }
    ]

    for ex_data in exams_data:
        exam = Exam(**ex_data)
        db.add(exam)
    db.commit()
    
    print("Database successfully seeded with exact daily class periods!")
    db.close()

if __name__ == "__main__":
    seed_database()
