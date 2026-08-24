# DutyPilot — AI-Powered Exam Invigilation Allocation System

DutyPilot is an intelligent exam invigilation scheduling and optimization system. It uses **Google OR-Tools CP-SAT** to search the entire allocation space, resolving timetable clashes and ensuring fair workload distribution across faculty roles while maintaining academic year isolation.

---

## 🛠️ Stack & Architecture
- **Backend**: FastAPI (Python 3.14)
- **Solver**: Google OR-Tools CP-SAT (Constraint Programming)
- **Database**: SQLite with SQLAlchemy ORM
- **Frontend**: Single-Page App (SPA) built with Vue.js 3 & Tailwind CSS (zero-npm setup)

---

## 🧠 Optimization & Constraints Model

### 1. Hard Constraints (Rules Engine)
- **Role Limits**: Faculty slots are limited strictly by role:
  - **BOA Faculty**: Max 2 slots
  - **Senior Faculty**: Max 3 slots
  - **Fresher Faculty**: Max 4 slots
- **No Overlapping Duties**: A faculty member cannot be assigned twice in the same slot on the same day.
- **Teaching Timetable Conflicts**: Excludes faculty automatically if they teach a class during the exam's time slot.
- **Absence List (What-If)**: Excludes faculty marked unavailable during simulation tests.

### 2. Soft Preferences (Optimization Weights)
- **Same Academic Year Match**: $+30$ points
- **Same Department Match**: $+20$ points
- **Invigilation Experience**: up to $+10$ points (linear scale)
- **Workload Fairness**: Enforced via step penalties to prevent overloaded schedules:
  - 1st duty: 0 penalty
  - 2nd duty: 10 penalty
  - 3rd duty: 30 penalty
  - 4th duty: 80 penalty

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install ortools pandas openpyxl fastapi uvicorn sqlalchemy python-multipart
```

### 2. Populate Seed Datasets
Populates the database with customizable slots (8:15 AM to 4:00 PM), departments (starting with ACSE), and faculty timetables:
```bash
python -m backend.seed
```

### 3. Launch Dev Server
```bash
python -m uvicorn backend.main:app --reload
```

Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser to access the dashboard.

---

## 💡 Key Features Demo
1. **Explainable Scorecards**: Displays suitability scores out of 100 with clear breakdowns.
2. **Backups & Avoided Details**: Classifies non-assigned faculty into backups or avoided lists with clear reasons (e.g. class conflict, workload limit).
3. **What-If Simulation Sandbox**: Absences can be toggled to compare roster success rates side-by-side.
4. **Excel Import & CSV Export**: Allows uploading standard excel templates and downloading generated duty rosters.
