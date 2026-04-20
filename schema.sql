-- ==============================================================================
-- EEP PORTAL: MASTER DATABASE SCHEMA (v2.8)
-- ==============================================================================

-- 1. STAFF (The Security Bouncers & Users)
CREATE TABLE staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hash TEXT NOT NULL,
    role TEXT NOT NULL,
    program_id INTEGER DEFAULT 1, 
    program_scope TEXT DEFAULT 'EEP'
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
    meal_plan TEXT DEFAULT 'None',
    comment TEXT,
    previous_school TEXT,
    status TEXT DEFAULT 'Active',
    profile_picture TEXT DEFAULT 'default.png',
    household_id INTEGER REFERENCES households(id), 
    mother_name TEXT, 
    father_name TEXT, 
    caregiver_relationship TEXT, 
    program_id INTEGER DEFAULT 1, 
    updated_at DATETIME
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
    total_class_days INTEGER,
    scanned_document TEXT,
    grade_level TEXT,
    school_name TEXT,
    total_score REAL,
    overall_average REAL,
    overall_grade TEXT,
    flexible_rank TEXT,
    FOREIGN KEY(student_id) REFERENCES students(id)
);

-- 4. SUBJECTS (The Curriculum Settings)
CREATE TABLE subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER DEFAULT 99,
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
    learning_difficulties_detail TEXT,
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
    substance_abuse_evidence TEXT,
    general_notes TEXT,
    staff_notes TEXT,
    letter_quarter TEXT,
    letter_year TEXT,
    letter_given TEXT,
    letter_translated TEXT,
    letter_scanned TEXT,
    letter_sent TEXT,
    letter_notes TEXT,
    parent_working_notes TEXT,
    support_level INTEGER,
    church_attendance TEXT,
    child_jobs TEXT,
    risk_level INTEGER,
    student_story TEXT,
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
    description TEXT,
    attendance_count INTEGER DEFAULT 1,
    student_id INTEGER,
    FOREIGN KEY(student_id) REFERENCES students(id)
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

-- 12. HOUSEHOLDS (The Family Linkage Engine)
CREATE TABLE households (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guardian_name TEXT NOT NULL,
    phone_number TEXT,
    slum_area TEXT,
    household_income TEXT,
    living_conditions TEXT,
    notes TEXT,
    caregiver_picture TEXT, 
    adults_in_home TEXT, 
    total_headcount INTEGER
);

-- 13. PROGRAMS (The Context Switcher)
CREATE TABLE programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    icon TEXT
);

-- 14. TASKS (The Calendar Engine)
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    due_date DATETIME NOT NULL,
    end_date DATETIME,           -- NEW v2.8: Support for date ranges
    priority TEXT DEFAULT 'Medium',
    status TEXT DEFAULT 'Pending',
    student_id INTEGER,
    staff_id INTEGER,
    program_id INTEGER DEFAULT 1,
    is_team_task INTEGER DEFAULT 0,
    is_holiday INTEGER DEFAULT 0 -- NEW v2.8: Explicit flag to suppress nutrition logs
);

-- 15. SYSTEM SETTINGS
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 16. ROLE PERMISSIONS (The Granular CRUD Matrix)
CREATE TABLE role_permissions (
    role TEXT PRIMARY KEY,
    can_edit_profiles INTEGER DEFAULT 0,
    can_create_profiles INTEGER DEFAULT 0,
    can_update_profiles INTEGER DEFAULT 0,
    can_manage_academics INTEGER DEFAULT 0,
    can_create_academics INTEGER DEFAULT 0,
    can_update_academics INTEGER DEFAULT 0,
    can_delete_academics INTEGER DEFAULT 0,
    can_manage_followups INTEGER DEFAULT 0,
    can_create_followups INTEGER DEFAULT 0,
    can_update_followups INTEGER DEFAULT 0,
    can_upload_files INTEGER DEFAULT 0,
    can_create_files INTEGER DEFAULT 0,
    can_delete_files INTEGER DEFAULT 0,
    can_create_expenses INTEGER DEFAULT 0,
    can_export_data INTEGER DEFAULT 0
);