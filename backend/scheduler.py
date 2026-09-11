import json
from datetime import datetime
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from .models import Faculty, FacultyTimetable, Exam, DutyAssignment, TimeSlot

def to_minutes(t_str: str) -> int:
    """Converts 'HH:MM' string to minutes from midnight."""
    try:
        parts = t_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0

def times_overlap(start1_str: str, end1_str: str, start2_str: str, end2_str: str) -> bool:
    """
    Checks if interval [start1, end1] overlaps with [start2, end2].
    Times in 'HH:MM' format.
    Overlap condition: max(start1, start2) < min(end1, end2)
    """
    s1, e1 = to_minutes(start1_str), to_minutes(end1_str)
    s2, e2 = to_minutes(start2_str), to_minutes(end2_str)
    return max(s1, s2) < min(e1, e2)

def get_day_of_week(date_str: str) -> str:
    """Returns the day of the week for a given YYYY-MM-DD date."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
    except ValueError:
        return "Monday"

def get_exam_times(exam: Exam) -> tuple:
    """Returns (start_time, end_time) for an exam."""
    if exam.start_time and exam.end_time:
        return exam.start_time, exam.end_time
    if exam.slot:
        return exam.slot.start_time, exam.slot.end_time
    return "08:15", "10:15"

def calculate_suitability(faculty: Faculty, exam: Exam, final_workloads: dict, is_available: bool) -> dict:
    """
    Calculates suitability score breakdown (Max 100).
    - Proximity & Role Tier: Max 70
      - Same Dept & Same Year: Fresher=70, Senior=60, BOA=50
      - Same Dept & Other Year: Fresher=45, Senior=40, BOA=35
      - Other Dept & Same Year: Fresher=35, Senior=30, BOA=25
      - Other Dept & Other Year: Fresher=20, Senior=15, BOA=10
    - Availability: Max 15
    - Workload: Max 10
    - Experience: Max 5
    """
    assigned_duties = final_workloads.get(faculty.id, 0)
    is_same_year = (faculty.primary_year == exam.year)
    is_same_dept = (faculty.department == exam.department)
    
    # 1. Proximity & Role Tier Score (Max 70)
    tier_score = 0
    tier_name = ""
    
    if is_same_dept and is_same_year:
        tier_name = "Same Dept & Same Year"
        tier_score = 70 if faculty.role == "Fresher" else (60 if faculty.role == "Senior" else 50)
    elif is_same_dept and not is_same_year:
        tier_name = "Same Dept (Other Year)"
        tier_score = 45 if faculty.role == "Fresher" else (40 if faculty.role == "Senior" else 35)
    elif not is_same_dept and is_same_year:
        tier_name = "Other Dept (Same Year)"
        tier_score = 35 if faculty.role == "Fresher" else (30 if faculty.role == "Senior" else 25)
    else:
        tier_name = "Other Dept & Other Year"
        tier_score = 20 if faculty.role == "Fresher" else (15 if faculty.role == "Senior" else 10)
        
    # 2. Availability (Max 15)
    avail_score = 15 if is_available else 0
    
    # 3. Workload factor (Max 10)
    workload_val = int(10 * (1.0 - (assigned_duties / faculty.max_slots)))
    workload_val = max(0, min(10, workload_val))
    
    # 4. Experience (Max 5)
    exp_val = min(5, faculty.experience_years)
    
    total = tier_score + avail_score + workload_val + exp_val
    
    return {
        "tier_name": tier_name,
        "tier_score": tier_score,
        "availability": avail_score,
        "workload": workload_val,
        "experience": exp_val,
        "total": total
    }

def solve_allocation(db: Session, is_simulation: bool = False) -> dict:
    """
    Solves the exam invigilation problem using Google OR-Tools CP-SAT
    with exact minute-to-minute class overlap detection.
    """
    # 1. Fetch datasets
    exams = db.query(Exam).all()
    faculty_list = db.query(Faculty).all()
    
    if not exams or not faculty_list:
        return {"status": "error", "message": "No exams or faculty members found."}
        
    # Map faculty daily teaching classes: (faculty_id, day_of_week) -> list of classes
    timetables = db.query(FacultyTimetable).filter(FacultyTimetable.is_teaching == True).all()
    faculty_classes = {}
    for tt in timetables:
        key = (tt.faculty_id, tt.day_of_week)
        if key not in faculty_classes:
            faculty_classes[key] = []
        faculty_classes[key].append({
            "class_name": tt.class_name or "Lecture",
            "start_time": tt.start_time,
            "end_time": tt.end_time
        })

    # Initialize CP-SAT Model
    model = cp_model.CpModel()
    
    # 2. Define Variables
    x = {} # (exam_id, faculty_id) -> BoolVar
    s = {} # exam_id -> IntVar (slack/shortage)
    
    for e in exams:
        s[e.id] = model.NewIntVar(0, e.required_invigilators, f"slack_{e.id}")
        for f in faculty_list:
            x[(e.id, f.id)] = model.NewBoolVar(f"x_{e.id}_{f.id}")
            
    # 3. Add Hard Constraints
    
    # C1: Roster completion with shortage slack
    for e in exams:
        model.Add(sum(x[(e.id, f.id)] for f in faculty_list) + s[e.id] == e.required_invigilators)
        
    # C2: Workload Limit per faculty
    for f in faculty_list:
        model.Add(sum(x[(e.id, f.id)] for e in exams) <= f.max_slots)
        
    # C3: No overlapping duties for any faculty on the same day
    # Check all pairs of exams on the same date
    for i in range(len(exams)):
        for j in range(i + 1, len(exams)):
            e1, e2 = exams[i], exams[j]
            if e1.date == e2.date:
                s1, end1 = get_exam_times(e1)
                s2, end2 = get_exam_times(e2)
                if times_overlap(s1, end1, s2, end2):
                    for f in faculty_list:
                        model.Add(x[(e1.id, f.id)] + x[(e2.id, f.id)] <= 1)
            
    # C4: Minute-to-Minute Class Conflicts & Simulated Unavailability
    class_clash_map = {} # (exam_id, faculty_id) -> clash reason string
    for e in exams:
        day = get_day_of_week(e.date)
        e_start, e_end = get_exam_times(e)
        
        for f in faculty_list:
            is_sim_unavailable = is_simulation and f.is_simulated_unavailable
            
            # Check minute-to-minute class overlaps on that day
            classes_today = faculty_classes.get((f.id, day), [])
            has_class_clash = False
            for c in classes_today:
                if times_overlap(c["start_time"], c["end_time"], e_start, e_end):
                    has_class_clash = True
                    class_clash_map[(e.id, f.id)] = (
                        f"Class clash: '{c['class_name']}' ({c['start_time']}–{c['end_time']}) "
                        f"overlaps with exam ({e_start}–{e_end})"
                    )
                    break
                    
            if has_class_clash or is_sim_unavailable:
                model.Add(x[(e.id, f.id)] == 0)

    # 4. Fairness Optimization & Workload step penalties
    y = {}
    for f in faculty_list:
        max_d = f.max_slots
        for k in range(1, max_d + 1):
            y[(f.id, k)] = model.NewBoolVar(f"y_{f.id}_{k}")
            
        model.Add(sum(x[(e.id, f.id)] for e in exams) == sum(y[(f.id, k)] for k in range(1, max_d + 1)))
        for k in range(1, max_d):
            model.Add(y[(f.id, k)] >= y[(f.id, k + 1)])

    # 5. Objective Function Formulation
    objective_terms = []
    
    # Shortage Slack Penalty
    for e in exams:
        objective_terms.append(-100000 * s[e.id])
        
    # Preference Scores for Assignments (Hierarchical Role & Proximity Tiers)
    for e in exams:
        for f in faculty_list:
            is_same_year = (f.primary_year == e.year)
            is_same_dept = (f.department == e.department)
            
            if is_same_dept and is_same_year:
                tier_score = 1000 if f.role == "Fresher" else (800 if f.role == "Senior" else 600)
            elif is_same_dept and not is_same_year:
                tier_score = 500 if f.role == "Fresher" else (400 if f.role == "Senior" else 300)
            elif not is_same_dept and is_same_year:
                tier_score = 400 if f.role == "Fresher" else (300 if f.role == "Senior" else 200)
            else:
                tier_score = 200 if f.role == "Fresher" else (150 if f.role == "Senior" else 100)
                
            pref = tier_score + min(10, f.experience_years)
            objective_terms.append(pref * x[(e.id, f.id)])
            
    # Workload Balancing Penalties
    penalties = {1: 0, 2: 10, 3: 30, 4: 80}
    for f in faculty_list:
        for k in range(1, f.max_slots + 1):
            penalty = penalties.get(k, 100)
            objective_terms.append(-penalty * y[(f.id, k)])
            
    model.Maximize(sum(objective_terms))
    
    # 6. Execute Solver
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.Solve(model)
    
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "error",
            "message": "Optimization solver could not find a feasible solution structure."
        }
        
    # 7. Post-Process Results & Extract Assignments
    final_workloads = {}
    for f in faculty_list:
        final_workloads[f.id] = sum(int(solver.Value(x[(e.id, f.id)])) for e in exams)
        
    assignments_to_save = []
    response_details = []
    shortages_by_exam = {}
    
    total_required = sum(e.required_invigilators for e in exams)
    total_assigned = 0
    cross_year_assignments = 0
    
    for e in exams:
        shortage = int(solver.Value(s[e.id]))
        shortages_by_exam[e.course_code] = shortage
        e_start, e_end = get_exam_times(e)
        
        # Extract Assigned Faculty
        assigned_faculty_ids = []
        for f in faculty_list:
            if solver.Value(x[(e.id, f.id)]) == 1:
                assigned_faculty_ids.append(f.id)
                total_assigned += 1
                if f.primary_year != e.year:
                    cross_year_assignments += 1
                    
        # Compute Suitability details for all faculty & classify
        faculty_suitability_list = []
        for f in faculty_list:
            has_class_clash = (e.id, f.id) in class_clash_map
            is_sim_unavail = is_simulation and f.is_simulated_unavailable
            is_available = not (has_class_clash or is_sim_unavail)
            
            score_card = calculate_suitability(f, e, final_workloads, is_available)
            
            rejection_reason = None
            status_str = "Avoided"
            
            if f.id in assigned_faculty_ids:
                status_str = "Assigned"
            else:
                if has_class_clash:
                    rejection_reason = class_clash_map[(e.id, f.id)]
                elif is_sim_unavail:
                    rejection_reason = "Marked unavailable (What-If simulation)"
                else:
                    # Check if assigned to another overlapping exam on this day
                    other_exam_assigned = False
                    for other_e in exams:
                        if other_e.id != e.id and other_e.date == e.date:
                            s_other, end_other = get_exam_times(other_e)
                            if times_overlap(e_start, e_end, s_other, end_other) and solver.Value(x[(other_e.id, f.id)]) == 1:
                                other_exam_assigned = True
                                rejection_reason = f"Assigned to {other_e.course_code} ({s_other}–{end_other})"
                                break
                    
                    if not other_exam_assigned:
                        if final_workloads[f.id] >= f.max_slots:
                            rejection_reason = f"Maximum workload limit reached ({f.max_slots}/{f.max_slots} slots)"
                        elif f.primary_year != e.year or f.department != e.department:
                            rejection_reason = "Avoided: non-assigned fallback candidate"
                        else:
                            rejection_reason = "Backup candidate available"
            
            faculty_suitability_list.append({
                "faculty": f,
                "score_card": score_card,
                "status": status_str,
                "rejection_reason": rejection_reason,
                "is_available": is_available
            })
            
        # Eligible backups
        eligible_backups = [
            item for item in faculty_suitability_list 
            if item["status"] == "Avoided" and item["is_available"] and not str(item["rejection_reason"]).startswith("Assigned to")
        ]
        eligible_backups.sort(key=lambda item: item["score_card"]["total"], reverse=True)
        
        for item in eligible_backups[:3]:
            item["status"] = "Backup"
            item["rejection_reason"] = None
            
        for item in faculty_suitability_list:
            f = item["faculty"]
            status_val = item["status"]
            rejection_val = item["rejection_reason"]
            score_card = item["score_card"]
            
            if not is_simulation:
                assignment = DutyAssignment(
                    exam_id=e.id,
                    faculty_id=f.id,
                    suitability_score=score_card["total"],
                    status=status_val,
                    rejection_reason=rejection_val,
                    score_breakdown=json.dumps(score_card)
                )
                assignments_to_save.append(assignment)
                
            response_details.append({
                "id": 0,
                "exam_id": e.id,
                "faculty_id": f.id,
                "faculty_name": f.name,
                "faculty_role": f.role,
                "faculty_department": f.department,
                "faculty_primary_year": f.primary_year,
                "suitability_score": score_card["total"],
                "status": status_val,
                "rejection_reason": rejection_val,
                "score_breakdown": score_card
            })
            
    if not is_simulation:
        db.query(DutyAssignment).delete()
        db.add_all(assignments_to_save)
        db.commit()
        
    success_rate = (total_assigned / total_required * 100) if total_required > 0 else 100.0
    
    return {
        "status": "success",
        "scenario_name": "What-If Simulation" if is_simulation else "Baseline Allocation",
        "total_exams": len(exams),
        "assigned_count": total_assigned,
        "required_count": total_required,
        "success_rate": round(success_rate, 2),
        "conflicts_count": sum(shortages_by_exam.values()),
        "cross_year_assignments": cross_year_assignments,
        "shortages": shortages_by_exam,
        "assignments": response_details
    }
