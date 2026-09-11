import pandas as pd

def create_sample_excel():
    # 1. Faculty Sheet Data
    faculty_data = {
        "Name": [
            "Dr. Satish (ACSE)", "Mrs. Anitha (ACSE)", "Mr. Rahul (ACSE)", "Dr. Prasad (ACSE)", 
            "Mrs. Priya (ACSE)", "Mr. Vikram (ACSE)", "Dr. Geeta (ACSE)", "Dr. Madhav (ECE)", 
            "Mrs. Sravani (ECE)", "Dr. Krishna (ECE)", "Mr. Sandeep (ECE)", "Dr. Raghav (EEE)", 
            "Mr. Karthik (EEE)", "Mrs. Divya (EEE)", "Dr. Sekhar (MECH)", "Mr. Tarun (MECH)"
        ],
        "Email": [
            "satish@acse.edu", "anitha@acse.edu", "rahul@acse.edu", "prasad@acse.edu", 
            "priya@acse.edu", "vikram@acse.edu", "geeta@acse.edu", "madhav@ece.edu", 
            "sravani@ece.edu", "krishna@ece.edu", "sandeep@ece.edu", "raghav@eee.edu", 
            "karthik@eee.edu", "divya@eee.edu", "sekhar@mech.edu", "tarun@mech.edu"
        ],
        "Role": [
            "BOA", "Senior", "Fresher", "Senior", 
            "Fresher", "Fresher", "BOA", "Senior", 
            "Fresher", "BOA", "Fresher", "Senior", 
            "Fresher", "Senior", "Senior", "Fresher"
        ],
        "Department": [
            "ACSE", "ACSE", "ACSE", "ACSE", 
            "ACSE", "ACSE", "ACSE", "ECE", 
            "ECE", "ECE", "ECE", "EEE", 
            "EEE", "EEE", "MECH", "MECH"
        ],
        "Primary Year": [3, 3, 3, 2, 2, 1, 4, 2, 2, 4, 1, 3, 1, 4, 1, 3],
        "Experience Years": [15, 8, 2, 6, 3, 1, 12, 9, 3, 18, 2, 7, 1, 5, 10, 2]
    }
    
    # 2. Exams Sheet Data
    exams_data = {
        "Course Code": ["ACSE301", "ECE201", "ACSE401", "ACSE302", "EEE101", "MECH401"],
        "Course Name": [
            "Database Management Systems", "Digital Logic Design", 
            "Artificial Intelligence & ML", "Design & Analysis of Algorithms", 
            "Basic Electrical Engineering", "Robotics & Automation"
        ],
        "Department": ["ACSE", "ECE", "ACSE", "ACSE", "EEE", "MECH"],
        "Year": [3, 2, 4, 3, 1, 4],
        "Date": ["2026-09-15", "2026-09-15", "2026-09-15", "2026-09-16", "2026-09-16", "2026-09-16"],
        "Slot Name": ["Slot 1", "Slot 1", "Slot 2", "Slot 1", "Slot 2", "Slot 2"],
        "Required Invigilators": [3, 2, 3, 12, 2, 2]
    }
    
    # 3. Timetable Sheet Data (Class clashes)
    timetable_data = {
        "Faculty Email": [
            "satish@acse.edu", "madhav@ece.edu", "raghav@eee.edu", 
            "rahul@acse.edu", "sravani@ece.edu", "divya@eee.edu", 
            "anitha@acse.edu", "geeta@acse.edu"
        ],
        "Day of Week": [
            "Monday", "Monday", "Monday", 
            "Monday", "Monday", "Monday", 
            "Tuesday", "Tuesday"
        ],
        "Slot Name": [
            "Slot 1", "Slot 1", "Slot 1", 
            "Slot 2", "Slot 2", "Slot 2", 
            "Slot 1", "Slot 1"
        ],
        "Is Teaching": [1, 1, 1, 1, 1, 1, 1, 1]
    }
    
    # Create DataFrames
    df_faculty = pd.DataFrame(faculty_data)
    df_exams = pd.DataFrame(exams_data)
    df_timetable = pd.DataFrame(timetable_data)
    
    # Write to Excel
    with pd.ExcelWriter("sample_dutypilot_data.xlsx", engine="openpyxl") as writer:
        df_faculty.to_excel(writer, sheet_name="Faculty", index=False)
        df_exams.to_excel(writer, sheet_name="Exams", index=False)
        df_timetable.to_excel(writer, sheet_name="Timetable", index=False)
        
    print("Successfully generated sample_dutypilot_data.xlsx")

if __name__ == "__main__":
    create_sample_excel()
