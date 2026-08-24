from backend.database import SessionLocal
from backend.scheduler import solve_allocation
from backend.models import Faculty, Exam

def run_tests():
    db = SessionLocal()
    print("=== Running Scheduler Test ===")
    
    # 1. Test Baseline Optimization Run
    res = solve_allocation(db, is_simulation=False)
    
    if res["status"] == "error":
        print(f"FAILED: Solver returned error: {res['message']}")
        db.close()
        return
        
    print(f"Roster Status: {res['status'].upper()}")
    print(f"Total Exams Scheduled: {res['total_exams']}")
    print(f"Total Required Duties: {res['required_count']}")
    print(f"Total Assigned Duties: {res['assigned_count']}")
    print(f"Shortage Count: {res['conflicts_count']}")
    print(f"Success Rate: {res['success_rate']}%")
    print(f"Cross-Year Duties: {res['cross_year_assignments']}")
    print("Shortages by Exam:", res["shortages"])
    
    # Verify constraints: Workload limit check
    faculty_list = db.query(Faculty).all()
    assignments = res["assignments"]
    
    # Check that no faculty member exceeded their max slots
    fac_counts = {}
    for a in assignments:
        if a["status"] == "Assigned":
            fac_counts[a["faculty_id"]] = fac_counts.get(a["faculty_id"], 0) + 1
            
    for f in faculty_list:
        assigned = fac_counts.get(f.id, 0)
        assert assigned <= f.max_slots, f"Constraint Violation: {f.name} assigned {assigned} slots, max allowed is {f.max_slots}."
    
    print("\n[PASSED] Hard workload limit constraints verified!")
    
    # Check that no faculty member is double booked in the same slot
    # We check if there are any duplicate assignments for a faculty on the same day and slot.
    exams = db.query(Exam).all()
    exam_map = {e.id: e for e in exams}
    
    fac_slot_bookings = {}
    for a in assignments:
        if a["status"] == "Assigned":
            e = exam_map[a["exam_id"]]
            key = (a["faculty_id"], e.date, e.slot_id)
            assert key not in fac_slot_bookings, f"Constraint Violation: {a['faculty_name']} double booked on {e.date} in slot {e.slot_id}."
            fac_slot_bookings[key] = True
            
    print("[PASSED] Double booking check verified (0 overlaps)!")
    
    # 2. Test Simulation Mode (Mark 5 ACSE/ECE faculty as unavailable)
    print("\n=== Simulating What-If (Faculty Absence) ===")
    
    # Mark some faculty as simulated unavailable
    absent_names = [
        "Dr. Ramesh (ACSE)",
        "Dr. Prasad (ACSE)",
        "Mr. Vikram (ACSE)",
        "Dr. Krishna (ECE)",
        "Dr. Raghav (EEE)"
    ]
    
    db.query(Faculty).filter(Faculty.name.in_(absent_names)).update(
        {Faculty.is_simulated_unavailable: True},
        synchronize_session=False
    )
    db.commit()
    
    # Run simulation
    sim_res = solve_allocation(db, is_simulation=True)
    
    print(f"Simulation Roster Status: {sim_res['status'].upper()}")
    print(f"Required Duties: {sim_res['required_count']}")
    print(f"Assigned Duties: {sim_res['assigned_count']}")
    print(f"Shortage Count: {sim_res['conflicts_count']}")
    print(f"Simulation Success Rate: {sim_res['success_rate']}%")
    print(f"Simulation Cross-Year Duties: {sim_res['cross_year_assignments']}")
    print("Simulation Shortages by Exam:", sim_res["shortages"])
    
    # Check that none of the absent faculty were assigned in simulation
    absent_ids = [f.id for f in faculty_list if f.name in absent_names]
    for a in sim_res["assignments"]:
        if a["status"] == "Assigned":
            assert a["faculty_id"] not in absent_ids, f"Constraint Violation: Unavailable faculty {a['faculty_name']} was assigned in simulation."
            
    print("[PASSED] What-If simulation constraints verified (Unavailable faculty excluded)!")
    
    # Clean up simulation flags
    db.query(Faculty).update({Faculty.is_simulated_unavailable: False}, synchronize_session=False)
    db.commit()
    print("\n=== All Tests Passed Successfully! ===")
    db.close()

if __name__ == "__main__":
    run_tests()
