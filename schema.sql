-- ==============================================================================
-- EEP PORTAL: MASTER DATABASE SCHEMA (v2.6)
-- ==============================================================================

-- 1. STAFF (The Security Bouncers & Users)
CREATE TABLE staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    role TEXT NOT NULL
);

-- 2. STUDENTS (The Core Identity & Roster)
CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ngo_id TEXT UNIQUE NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    khmer_name TEXT,
    gender TEXT,
    dob DATE,
    joined_date DATE,
    guardian_name TEXT,
    phone_number TEXT,
    slum_area TEXT,
    current_school TEXT,
    grade_level TEXT,
    meal_plan TEXT,
    comment TEXT,
    status TEXT DEFAULT 'Active',
    profile_picture TEXT
);

-- 3. MONTHLY REPORTS (The Academic Engine - Main Report)
CREATE TABLE monthly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    month TEXT NOT NULL,
    academic_year TEXT NOT NULL,
    semester TEXT,
    class_rank TEXT,
    teacher_comment TEXT,
    attendance_days INTEGER,
    scanned_document TEXT,
    grade_level TEXT,
    school_name TEXT,
    total_score REAL,
    overall_average REAL,
    overall_grade TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

-- 4. SUBJECTS (The Curriculum Settings)
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER,
    category TEXT DEFAULT 'General'
);

-- 5. GRADES (The Individual Subject Scores per Report)
CREATE TABLE grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    score TEXT,
    max_score TEXT,
    custom_subject_name TEXT,
    FOREIGN KEY(report_id) REFERENCES monthly_reports(id),
    FOREIGN KEY(subject_id) REFERENCES subjects(id)
);

-- 6. FOLLOWUPS (The Social Work Case Notes & Risk Assessments)
CREATE TABLE followups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    followup_date DATE NOT NULL,
    location TEXT,
    completed_by TEXT NOT NULL,
    physical_health TEXT,
    physical_health_detail TEXT,
    social_interaction TEXT,
    social_interaction_detail TEXT,
    home_life TEXT,
    home_life_detail TEXT,
    evidence_drugs_violence TEXT,
    learning_difficulties TEXT,
    behavior_in_class TEXT,
    behavior_in_class_detail TEXT,
    peer_issues TEXT,
    peer_issues_detail TEXT,
    teacher_involvement TEXT,
    teacher_involvement_detail TEXT,
    transportation TEXT,
    transportation_detail TEXT,
    tutoring_participation TEXT,
    tutoring_participation_detail TEXT,
    risk_factors TEXT,
    risk_details TEXT,
    child_protection_concerns TEXT,
    trafficking_risk TEXT,
    general_notes TEXT,
    letter_quarter TEXT,
    letter_year TEXT,
    letter_given TEXT,
    letter_translated TEXT,
    letter_scanned TEXT,
    letter_sent TEXT,
    letter_notes TEXT,
    alert_status TEXT DEFAULT 'Active',
    FOREIGN KEY(student_id) REFERENCES students(id)
);

-- 7. DOCUMENTS (The Digital Filing Cabinet)
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    original_filename TEXT NOT NULL,
    saved_filename TEXT NOT NULL,
    document_type TEXT NOT NULL,
    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

-- 8. AUDIT LOGS (The Admin Security Tracker)
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    device_info TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(staff_id) REFERENCES staff(id)
);

-- 9. ACTIVITIES (The Community Impact & Group Logs)
CREATE TABLE activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_type TEXT NOT NULL,
    activity_date DATE NOT NULL,
    attendance_count INTEGER DEFAULT 1
);

-- 10. STUDENT SERVICES (The Nutrition & Direct Support Logs)
CREATE TABLE student_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    service_date DATE NOT NULL,
    service_type TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

-- 11. STUDENT EXPENSES (The Phase 4 NGO Financial Ledger)
CREATE TABLE student_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    vendor_name TEXT,
    expense_date DATE DEFAULT CURRENT_DATE,
    receipt_image TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);