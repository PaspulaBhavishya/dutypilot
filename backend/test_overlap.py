from backend.scheduler import times_overlap, solve_allocation
from backend.parsers import parse_docx_timetable, parse_pdf_timetable
from backend.database import SessionLocal
from backend.models import Faculty, Exam, DutyAssignment

def test_interval_math():
    print("\n--- 1. Testing Minute-to-Minute Overlap Interval Math ---")
    
    # Complete overlap
    assert times_overlap("10:00", "11:00", "09:30", "12:30") is True, "Failed on complete overlap"
    print("[PASS] Complete overlap: 10:00-11:00 overlaps 09:30-12:30")
    
    # Partial start overlap
    assert times_overlap("09:00", "10:00", "09:30", "12:30") is True, "Failed on partial start"
    print("[PASS] Partial start overlap: 09:00-10:00 overlaps 09:30-12:30")
    
    # Partial end overlap
    assert times_overlap("12:00", "13:00", "09:30", "12:30") is True, "Failed on partial end"
    print("[PASS] Partial end overlap: 12:00-13:00 overlaps 09:30-12:30")
    
    # Adjacent boundary (touching, but not overlapping)
    assert times_overlap("08:30", "09:30", "09:30", "12:30") is False, "Failed on adjacent boundary"
    print("[PASS] Adjacent boundary: 08:30-09:30 does NOT overlap 09:30-12:30")
    
    # Completely disjoint before
    assert times_overlap("07:00", "08:00", "09:30", "12:30") is False, "Failed on disjoint before"
    print("[PASS] Disjoint before: 07:00-08:00 does NOT overlap 09:30-12:30")
    
    # Completely disjoint after
    assert times_overlap("14:00", "15:00", "09:30", "12:30") is False, "Failed on disjoint after"
    print("[PASS] Disjoint after: 14:00-15:00 does NOT overlap 09:30-12:30")

def test_document_parsers():
    print("\n--- 2. Testing Document Parsers (DOCX & PDF) ---")
    
    with open("sample_timetable.docx", "rb") as f:
        docx_bytes = f.read()
    docx_rows = parse_docx_timetable(docx_bytes)
    assert len(docx_rows) > 0, "DOCX parser failed to extract rows"
    print(f"[PASS] DOCX parser extracted {len(docx_rows)} timetable classes from sample_timetable.docx")
    first = docx_rows[0]
    print(f"       Sample row: {first['faculty_identifier']} | {first['day_of_week']} | {first['start_time']}–{first['end_time']} | {first['class_name']}")
    
    with open("sample_timetable.pdf", "rb") as f:
        pdf_bytes = f.read()
    pdf_rows = parse_pdf_timetable(pdf_bytes)
    assert len(pdf_rows) > 0, "PDF parser failed to extract rows"
    print(f"[PASS] PDF parser extracted {len(pdf_rows)} timetable classes from sample_timetable.pdf")

def test_solver_with_interval_clashes():
    print("\n--- 3. Testing Solver With Real Class Clashes ---")
    db = SessionLocal()
    res = solve_allocation(db, is_simulation=False)
    assert res["status"] == "success", f"Solver failed: {res.get('message')}"
    
    print(f"[PASS] Solver executed: {res['assigned_count']}/{res['required_count']} duties assigned ({res['success_rate']}%)")
    print(f"       Cross-year fallbacks: {res['cross_year_assignments']}")
    
    # Check that faculty with class clashes were Avoided with clash explanations
    assignments = res["assignments"]
    clash_avoided = [a for a in assignments if a["status"] == "Avoided" and "Class clash" in str(a.get("rejection_reason"))]
    assert len(clash_avoided) > 0, "No class clashes detected by solver!"
    print(f"[PASS] Successfully detected and prevented {len(clash_avoided)} class clash conflicts!")
    print(f"       Sample reason: {clash_avoided[0]['faculty_name']} -> {clash_avoided[0]['rejection_reason']}")
    
    db.close()

if __name__ == "__main__":
    test_interval_math()
    test_document_parsers()
    test_solver_with_interval_clashes()
    print("\n=== ALL OVERLAP & PARSER TESTS PASSED! ===")
