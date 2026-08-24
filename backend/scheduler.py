import json
from datetime import datetime
from ortools.sat.python import cp_model
from sqlalchemy.orm import Session
from .models import Faculty, FacultyTimetable, Exam, DutyAssignment, TimeSlot

def get_day_of_week(date_str: str) -> str:
    """Returns the day of the week for a given YYYY-MM-DD date."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
    except ValueError:
        return "Monday" # Fallback

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
    Solves the exam invigilation problem using Google OR-Tools CP-SAT.
    """
    # 1. Fetch all datasets
    exams = db.query(Exam).all()
    faculty_list = db.query(Faculty).all()
    slots = db.query(TimeSlot).all()
    
    if not exams or not faculty_list:
        return {"status": "error", "message": "No exams or faculty members found."}
        
    # Map timetables for quick lookup
    # timetable_map[(faculty_id, day, slot_id)] = is_teaching
    timetables = db.query(FacultyTimetable).all()
    tt_map = {}
    for tt in timetables:
        tt_map[(tt.faculty_id, tt.day_of_week, tt.slot_id)] = tt.is_teaching

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
        
    # C3: No double booking / overlap in the same slot
    # Group exams by (date, slot_id)
    slot_exams = {}
    for e in exams:
        key = (e.date, e.slot_id)
        if key not in slot_exams:
            slot_exams[key] = []
        slot_exams[key].append(e)
        
    for (date, slot_id), exam_subset in slot_exams.items():
        for f in faculty_list:
            model.Add(sum(x[(e.id, f.id)] for e in exam_subset) <= 1)
            
    # C4: Timetable class conflicts & Simulated Unavailability
    for e in exams:
        day = get_day_of_week(e.date)
        for f in faculty_list:
            # Check timetable conflict
            has_class = tt_map.get((f.id, day, e.slot_id), False)
            # Check if unavailable in simulation sandbox
            is_sim_unavailable = is_simulation and f.is_simulated_unavailable
            
            if has_class or is_sim_unavailable:
                model.Add(x[(e.id, f.id)] == 0)

    # 4. Fairness Optimization & Workload step penalties
    # Create auxiliary variables to represent duties assigned to each faculty
    # y[f.id, k] = 1 if faculty has >= k duties
    y = {}
    for f in faculty_list:
        max_d = f.max_slots
        for k in range(1, max_d + 1):
            y[(f.id, k)] = model.NewBoolVar(f"y_{f.id}_{k}")
            
        # Sum of assignments = sum of y's
        model.Add(sum(x[(e.id, f.id)] for e in exams) == sum(y[(f.id, k)] for k in range(1, max_d + 1)))
        
        # Order the y's: y_1 >= y_2 >= y_3 ...
        for k in range(1, max_d):
            model.Add(y[(f.id, k)] >= y[(f.id, k + 1)])

    # 5. Objective Function Formulation
    objective_terms = []
    
    # Shortage Slack Penalty (very high penalty)
    for e in exams:
        objective_terms.append(-100000 * s[e.id])
        
    # Preference Scores for Assignments (Hierarchical Role & Proximity Tiers)
    for e in exams:
        for f in faculty_list:
            is_same_year = (f.primary_year == e.year)
            is_same_dept = (f.department == e.department)
            
            # Tier score matching
            if is_same_dept and is_same_year:
                # Same Department & Same Year (Top Tier)
                tier_score = 1000 if f.role == "Fresher" else (800 if f.role == "Senior" else 600)
            elif is_same_dept and not is_same_year:
                # Same Department but different year
                tier_score = 500 if f.role == "Fresher" else (400 if f.role == "Senior" else 300)
            elif not is_same_dept and is_same_year:
                # Different Department but same year
                tier_score = 400 if f.role == "Fresher" else (300 if f.role == "Senior" else 200)
            else:
                # Different Department & Different Year
                tier_score = 200 if f.role == "Fresher" else (150 if f.role == "Senior" else 100)
                
            pref = tier_score + min(10, f.experience_years)
            objective_terms.append(pref * x[(e.id, f.id)])
            
    # Workload Balancing Penalties
    for f in faculty_list:
        # Step penalties: 
        # 1st slot: 0 penalty
        # 2nd slot: 10 penalty
        # 3rd slot: 30 penalty
        # 4th slot: 80 penalty
        penalties = {1: 0, 2: 10, 3: 30, 4: 80}
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
        exam_date_day = get_day_of_week(e.date)
        shortage = int(solver.Value(s[e.id]))
        shortages_by_exam[e.course_code] = shortage
        
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
            # Check availability
            has_class = tt_map.get((f.id, exam_date_day, e.slot_id), False)
            is_sim_unavail = is_simulation and f.is_simulated_unavailable
            is_available = not (has_class or is_sim_unavail)
            
            # Compute Suitability Score
            score_card = calculate_suitability(f, e, final_workloads, is_available)
            
            # Rejection/Avoided Reason
            rejection_reason = None
            status_str = "Avoided"
            
            if f.id in assigned_faculty_ids:
                status_str = "Assigned"
            else:
                if has_class:
                    rejection_reason = f"Class conflict during {exam_date_day} {e.slot.name}"
                elif is_sim_unavail:
                    rejection_reason = "Marked unavailable (What-If)"
                else:
                    other_exam_assigned = False
                    for other_e in slot_exams.get((e.date, e.slot_id), []):
                        if other_e.id != e.id and solver.Value(x[(other_e.id, f.id)]) == 1:
                            other_exam_assigned = True
                            rejection_reason = f"Assigned to {other_e.course_code} in same slot"
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
            
        # Sort candidates to determine backups
        eligible_backups = [
            item for item in faculty_suitability_list 
            if item["status"] == "Avoided" and item["is_available"] and not item["rejection_reason"].startswith("Assigned to")
        ]
        eligible_backups.sort(key=lambda item: item["score_card"]["total"], reverse=True)
        
        backup_faculty_ids = set()
        for item in eligible_backups[:3]:
            item["status"] = "Backup"
            item["rejection_reason"] = None
            backup_faculty_ids.add(item["faculty"].id)
            
        # Save all results to assignments list
        for item in faculty_suitability_list:
            f = item["faculty"]
            status_val = item["status"]
            rejection_val = item["rejection_reason"]
            score_card = item["score_card"]
            
            # Save all Assignments to Database (if not simulation)
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
            
    # If not simulation, overwrite the database assignments
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
