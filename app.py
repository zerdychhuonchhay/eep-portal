"""
CS50 FINAL PROJECT CITATION:
The core architecture, routing map, and database schema for this application
are my original work. Google Gemini was utilized as an AI coding assistant to
help generate boilerplate HTML, refine complex CSS/Bootstrap styling, architect
the dynamic JavaScript filtering/zoom logic, and assist in debugging SQL syntax.
"""

# ==============================================================================
# NEIGHBORHOOD: SETUP & CONFIG (Imports, Secret Key, Folders, Database connection)
# ==============================================================================
import io
import csv
import os
import time
from datetime import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, Response, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from helpers import login_required, admin_required

# 1. Turn on the flask application
app = Flask(__name__)

# SECURITY: Flask needs a secret key to use 'session' memory
app.secret_key = "super_secret_eep_key"

# --- FILE UPLOAD CONFIGURATION ---
UPLOAD_FOLDER = 'static/uploads/documents'
PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'webp', 'heic', 'heif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER

# Ensure both upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# 2. Connect to your database
db = SQL("sqlite:///eep.db")

# ==============================================================================
# THE SPY: AUDIT LOG HELPER (Records actions silently)
# ==============================================================================
def log_action(description):
    """Silently record what a staff member just did"""
    if "user_id" in session:
        # Capture the Browser/Device Info
        user_agent_raw = request.headers.get('User-Agent', 'Unknown Device')
        
        # Clean it up to be readable (e.g., "Chrome on Windows")
        device_info = "Unknown Device"
        if "Windows" in user_agent_raw:
            os_name = "Windows"
        elif "Macintosh" in user_agent_raw or "Mac OS" in user_agent_raw:
            os_name = "Mac"
        elif "iPhone" in user_agent_raw or "iPad" in user_agent_raw:
            os_name = "iOS"
        elif "Android" in user_agent_raw:
            os_name = "Android"
        else:
            os_name = "Unknown OS"

        if "Chrome" in user_agent_raw and "Edg" not in user_agent_raw:
            browser = "Chrome"
        elif "Edg" in user_agent_raw:
            browser = "Edge"
        else:
            browser = "Unknown Browser"
            
        if user_agent_raw != 'Unknown Device':
            device_info = f"{browser} on {os_name}"

        # CRASH-PROOF FIX: Try to insert with device_info, fallback if the column doesn't exist yet!
        try:
            db.execute("INSERT INTO audit_logs (staff_id, action, device_info, timestamp) VALUES (?, ?, ?, datetime('now', 'localtime'))", 
                       session["user_id"], description, device_info)
        except Exception:
            db.execute("INSERT INTO audit_logs (staff_id, action, timestamp) VALUES (?, ?, datetime('now', 'localtime'))", 
                       session["user_id"], description)

# ==============================================================================
# GLOBAL NOTIFICATION ENGINE
# ==============================================================================
@app.context_processor
def inject_pending_staff():
    """Globally injects the count of pending staff into all HTML templates"""
    if session.get("role") in ["Admin", "Director"]:
        try:
            count = db.execute("SELECT COUNT(*) as count FROM staff WHERE role = 'Pending'")[0]['count']
            return dict(pending_staff_count=count)
        except Exception:
            return dict(pending_staff_count=0)
    return dict(pending_staff_count=0)

# ==============================================================================
# NEIGHBORHOOD: DASHBOARD & STATS (Dashboard route, Impact logic, Activity logging)
# ==============================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """Smart Dashboard Router based on Active Program Context"""
    
    # Check which hat the user is currently wearing (Default to 1: EEP)
    program_id = session.get("program_id", 1) 
    
    # ==============================================================
    # HAT 1: GOVT AFFAIRS & CENTRAL ADMIN (program_id == 0)
    # ==============================================================
    if program_id == 0:
        # We will build the real Government stats in Phase 8!
        # For now, we just load the template so you can see the layout.
        today_date = datetime.now().strftime('%Y-%m-%d')
        return render_template("dashboard_global.html", date_now=today_date)
        
    # ==============================================================
    # HAT 2: EEP MANAGEMENT (program_id == 1)
    # ==============================================================
    elif program_id == 1:
        # AUDIT FIX: Enforce timeframe as an integer so the database doesn't crash!
        try:
            months = int(request.args.get('timeframe', 1))
        except ValueError:
            months = 1

        # 2. Stats: Enrollment Breakdown
        active_kids = db.execute(
            "SELECT gender, COUNT(*) as count FROM students WHERE status = 'Active' GROUP BY gender")
        total_active = sum(row['count'] for row in active_kids)
        boys = next((row['count'] for row in active_kids if row['gender'] == 'Male'), 0)
        girls = next((row['count'] for row in active_kids if row['gender'] == 'Female'), 0)

        uni_kids = db.execute(
            "SELECT COUNT(*) as count FROM students WHERE status = 'Active' AND grade_level LIKE '%University%'")[0]['count']
        vocal_kids = db.execute(
            "SELECT COUNT(*) as count FROM students WHERE status = 'Active' AND grade_level LIKE '%Vocational%'")[0]['count']

        # 3. Stats: Services (Filtered by Time)
        lunch_kids_count = db.execute("SELECT COUNT(*) as count FROM students WHERE status = 'Active' AND meal_plan = 'Daily Hot Lunch'")[0]['count']
        estimated_workdays = months * 22
        max_possible_meals = lunch_kids_count * estimated_workdays

        missed_meals = db.execute("""
            SELECT COUNT(*) as total FROM student_services
            WHERE service_type = 'Missed Hot Lunch'
            AND service_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        holidays_logged = db.execute("""
            SELECT COUNT(*) as total FROM student_services
            WHERE service_type = 'Holiday - No Meals'
            AND service_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0
        holiday_missed_meals = holidays_logged * lunch_kids_count

        calculated_meals = max_possible_meals - missed_meals - holiday_missed_meals
        meals = max(0, calculated_meals)

        parent_meetings = db.execute("""
            SELECT COUNT(*) as total FROM activities
            WHERE activity_type = 'Parent Meeting' AND activity_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        # 4. Stats: Impact (Filtered by Time)
        housing_supports = db.execute("""
            SELECT SUM(attendance_count) as total FROM activities
            WHERE activity_type = 'Housing Support' AND activity_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        other_activities = db.execute("""
            SELECT COUNT(*) as total FROM activities
            WHERE activity_type NOT IN ('Hot Meal', 'Parent Meeting', 'Housing Support')
            AND activity_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        # 5. Stats: Academic Excellence
        top_performers = db.execute(
            "SELECT COUNT(*) as count FROM monthly_reports WHERE CAST(class_rank AS INTEGER) <= 10 AND CAST(class_rank AS INTEGER) > 0")[0]['count']

        graduates = db.execute(
            "SELECT COUNT(*) as count FROM students WHERE status = 'Graduated'")[0]['count']

        # 6. Priority Alerts
        academic_alerts = db.execute("""
            SELECT s.first_name, s.last_name, s.id, r.overall_average, r.academic_year, r.month
            FROM students s JOIN monthly_reports r ON s.id = r.student_id
            WHERE r.overall_average < 50 AND r.overall_average IS NOT NULL
            AND s.status = 'Active'
            ORDER BY r.academic_year DESC, r.id DESC LIMIT 5
        """)

        protection_alerts = db.execute("""
            SELECT s.first_name, s.last_name, s.id, f.id as followup_id, f.child_protection_concerns
            FROM students s JOIN followups f ON s.id = f.student_id
            WHERE f.child_protection_concerns NOT IN ('No', 'None', 'N/A', '')
            AND f.child_protection_concerns IS NOT NULL
            AND (f.alert_status IS NULL OR f.alert_status = 'Active')
            AND s.status = 'Active'
            ORDER BY f.followup_date DESC LIMIT 5
        """)

        # 7. Smart Sponsor Letters Logic
        current_month = datetime.now().month
        current_year = str(datetime.now().year)
        if current_month <= 3: current_quarter = 'Q1'
        elif current_month <= 6: current_quarter = 'Q2'
        elif current_month <= 9: current_quarter = 'Q3'
        else: current_quarter = 'Q4'

        missing_letters_raw = db.execute("""
            SELECT s.id, s.first_name, s.last_name,
                   MAX(f.letter_given) as given,
                   MAX(f.letter_translated) as translated,
                   MAX(f.letter_scanned) as scanned,
                   MAX(f.letter_sent) as sent,
                   MAX(f.id) as followup_id
            FROM students s
            LEFT JOIN followups f ON s.id = f.student_id AND f.letter_quarter = ? AND f.letter_year = ?
            WHERE s.status = 'Active'
            GROUP BY s.id
            HAVING sent IS NULL OR sent != 'Yes'
            ORDER BY s.first_name ASC
        """, current_quarter, current_year)

        missing_letters = []
        for student in missing_letters_raw:
            if student['scanned'] == 'Yes':
                student['status_badge'] = "Ready to Send"
                student['status_color'] = "primary"
            elif student['translated'] == 'Yes':
                student['status_badge'] = "Waiting to Scan"
                student['status_color'] = "info"
            elif student['given'] == 'Yes':
                student['status_badge'] = "Needs Translation"
                student['status_color'] = "warning"
            else:
                student['status_badge'] = "Not Started"
                student['status_color'] = "danger"
            missing_letters.append(student)

        # 8. Audit Log Feed (Only for Admins)
        recent_activity = []
        if session.get("role") in ["Admin", "System PM", "Director"]:
            try:
                recent_activity = db.execute("""
                    SELECT a.action, a.timestamp, a.device_info, s.username 
                    FROM audit_logs a
                    JOIN staff s ON a.staff_id = s.id
                    ORDER BY a.timestamp DESC LIMIT 15
                """)
            except Exception:
                recent_activity = db.execute("""
                    SELECT a.action, a.timestamp, 'Unknown' as device_info, s.username 
                    FROM audit_logs a
                    JOIN staff s ON a.staff_id = s.id
                    ORDER BY a.timestamp DESC LIMIT 15
                """)

        date_now = datetime.now().strftime('%Y-%m-%d')

        return render_template("executive_dashboard.html",
                               total_active=total_active, boys=boys, girls=girls,
                               uni_kids=uni_kids, vocal_kids=vocal_kids,
                               meals=meals, meetings=parent_meetings,
                               housing_supports=housing_supports, other_activities=other_activities,
                               top_performers=top_performers, graduates=graduates,
                               academic_alerts=academic_alerts, protection_alerts=protection_alerts,
                               missing_letters=missing_letters, current_quarter=current_quarter, current_year=current_year,
                               timeframe=months, date_now=date_now, recent_activity=recent_activity)


@app.route("/log_activity", methods=["POST"])
@login_required
def log_activity():
    activity_type = request.form.get("activity_type")
    activity_date = request.form.get("activity_date")
    attendance_count = request.form.get("attendance_count")

    db.execute("""
        INSERT INTO activities (activity_type, activity_date, attendance_count)
        VALUES (?, ?, ?)
    """, activity_type, activity_date, attendance_count)

    log_action(f"Logged Community Activity: {activity_type} ({attendance_count} attendees)")

    flash(f"Successfully logged {activity_type} on {activity_date}!", "success")
    return redirect("/dashboard")


@app.route("/log_services", methods=["GET", "POST"])
@login_required
def log_services():
    """Bulk log daily meals, missing meals, or individual support"""
    if request.method == "POST":
        service_date = request.form.get("service_date")
        service_type = request.form.get("service_type")
        notes = request.form.get("notes")

        # request.form.getlist grabs EVERY checked box and puts the IDs in a python list!
        student_ids = request.form.getlist("student_ids")

        if not service_date or not service_type:
            flash("Date and Service Type are required.", "danger")
            return redirect("/log_services")

        if not student_ids:
            flash("You must select at least one student.", "warning")
            return redirect("/log_services")

        # Loop through the checked students and save a record for each
        for sid in student_ids:
            db.execute("""
                INSERT INTO student_services (student_id, service_date, service_type, notes)
                VALUES (?, ?, ?, ?)
            """, sid, service_date, service_type, notes)

        log_action(f"Logged Bulk Service: {service_type} for {len(student_ids)} students")

        flash(f"Successfully logged '{service_type}' for {len(student_ids)} students on {service_date}!", "success")
        return redirect("/dashboard")

    students = db.execute("""
        SELECT id, first_name, last_name, khmer_name, grade_level, meal_plan
        FROM students
        WHERE status = 'Active'
        ORDER BY first_name ASC
    """)
    today_date = datetime.now().strftime('%Y-%m-%d')

    return render_template("log_services.html", students=students, today_date=today_date)


@app.route("/resolve_alert/<int:followup_id>", methods=["POST"])
@login_required
def resolve_alert(followup_id):
    """Mark a protection alert as resolved"""
    db.execute("""
        UPDATE followups
        SET alert_status = 'Resolved'
        WHERE id = ?
    """, followup_id)
    
    log_action(f"Resolved Risk Alert from Follow-up #{followup_id}")
    flash("Alert marked as resolved!", "success")
    return redirect("/dashboard")


# ==============================================================================
# NEIGHBORHOOD: FIELD CALENDAR & TASK MANAGEMENT
# ==============================================================================

@app.route("/setup_calendar")
@login_required
def setup_calendar():
    """Run this ONCE to create the tasks table in your database!"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            due_date DATETIME NOT NULL,
            priority TEXT DEFAULT 'Medium',
            status TEXT DEFAULT 'Pending',
            student_id INTEGER,
            staff_id INTEGER,
            program_id INTEGER DEFAULT 1
        )
    """)
    
    # SMART UPGRADE: Safely add the column if they already have the old table
    try:
        db.execute("ALTER TABLE tasks ADD COLUMN program_id INTEGER DEFAULT 1")
    except Exception:
        pass 

    flash("Calendar Database Table successfully created/upgraded! You are ready to go.", "success")
    return redirect("/calendar")

@app.route("/calendar")
@login_required
def field_calendar():
    """Renders the main Calendar UI"""
    program_id = session.get("program_id", 1)
    
    if program_id == 0:
        students = db.execute("SELECT id, first_name, last_name, ngo_id FROM students WHERE status = 'Active' ORDER BY first_name ASC")
    else:
        students = db.execute("SELECT id, first_name, last_name, ngo_id FROM students WHERE status = 'Active' AND program_id = ? ORDER BY first_name ASC", program_id)
    
    pending_tasks = db.execute("""
        SELECT t.*, s.first_name, s.last_name, st.username as creator_name
        FROM tasks t 
        LEFT JOIN students s ON t.student_id = s.id 
        LEFT JOIN staff st ON t.staff_id = st.id
        WHERE t.status = 'Pending' AND t.staff_id = ?
        ORDER BY t.due_date ASC LIMIT 15
    """, session["user_id"])
    
    return render_template("calendar.html", students=students, pending_tasks=pending_tasks)

@app.route("/api/tasks")
@login_required
def api_tasks():
    """Background API that feeds data to FullCalendar.js"""
    view_mode = request.args.get("view", "my")
    program_id = session.get("program_id", 1)
    
    if view_mode == "team":
        if program_id == 0:
            tasks = db.execute("""
                SELECT t.*, st.username as creator_name 
                FROM tasks t 
                LEFT JOIN staff st ON t.staff_id = st.id
            """)
        else:
            tasks = db.execute("""
                SELECT t.*, st.username as creator_name 
                FROM tasks t 
                LEFT JOIN staff st ON t.staff_id = st.id 
                WHERE t.program_id = ?
            """, program_id)
    else:
        tasks = db.execute("""
            SELECT t.*, st.username as creator_name 
            FROM tasks t 
            LEFT JOIN staff st ON t.staff_id = st.id 
            WHERE t.staff_id = ?
        """, session["user_id"])
        
    events = []
    
    for t in tasks:
        color = "#0d6efd" 
        
        if t["status"] == "Completed":
            color = "#198754" 
        elif t["priority"] == "High":
            color = "#dc3545" 
        elif t["priority"] == "Low":
            color = "#6c757d" 

        events.append({
            "id": t["id"],
            "title": t["title"],
            "start": t["due_date"],
            "color": color,
            "extendedProps": {
                "description": t["description"],
                "status": t["status"],
                "priority": t["priority"],
                "creator_name": t["creator_name"]
            }
        })
        
    return jsonify(events)

@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    """Saves a new task to the database"""
    title = request.form.get("title")
    due_date = request.form.get("due_date")
    description = request.form.get("description")
    priority = request.form.get("priority")
    student_id = request.form.get("student_id")
    
    program_id = session.get("program_id", 1)
    
    if not student_id or student_id == "None":
        student_id = None
        
    if not title or not due_date:
        flash("Task Title and Date are required.", "danger")
        return redirect("/calendar")
        
    db.execute("""
        INSERT INTO tasks (title, description, due_date, priority, status, student_id, staff_id, program_id)
        VALUES (?, ?, ?, ?, 'Pending', ?, ?, ?)
    """, title, description, due_date, priority, student_id, session["user_id"], program_id)
    
    log_action(f"Created new task: {title}")
    flash("Task successfully added to your calendar!", "success")
    return redirect("/calendar")

@app.route("/complete_task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    """Marks a task as completed"""
    db.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", task_id)
    log_action(f"Marked task #{task_id} as Completed")
    flash("Task marked as completed! Great job.", "success")
    return redirect("/calendar")

@app.route("/delete_task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
    """Deletes a task from the calendar"""
    task = db.execute("SELECT staff_id, title FROM tasks WHERE id = ?", task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect("/calendar")
        
    if session["role"] not in ["Admin", "Director"] and task[0]["staff_id"] != session["user_id"]:
        flash("Unauthorized: You can only delete your own tasks.", "danger")
        return redirect("/calendar")
        
    db.execute("DELETE FROM tasks WHERE id = ?", task_id)
    log_action(f"Deleted task: {task[0]['title']}")
    flash("Task successfully deleted.", "success")
    return redirect("/calendar")


# ==============================================================================
# NEIGHBORHOOD: ACADEMICS
# ==============================================================================

@app.route("/academics")
@login_required
def academics():
    """Show Master Gradebook for all students"""
    active_students = db.execute("SELECT id, ngo_id, first_name, last_name FROM students WHERE status = 'Active' ORDER BY first_name")

    reports = db.execute("""
        SELECT r.id as report_id, r.month, r.academic_year, r.semester, r.overall_average, r.class_rank, r.grade_level as historical_grade, r.school_name,
               s.id as student_id, s.ngo_id, s.first_name, s.last_name, s.grade_level as current_grade
        FROM monthly_reports r
        JOIN students s ON r.student_id = s.id
        WHERE s.status = 'Active'
        ORDER BY r.id DESC
    """)

    all_grades = db.execute("""
        SELECT g.report_id, COALESCE(s.name, g.custom_subject_name) as subject_name, g.score, g.max_score
        FROM grades g
        LEFT JOIN subjects s ON g.subject_id = s.id
        ORDER BY s.sort_order ASC, subject_name ASC
    """)

    academic_records = []
    for report in reports:
        report_grades = []
        for grade in all_grades:
            if grade["report_id"] == report["report_id"]:
                report_grades.append({
                    "name": grade["subject_name"],
                    "score": grade["score"],
                    "max_score": grade["max_score"]
                })
        report["subjects"] = report_grades
        academic_records.append(report)

    return render_template("academics.html", academic_records=academic_records, active_students=active_students)

@app.template_filter('get_badge')
def get_badge_filter(score, max_score):
    if not max_score: return None
    try:
        s, m = float(score), float(max_score)
        if m == 0: return None
        percentage = (s / m) * 100
        if percentage >= 90: return ('A', 'success')
        elif percentage >= 80: return ('B', 'primary')
        elif percentage >= 70: return ('C', 'info')
        elif percentage >= 60: return ('D', 'warning')
        elif percentage >= 50: return ('E', 'warning')
        else: return ('F', 'danger')
    except (ValueError, TypeError):
        return None

@app.route("/add_report/<int:student_id>", methods=["GET", "POST"])
@login_required
def add_report(student_id):
    """Add a monthly academic report for a student"""
    if request.method == "POST":
        month = request.form.get("month")
        semester = request.form.get("semester")
        academic_year = request.form.get("academic_year")
        grade_level = request.form.get("grade_level")
        school_name = request.form.get("school_name")
        class_rank = request.form.get("class_rank")
        teacher_comment = request.form.get("teacher_comment")
        attendance_days = request.form.get("attendance_days")
        source_url = request.form.get("source_url")

        if source_url == "None" or not source_url:
            source_url = None

        if not month or not academic_year:
            return render_template("apology.html", message="Report Month and Academic Year are required. Please use your browser's BACK arrow to return to the form without losing your typed grades.")

        existing_report = db.execute("""
            SELECT id FROM monthly_reports
            WHERE student_id = ? AND month = ? AND academic_year = ?
        """, student_id, month, academic_year)

        if existing_report:
            return render_template("apology.html", message=f"A report for {month} {academic_year} already exists! Please use your browser's BACK arrow to return to the form and change the month.")

        file = request.files.get('scanned_document')
        scanned_filename = None
        if file and file.filename != '' and allowed_file(file.filename):
            original_name = secure_filename(file.filename)
            scanned_filename = f"report_{student_id}_{int(time.time())}_{original_name}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], scanned_filename))

        report_id = db.execute("""
            INSERT INTO monthly_reports (student_id, month, academic_year, semester, class_rank, teacher_comment, attendance_days, scanned_document, grade_level, school_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, student_id, month, academic_year, semester, class_rank, teacher_comment, attendance_days, scanned_filename, grade_level, school_name)

        # Subject Logic
        subjects = db.execute("SELECT * FROM subjects")
        calculated_total = 0.0
        calculated_max = 0.0
        has_numeric = False
        missing_max = False

        for subject in subjects:
            sub_id = subject['id']
            score = request.form.get(f"score_{sub_id}")
            max_score = request.form.get(f"max_score_{sub_id}")

            if score:
                db.execute("INSERT INTO grades (report_id, subject_id, score, max_score) VALUES (?, ?, ?, ?)",
                           report_id, sub_id, score, max_score)
                try:
                    calculated_total += float(score)
                    if max_score and str(max_score).strip() != "":
                        calculated_max += float(max_score)
                    else:
                        missing_max = True
                    has_numeric = True
                except ValueError:
                    pass

        # Wildcard Row Logic
        custom_name = request.form.get("custom_subject_name")
        custom_score = request.form.get("custom_score")
        custom_max = request.form.get("custom_max_score")

        if custom_score:
            db.execute("INSERT INTO grades (report_id, subject_id, score, max_score, custom_subject_name) VALUES (?, 0, ?, ?, ?)",
                       report_id, custom_score, custom_max, custom_name)
            try:
                calculated_total += float(custom_score)
                if custom_max and str(custom_max).strip() != "":
                    calculated_max += float(custom_max)
                else:
                    missing_max = True
                has_numeric = True
            except ValueError:
                pass

        # Calculate Logic
        if has_numeric and calculated_max > 0 and not missing_max:
            calculated_avg = round((calculated_total / calculated_max) * 100, 2)
        else:
            calculated_avg = None

        if calculated_avg is not None:
            if calculated_avg >= 90: calculated_grade = "A"
            elif calculated_avg >= 80: calculated_grade = "B"
            elif calculated_avg >= 70: calculated_grade = "C"
            elif calculated_avg >= 60: calculated_grade = "D"
            elif calculated_avg >= 50: calculated_grade = "E"
            else: calculated_grade = "F"
        else:
            calculated_grade = "N/A"

        manual_total = request.form.get("manual_total_score")
        manual_average = request.form.get("manual_average")
        manual_grade = request.form.get("manual_grade")

        try:
            final_total = float(manual_total) if manual_total and str(manual_total).strip() != "" else (calculated_total if has_numeric else None)
        except ValueError:
            final_total = calculated_total if has_numeric else None

        try:
            final_avg = float(manual_average) if manual_average and str(manual_average).strip() != "" else calculated_avg
        except ValueError:
            final_avg = calculated_avg

        final_grade = str(manual_grade).strip() if manual_grade and str(manual_grade).strip() != "" else calculated_grade

        db.execute("""
            UPDATE monthly_reports
            SET total_score = ?, overall_average = ?, overall_grade = ?
            WHERE id = ?
        """, final_total, final_avg, final_grade, report_id)

        log_action(f"Added academic report for Student ID: {student_id}")
        flash("Academic report successfully recorded!", "success")
        return redirect(source_url) if source_url else redirect(f"/student/{student_id}")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    subjects = db.execute("SELECT * FROM subjects ORDER BY category ASC, sort_order ASC, name ASC")
    return render_template("add_report.html", student=student, subjects=subjects)


@app.route("/edit_report/<int:report_id>", methods=["GET", "POST"])
@login_required
def edit_report(report_id):
    report_data = db.execute("SELECT * FROM monthly_reports WHERE id = ?", report_id)
    if len(report_data) != 1:
        return render_template("apology.html", message="Report not found")
    report = report_data[0]
    student_id = report["student_id"]

    if request.method == "POST":
        month = request.form.get("month")
        semester = request.form.get("semester")
        academic_year = request.form.get("academic_year")
        grade_level = request.form.get("grade_level")
        school_name = request.form.get("school_name")
        attendance_days = request.form.get("attendance_days")
        teacher_comment = request.form.get("teacher_comment")
        class_rank = request.form.get("class_rank")
        source_url = request.form.get("source_url")

        if source_url == "None" or not source_url:
            source_url = None

        if not month or not academic_year:
            return render_template("apology.html", message="Month and Academic Year are required. Please use your browser's BACK arrow to return without losing data.")

        existing_report = db.execute("""
            SELECT id FROM monthly_reports
            WHERE student_id = ? AND month = ? AND academic_year = ? AND id != ?
        """, student_id, month, academic_year, report_id)

        if existing_report:
            return render_template("apology.html", message="Another report for this month and year already exists. Please use your browser's BACK arrow to return and change the month.")

        file = request.files.get('scanned_document')
        if file and file.filename != '' and allowed_file(file.filename):
            original_name = secure_filename(file.filename)
            scanned_filename = f"report_{student_id}_{int(time.time())}_{original_name}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], scanned_filename))
            db.execute("UPDATE monthly_reports SET scanned_document = ? WHERE id = ?", scanned_filename, report_id)

        db.execute("""
            UPDATE monthly_reports
            SET month = ?, academic_year = ?, semester = ?, attendance_days = ?, teacher_comment = ?, class_rank = ?, grade_level = ?, school_name = ?
            WHERE id = ?
        """, month, academic_year, semester, attendance_days, teacher_comment, class_rank, grade_level, school_name, report_id)

        # 1. Process Standard Subjects
        subjects = db.execute("SELECT * FROM subjects")
        for subject in subjects:
            sub_id = subject['id']
            score = request.form.get(f"score_{sub_id}")
            max_score = request.form.get(f"max_score_{sub_id}")
            existing_grade = db.execute("SELECT id FROM grades WHERE report_id = ? AND subject_id = ?", report_id, sub_id)

            if score:
                if existing_grade:
                    db.execute("UPDATE grades SET score = ?, max_score = ? WHERE report_id = ? AND subject_id = ?", score, max_score, report_id, sub_id)
                else:
                    db.execute("INSERT INTO grades (report_id, subject_id, score, max_score) VALUES (?, ?, ?, ?)", report_id, sub_id, score, max_score)
            elif existing_grade:
                db.execute("DELETE FROM grades WHERE report_id = ? AND subject_id = ?", report_id, sub_id)

        # 2. Process The Wildcard Subject
        custom_name = request.form.get("custom_subject_name")
        custom_score = request.form.get("custom_score")
        custom_max = request.form.get("custom_max_score")
        existing_custom = db.execute("SELECT id FROM grades WHERE report_id = ? AND subject_id = 0", report_id)

        if custom_score:
            if existing_custom:
                db.execute("UPDATE grades SET score = ?, max_score = ?, custom_subject_name = ? WHERE report_id = ? AND subject_id = 0",
                           custom_score, custom_max, custom_name, report_id)
            else:
                db.execute("INSERT INTO grades (report_id, subject_id, score, max_score, custom_subject_name) VALUES (?, 0, ?, ?, ?)",
                           report_id, custom_score, custom_max, custom_name)
        elif existing_custom:
            db.execute("DELETE FROM grades WHERE report_id = ? AND subject_id = 0", report_id)

        # 3. Calculate Math
        current_grades = db.execute("SELECT score, max_score FROM grades WHERE report_id = ?", report_id)
        calculated_total = 0.0
        calculated_max = 0.0
        has_numeric = False
        missing_max = False

        for g in current_grades:
            try:
                calculated_total += float(g['score'])
                if g['max_score'] and str(g['max_score']).strip() != "":
                    calculated_max += float(g['max_score'])
                else:
                    missing_max = True
                has_numeric = True
            except ValueError:
                pass

        if has_numeric and calculated_max > 0 and not missing_max:
            calculated_avg = round((calculated_total / calculated_max) * 100, 2)
        else:
            calculated_avg = None

        if calculated_avg is not None:
            if calculated_avg >= 90: calculated_grade = "A"
            elif calculated_avg >= 80: calculated_grade = "B"
            elif calculated_avg >= 70: calculated_grade = "C"
            elif calculated_avg >= 60: calculated_grade = "D"
            elif calculated_avg >= 50: calculated_grade = "E"
            else: calculated_grade = "F"
        else:
            calculated_grade = "N/A"

        manual_total = request.form.get("manual_total_score")
        manual_average = request.form.get("manual_average")
        manual_grade = request.form.get("manual_grade")

        try:
            final_total = float(manual_total) if manual_total and str(manual_total).strip() != "" else (calculated_total if has_numeric else None)
        except ValueError:
            final_total = calculated_total if has_numeric else None

        try:
            final_avg = float(manual_average) if manual_average and str(manual_average).strip() != "" else calculated_avg
        except ValueError:
            final_avg = calculated_avg

        final_grade = str(manual_grade).strip() if manual_grade and str(manual_grade).strip() != "" else calculated_grade

        db.execute("UPDATE monthly_reports SET total_score = ?, overall_average = ?, overall_grade = ? WHERE id = ?", final_total, final_avg, final_grade, report_id)

        log_action(f"Edited academic report for Student ID: {student_id}")
        flash("Academic report successfully updated!", "success")
        return redirect(source_url) if source_url else redirect(f"/student/{student_id}")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    subjects = db.execute("SELECT * FROM subjects ORDER BY category ASC, sort_order ASC, name ASC")
    grades = db.execute("SELECT * FROM grades WHERE report_id = ?", report_id)
    existing_grades = {g['subject_id']: g for g in grades}

    return render_template("edit_report.html", student=student, report=report, subjects=subjects, existing_grades=existing_grades)


@app.route("/delete_report/<int:report_id>", methods=["POST"])
@login_required
@admin_required 
def delete_report(report_id):
    report = db.execute("SELECT student_id, scanned_document FROM monthly_reports WHERE id = ?", report_id)
    if not report:
        flash("Report not found.", "danger")
        return redirect(request.referrer or "/")

    student_id = report[0]["student_id"]
    scanned_doc = report[0]["scanned_document"]

    if scanned_doc:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], scanned_doc)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.execute("DELETE FROM grades WHERE report_id = ?", report_id)
    db.execute("DELETE FROM monthly_reports WHERE id = ?", report_id)

    log_action(f"DELETED academic report #{report_id} for Student ID: {student_id}")
    flash("Academic record deleted successfully.", "success")
    return redirect(request.referrer or f"/student/{student_id}")

# ==============================================================================
# NEIGHBORHOOD: STUDENT MANAGEMENT (Index/Roster, Add Student, Edit Student)
# ==============================================================================

@app.route("/")
@login_required
def index():
    """Smart Homepage that changes based on the user's active program view"""
    program_id = session.get("program_id", 1) 
    
    try:
        db.execute("ALTER TABLE students ADD COLUMN updated_at DATETIME")
    except Exception:
        pass

    if program_id == 0:
        staff_members = db.execute("SELECT * FROM staff ORDER BY role ASC, username ASC")
        return render_template("hr_roster.html", staff_members=staff_members, title="Global HR Directory")
        
    elif program_id == 1:
        staff = db.execute("SELECT username FROM staff WHERE id = ?", session["user_id"])
        username = staff[0]["username"] if staff else "Staff"

        recent_students = db.execute("""
            SELECT id, first_name, last_name, khmer_name, ngo_id, profile_picture 
            FROM students 
            WHERE status = 'Active' 
            ORDER BY COALESCE(updated_at, joined_date, id) DESC LIMIT 5
        """)
        
        all_active_students = db.execute("SELECT * FROM students WHERE status = 'Active' ORDER BY first_name")
        return render_template("index.html", username=username, recent_students=recent_students, students=all_active_students)

@app.route("/roster")
@login_required
def roster():
    """Show the full active roster (Moved from index)"""
    students = db.execute("SELECT * FROM students WHERE status != 'Dropped Out' AND status != 'Graduated' ORDER BY first_name")
    return render_template("roster.html", students=students, title="Active Roster")

@app.route("/archive")
@login_required
def archive():
    """Show dropped out / graduated students"""
    students = db.execute("SELECT * FROM students WHERE status = 'Dropped Out' OR status = 'Graduated' ORDER BY first_name")
    return render_template("roster.html", students=students, title="Archived Students")

@app.route("/guide")
@login_required
def guide():
    """Show the Beta Testing Instructions"""
    return render_template("guide.html")

@app.route("/add_student", methods=["GET", "POST"])
@login_required
def add_student():
    """Add a new student to the database"""
    if request.method == "POST":
        ngo_id = request.form.get("ngo_id")
        status = request.form.get("status")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        khmer_name = request.form.get("khmer_name")
        gender = request.form.get("gender")
        dob = request.form.get("dob")
        joined_date = request.form.get("joined_date")
        guardian_name = request.form.get("guardian_name")
        phone = request.form.get("phone_number")
        slum = request.form.get("slum_area")
        current_school = request.form.get("current_school")
        grade = request.form.get("grade_level")
        meal_plan = request.form.get("meal_plan")
        comment = request.form.get("comment")
        household_id = request.form.get("household_id")
        
        caregiver_relationship = request.form.get("caregiver_relationship")
        mother_name = request.form.get("mother_name")
        father_name = request.form.get("father_name")

        if not ngo_id or not first_name or not last_name:
            return render_template("apology.html", message="NGO ID, First Name, and Last Name are required. Please use your browser's BACK arrow to return without losing data.")

        if not household_id:
            household_id = None 

        try:
            db.execute("""
                INSERT INTO students
                (ngo_id, status, first_name, last_name, khmer_name, gender, dob, joined_date, guardian_name, phone_number, slum_area, current_school, grade_level, meal_plan, comment, household_id, caregiver_relationship, mother_name, father_name, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, ngo_id, status, first_name, last_name, khmer_name, gender, dob, joined_date, guardian_name, phone, slum, current_school, grade, meal_plan, comment, household_id, caregiver_relationship, mother_name, father_name)
            
            student_id = db.execute("SELECT id FROM students WHERE ngo_id = ?", ngo_id)[0]['id']
            
            file = request.files.get('profile_picture')
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                saved_name = f"profile_{student_id}_{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], saved_name))
                db.execute("UPDATE students SET profile_picture = ? WHERE id = ?", saved_name, student_id)
            
            log_action(f"Added new student profile: {first_name} {last_name}")
            flash(f"{first_name} added successfully!", "success")
            return redirect("/")

        except ValueError:
            return render_template("apology.html", message="A student with that NGO ID already exists. Please use your browser's BACK arrow to return without losing data.")

    else:
        today_date = datetime.now().strftime('%Y-%m-%d')
        households = db.execute("""
            SELECT h.id, h.guardian_name, h.phone_number, GROUP_CONCAT(s.first_name, ', ') as kids
            FROM households h
            LEFT JOIN students s ON h.id = s.household_id
            GROUP BY h.id
            ORDER BY h.guardian_name ASC
        """)
        return render_template("add_student.html", today_date=today_date, households=households)


@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
@login_required
def edit_student(id):
    """Edit an existing student's profile"""
    if request.method == "POST":
        ngo_id = request.form.get("ngo_id")
        status = request.form.get("status")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        khmer_name = request.form.get("khmer_name")
        gender = request.form.get("gender")
        dob = request.form.get("dob")
        joined_date = request.form.get("joined_date")
        guardian_name = request.form.get("guardian_name")
        phone = request.form.get("phone_number")
        slum = request.form.get("slum_area")
        current_school = request.form.get("current_school")
        grade = request.form.get("grade_level")
        meal_plan = request.form.get("meal_plan")
        comment = request.form.get("comment")
        
        household_id = request.form.get("household_id")
        if not household_id:
            household_id = None 

        caregiver_relationship = request.form.get("caregiver_relationship")
        mother_name = request.form.get("mother_name")
        father_name = request.form.get("father_name")

        if not ngo_id or not first_name or not last_name:
            return render_template("apology.html", message="NGO ID, First Name, and Last Name are required. Please use your browser's BACK arrow to return without losing data.")

        try:
            db.execute("""
                UPDATE students 
                SET ngo_id = ?, first_name = ?, last_name = ?, khmer_name = ?, gender = ?, 
                    dob = ?, joined_date = ?, guardian_name = ?, phone_number = ?, 
                    slum_area = ?, current_school = ?, grade_level = ?, meal_plan = ?, 
                    comment = ?, status = ?, household_id = ?, caregiver_relationship = ?, 
                    mother_name = ?, father_name = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, ngo_id, first_name, last_name, khmer_name, gender, dob, joined_date, 
                 guardian_name, phone, slum, current_school, grade, 
                 meal_plan, comment, status, household_id, caregiver_relationship, mother_name, father_name, id)
            
            log_action(f"Edited student profile: {first_name} {last_name}")
            flash("Student updated successfully!", "success")
            return redirect(f"/student/{id}")

        except ValueError:
            return render_template("apology.html", message="Update failed. NGO ID might conflict with another student. Please use your browser's BACK arrow to return.")

    else:
        student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
        if len(student_data) != 1:
            return render_template("apology.html", message="Student not found")

        student = student_data[0]
        households = db.execute("""
            SELECT h.id, h.guardian_name, h.phone_number, GROUP_CONCAT(s.first_name, ', ') as kids
            FROM households h
            LEFT JOIN students s ON h.id = s.household_id
            GROUP BY h.id
            ORDER BY h.guardian_name ASC
        """)
        
        return render_template("edit_student.html", student=student, households=households)


@app.route("/update_avatar/<int:id>", methods=["POST"])
@login_required
def update_avatar(id):
    file = request.files.get('profile_picture')
    if file and file.filename != '' and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        saved_name = f"profile_{id}_{int(time.time())}_{filename}"
        file.save(os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], saved_name))
        
        db.execute("UPDATE students SET profile_picture = ? WHERE id = ?", saved_name, id)
        log_action(f"Updated profile picture for Student ID: {id}")
        flash("Photo updated!", "success")
    return redirect(f"/student/{id}")


@app.route("/manage_households", methods=["GET", "POST"])
@login_required
def manage_households():
    """Enterprise view to manage all family units"""
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            guardian = request.form.get("guardian_name")
            phone = request.form.get("phone_number")
            slum = request.form.get("slum_area")
            
            if not guardian:
                flash("Guardian Name is required.", "danger")
            else:
                db.execute("INSERT INTO households (guardian_name, phone_number, slum_area) VALUES (?, ?, ?)",
                           guardian, phone, slum)
                log_action(f"Created new household: {guardian}")
                flash(f"Household for {guardian} created successfully!", "success")
        
        elif action == "edit":
            hh_id = request.form.get("household_id")
            guardian = request.form.get("guardian_name")
            phone = request.form.get("phone_number")
            slum = request.form.get("slum_area")
            
            db.execute("UPDATE households SET guardian_name = ?, phone_number = ?, slum_area = ? WHERE id = ?",
                       guardian, phone, slum, hh_id)
            log_action(f"Updated Household ID {hh_id}: {guardian}")
            flash("Household updated successfully! All linked students will now show this new data.", "success")
            
        elif action == "delete":
            hh_id = request.form.get("household_id")
            linked_students = db.execute("SELECT COUNT(*) as count FROM students WHERE household_id = ?", hh_id)[0]['count']
            if linked_students > 0:
                flash(f"Cannot delete. There are {linked_students} students still linked to this household.", "danger")
            else:
                db.execute("DELETE FROM households WHERE id = ?", hh_id)
                log_action(f"Deleted Household ID {hh_id}")
                flash("Empty household deleted successfully.", "success")
                
        return redirect("/manage_households")

    else:
        households = db.execute("""
            SELECT h.id, h.guardian_name, h.phone_number, h.slum_area, 
                   COUNT(s.id) as student_count,
                   GROUP_CONCAT(s.first_name, ', ') as kids
            FROM households h
            LEFT JOIN students s ON h.id = s.household_id
            GROUP BY h.id
            ORDER BY h.guardian_name ASC
        """)
        return render_template("manage_households.html", households=households)


@app.route("/household/<int:id>", methods=["GET", "POST"])
@login_required
def household_profile(id):
    """Dedicated dashboard for a single family/household"""
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "unlink":
            student_id = request.form.get("student_id")
            db.execute("UPDATE students SET household_id = NULL WHERE id = ?", student_id)
            log_action(f"Unlinked Student ID {student_id} from Household ID {id}")
            flash("Student successfully unlinked from this family.", "success")
            
        elif action == "edit_household":
            guardian = request.form.get("guardian_name")
            phone = request.form.get("phone_number")
            slum = request.form.get("slum_area")
            adults = request.form.get("adults_in_home")
            headcount = request.form.get("total_headcount")
            
            file = request.files.get('caregiver_picture')
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                saved_name = f"household_{id}_{int(time.time())}_{filename}"
                file.save(os.path.join(app.config['PROFILE_UPLOAD_FOLDER'], saved_name))
                db.execute("UPDATE households SET caregiver_picture = ? WHERE id = ?", saved_name, id)

            db.execute("""
                UPDATE households 
                SET guardian_name = ?, phone_number = ?, slum_area = ?, adults_in_home = ?, total_headcount = ? 
                WHERE id = ?
            """, guardian, phone, slum, adults, headcount, id)
            
            log_action(f"Updated Household ID {id} profile (Blended Family Data)")
            flash("Caregiver and Household details updated successfully.", "success")

        elif action == "edit_kinship":
            student_id = request.form.get("student_id")
            caregiver_relation = request.form.get("caregiver_relationship")
            mother = request.form.get("mother_name")
            father = request.form.get("father_name")
            
            db.execute("""
                UPDATE students 
                SET caregiver_relationship = ?, mother_name = ?, father_name = ?
                WHERE id = ?
            """, caregiver_relation, mother, father, student_id)
            
            log_action(f"Updated biological parents & kinship for Student ID {student_id}")
            flash("Kinship and biological parent details updated successfully!", "success")
            
        return redirect(f"/household/{id}")

    else:
        household = db.execute("SELECT * FROM households WHERE id = ?", id)
        if not household:
            return render_template("apology.html", message="Household not found")
            
        kids = db.execute("SELECT * FROM students WHERE household_id = ? ORDER BY dob ASC", id)
        return render_template("household_profile.html", household=household[0], kids=kids)


# ==============================================================================
# NEIGHBORHOOD: STUDENT PROFILES
# ==============================================================================

@app.route("/student/<int:id>")
@login_required
def student_profile(id):
    student = db.execute("SELECT * FROM students WHERE id = ?", id)[0]

    siblings = []
    if student.get("household_id"):
        siblings = db.execute("""
            SELECT id, first_name, last_name, profile_picture, status, caregiver_relationship 
            FROM students 
            WHERE household_id = ? AND id != ?
            ORDER BY dob ASC
        """, student["household_id"], id)

    academic_years_raw = db.execute("SELECT DISTINCT academic_year FROM monthly_reports WHERE student_id = ? ORDER BY academic_year DESC", id)
    unique_years = [row['academic_year'] for row in academic_years_raw if row['academic_year']]

    timeframe = request.args.get("timeframe")

    if timeframe and timeframe.isdigit():
        reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? ORDER BY id DESC LIMIT ?", id, int(timeframe))
    elif timeframe and "-" in timeframe:
        reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? AND academic_year = ? ORDER BY id DESC", id, timeframe)
    else:
        reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? ORDER BY id DESC", id)

    followups = db.execute("SELECT * FROM followups WHERE student_id = ? ORDER BY id DESC", id)
    documents = db.execute("SELECT * FROM documents WHERE student_id = ? ORDER BY id DESC", id)

    raw_grades = db.execute("""
        SELECT g.*, COALESCE(s.name, g.custom_subject_name) as subject_name
        FROM grades g LEFT JOIN subjects s ON g.subject_id = s.id
        WHERE g.report_id IN (SELECT id FROM monthly_reports WHERE student_id = ?)
        ORDER BY s.sort_order ASC, subject_name ASC
    """, id)

    grades_by_report = {}
    for g in raw_grades:
        if g['report_id'] not in grades_by_report:
            grades_by_report[g['report_id']] = []
        grades_by_report[g['report_id']].append(g)

    # 🚨 THE BRIDGE FIX: Attach your grouped grades to each report so HTML can read it!
    for report in reports:
        report['subjects'] = grades_by_report.get(report['id'], [])

    return render_template("student_profile.html", student=student, reports=reports, followups=followups, documents=documents, timeframe=timeframe, unique_years=unique_years, siblings=siblings)
# ==============================================================================

@app.route("/add_followup/<int:student_id>", methods=["GET", "POST"])
@login_required
def add_followup(student_id):
    if request.method == "POST":
        followup_date = request.form.get("followup_date")
        completed_by = request.form.get("completed_by")

        if not followup_date or not completed_by:
            return render_template("apology.html", message="Date and Completed By are required. Please use your browser's BACK arrow to return without losing data.")

        risk_factors_list = request.form.getlist("risk_factors")
        risk_factors = ", ".join(risk_factors_list) if risk_factors_list else "None"

        letter_quarter = request.form.get("letter_quarter")
        letter_year = request.form.get("letter_year")
        letter_given = request.form.get("letter_given")
        letter_translated = request.form.get("letter_translated")
        letter_scanned = request.form.get("letter_scanned")
        letter_sent = request.form.get("letter_sent")
        letter_notes = request.form.get("letter_notes")

        db.execute("""
            INSERT INTO followups (
                student_id, followup_date, location, completed_by,
                physical_health, physical_health_detail, social_interaction, social_interaction_detail,
                home_life, home_life_detail, evidence_drugs_violence,
                learning_difficulties, behavior_in_class, behavior_in_class_detail,
                peer_issues, peer_issues_detail, teacher_involvement, teacher_involvement_detail,
                transportation, transportation_detail, tutoring_participation, tutoring_participation_detail,
                risk_factors, risk_details, child_protection_concerns, trafficking_risk, general_notes,
                letter_quarter, letter_year, letter_given, letter_translated, letter_scanned, letter_sent, letter_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, student_id, followup_date, request.form.get("location"), completed_by,
                   request.form.get("physical_health"), request.form.get("physical_health_detail"),
                   request.form.get("social_interaction"), request.form.get("social_interaction_detail"),
                   request.form.get("home_life"), request.form.get("home_life_detail"), request.form.get("evidence_drugs_violence"),
                   request.form.get("learning_difficulties"), request.form.get("behavior_in_class"), request.form.get("behavior_in_class_detail"),
                   request.form.get("peer_issues"), request.form.get("peer_issues_detail"), request.form.get("teacher_involvement"), request.form.get("teacher_involvement_detail"),
                   request.form.get("transportation"), request.form.get("transportation_detail"), request.form.get("tutoring_participation"), request.form.get("tutoring_participation_detail"),
                   risk_factors, request.form.get("risk_details"), request.form.get("child_protection_concerns"), request.form.get("trafficking_risk"), request.form.get("general_notes"),
                   letter_quarter, letter_year, letter_given, letter_translated, letter_scanned, letter_sent, letter_notes)

        log_action(f"Added Social Work Follow-Up for Student ID: {student_id}")
        flash("Follow-up successfully recorded!", "success")
        return redirect(f"/student/{student_id}")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    current_year = datetime.now().year
    today_date = datetime.now().strftime('%Y-%m-%d')
    staff_query = db.execute("SELECT username FROM staff WHERE id = ?", session["user_id"])
    current_user = staff_query[0]["username"] if staff_query else ""

    return render_template("add_followup.html", student=student, current_year=current_year, today_date=today_date, current_user=current_user)


@app.route("/edit_followup/<int:followup_id>", methods=["GET", "POST"])
@login_required
def edit_followup(followup_id):
    followup_data = db.execute("SELECT * FROM followups WHERE id = ?", followup_id)
    if len(followup_data) != 1:
        return render_template("apology.html", message="Follow-up not found")
    followup = followup_data[0]
    student_id = followup["student_id"]

    if request.method == "POST":
        followup_date = request.form.get("followup_date")
        completed_by = request.form.get("completed_by")

        if not followup_date or not completed_by:
            return render_template("apology.html", message="Date and Completed By are required. Please use your browser's BACK arrow to return without losing data.")

        risk_factors_list = request.form.getlist("risk_factors")
        risk_factors = ", ".join(risk_factors_list) if risk_factors_list else "None"

        letter_quarter = request.form.get("letter_quarter")
        letter_year = request.form.get("letter_year")
        letter_given = request.form.get("letter_given")
        letter_translated = request.form.get("letter_translated")
        letter_scanned = request.form.get("letter_scanned")
        letter_sent = request.form.get("letter_sent")
        letter_notes = request.form.get("letter_notes")

        db.execute("""
            UPDATE followups SET
                followup_date = ?, location = ?, completed_by = ?,
                physical_health = ?, physical_health_detail = ?, social_interaction = ?, social_interaction_detail = ?,
                home_life = ?, home_life_detail = ?, evidence_drugs_violence = ?,
                learning_difficulties = ?, behavior_in_class = ?, behavior_in_class_detail = ?,
                peer_issues = ?, peer_issues_detail = ?, teacher_involvement = ?, teacher_involvement_detail = ?,
                transportation = ?, transportation_detail = ?, tutoring_participation = ?, tutoring_participation_detail = ?,
                risk_factors = ?, risk_details = ?, child_protection_concerns = ?, trafficking_risk = ?, general_notes = ?,
                letter_quarter = ?, letter_year = ?, letter_given = ?, letter_translated = ?, letter_scanned = ?, letter_sent = ?, letter_notes = ?
            WHERE id = ?
        """, followup_date, request.form.get("location"), completed_by,
                   request.form.get("physical_health"), request.form.get("physical_health_detail"), request.form.get("social_interaction"), request.form.get("social_interaction_detail"),
                   request.form.get("home_life"), request.form.get("home_life_detail"), request.form.get("evidence_drugs_violence"),
                   request.form.get("learning_difficulties"), request.form.get("behavior_in_class"), request.form.get("behavior_in_class_detail"),
                   request.form.get("peer_issues"), request.form.get("peer_issues_detail"), request.form.get("teacher_involvement"), request.form.get("teacher_involvement_detail"),
                   request.form.get("transportation"), request.form.get("transportation_detail"), request.form.get("tutoring_participation"), request.form.get("tutoring_participation_detail"),
                   risk_factors, request.form.get("risk_details"), request.form.get("child_protection_concerns"), request.form.get("trafficking_risk"), request.form.get("general_notes"),
                   letter_quarter, letter_year, letter_given, letter_translated, letter_scanned, letter_sent, letter_notes, followup_id)

        log_action(f"Edited Social Work Follow-Up for Student ID: {student_id}")
        flash("Follow-up successfully updated!", "success")
        return redirect(f"/student/{student_id}")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    return render_template("edit_followup.html", student=student, followup=followup)


@app.route("/bulk_followup", methods=["GET", "POST"])
@login_required
def bulk_followup():
    """Log a single follow-up note for multiple students at once"""
    if request.method == "POST":
        followup_date = request.form.get("followup_date")
        completed_by = request.form.get("completed_by")
        location = request.form.get("location")
        general_notes = request.form.get("general_notes")
        
        student_ids = request.form.getlist("student_ids")

        if not followup_date or not completed_by:
            flash("Date and Completed By are required.", "danger")
            return redirect("/bulk_followup")

        if not student_ids:
            flash("You must select at least one student from the list.", "warning")
            return redirect("/bulk_followup")

        for sid in student_ids:
            db.execute("""
                INSERT INTO followups (
                    student_id, followup_date, location, completed_by, general_notes
                ) VALUES (?, ?, ?, ?, ?)
            """, sid, followup_date, location, completed_by, general_notes)

        log_action(f"Logged Group Follow-Up ({location}) for {len(student_ids)} students")

        flash(f"Successfully logged group follow-up for {len(student_ids)} students!", "success")
        return redirect("/dashboard")

    students = db.execute("""
        SELECT id, first_name, last_name, khmer_name, ngo_id, grade_level 
        FROM students 
        WHERE status = 'Active' 
        ORDER BY first_name ASC
    """)
    today_date = datetime.now().strftime('%Y-%m-%d')
    staff_query = db.execute("SELECT username FROM staff WHERE id = ?", session["user_id"])
    current_user = staff_query[0]["username"] if staff_query else ""

    return render_template("bulk_followup.html", students=students, today_date=today_date, current_user=current_user)


# ==============================================================================
# NEIGHBORHOOD: FILING CABINET
# ==============================================================================

@app.route('/upload_document/<int:student_id>', methods=['POST'])
@login_required
def upload_document(student_id):
    if 'document_file' not in request.files:
        flash("No file part", "danger")
        return redirect(f"/student/{student_id}")

    file = request.files['document_file']
    doc_type = request.form.get('document_type')

    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(f"/student/{student_id}")

    if file and allowed_file(file.filename):
        original_name = secure_filename(file.filename)
        saved_name = f"{student_id}_{int(time.time())}_{original_name}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_name))

        db.execute("INSERT INTO documents (student_id, original_filename, saved_filename, document_type) VALUES (?, ?, ?, ?)",
                   student_id, original_name, saved_name, doc_type)
        
        log_action(f"Uploaded Document '{doc_type}' for Student ID: {student_id}")
        flash(f"{doc_type} successfully uploaded!", "success")
    else:
        flash("Invalid file type. Allowed: PNG, JPG, PDF, DOC, DOCX", "danger")

    return redirect(f"/student/{student_id}")


@app.route("/delete_document/<int:doc_id>")
@login_required
@admin_required 
def delete_document(doc_id):
    doc = db.execute("SELECT * FROM documents WHERE id = ?", doc_id)
    if not doc:
        return "Document not found", 404

    student_id = doc[0]['student_id']
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], doc[0]['saved_filename'])

    if os.path.exists(file_path):
        os.remove(file_path)

    db.execute("DELETE FROM documents WHERE id = ?", doc_id)
    log_action(f"DELETED Document for Student ID: {student_id}")
    flash("Document deleted successfully.", "success")
    return redirect(url_for('student_profile', id=student_id))


# ==============================================================================
# NEIGHBORHOOD: EXPORTS & UTILITIES
# ==============================================================================

@app.route('/export_students')
@login_required
def export_students():
    students = db.execute("SELECT id, ngo_id, first_name, last_name, gender, dob, status, slum_area, current_school, grade_level FROM students ORDER BY last_name")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['System ID', 'NGO ID', 'First Name', 'Last Name', 'Gender', 'DOB', 'Status', 'Slum Area', 'School', 'Grade Level'])
    for s in students:
        writer.writerow([s['id'], s['ngo_id'], s['first_name'], s['last_name'], s['gender'], s['dob'], s['status'], s['slum_area'], s['current_school'], s['grade_level']])

    output.seek(0)
    log_action("Exported Student Roster to CSV")
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=eep_student_roster.csv"})

@app.route('/export_grades')
@login_required
def export_grades():
    """Export Master Gradebook to CSV"""
    reports = db.execute("""
        SELECT s.ngo_id, s.first_name, s.last_name, m.academic_year, m.month, m.grade_level, m.overall_average, m.class_rank
        FROM monthly_reports m
        JOIN students s ON m.student_id = s.id
        ORDER BY m.academic_year DESC, m.month DESC
    """)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['NGO ID', 'First Name', 'Last Name', 'Academic Year', 'Month', 'Grade Level', 'Overall Average', 'Class Rank'])
    
    for r in reports:
        writer.writerow([r['ngo_id'], r['first_name'], r['last_name'], r['academic_year'], r['month'], r['grade_level'], r['overall_average'], r['class_rank']])
    
    output.seek(0)
    log_action("Exported Master Gradebook to CSV")
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=eep_grades_{datetime.now().strftime('%Y%m%d')}.csv"})


@app.route('/export_staff')
@login_required
def export_staff():
    """Placeholder for Phase 8: Export Global Staff"""
    flash("Staff Export feature will be fully activated in Phase 8!", "info")
    return redirect(request.referrer or "/")


@app.route('/export_compliance')
@login_required
def export_compliance():
    """Placeholder for Phase 8: Export Compliance Logs"""
    flash("Compliance Export feature will be fully activated in Phase 8!", "info")
    return redirect(request.referrer or "/")


@app.route('/sw.js')
def sw():
    """Serve the Service Worker from the root scope for PWA"""
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')


@app.route('/manifest.json')
def manifest():
    """Serve the manifest from the root scope for PWA"""
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')


@app.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    """Master Control Panel for the NGO"""
    
    # 1. AUTO-BUILDER: Ensure the settings table exists so we don't crash
    db.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Ensure default academic year exists
    if not db.execute("SELECT * FROM system_settings WHERE key = 'current_academic_year'"):
        db.execute("INSERT INTO system_settings (key, value) VALUES ('current_academic_year', '2025-2026')")

    if request.method == "POST":
        action = request.form.get("action")
        
        # ==========================================
        # SUBJECT MANAGEMENT
        # ==========================================
        if action == "add_subject":
            new_subject = request.form.get("new_subject")
            category = request.form.get("category", "General") 
            if not new_subject:
                flash("Subject name cannot be empty", "danger")
            elif db.execute("SELECT id FROM subjects WHERE name = ?", new_subject):
                flash(f"Subject '{new_subject}' already exists.", "warning")
            else:
                max_sort = db.execute("SELECT MAX(sort_order) as max_val FROM subjects")[0]["max_val"]
                next_sort = (max_sort + 1) if max_sort is not None else 99
                db.execute("INSERT INTO subjects (name, sort_order, category) VALUES (?, ?, ?)", new_subject, next_sort, category)
                log_action(f"Added new master subject: {new_subject}")
                flash(f"Successfully added '{new_subject}'!", "success")

        elif action == "update_subjects":
            subjects = db.execute("SELECT id FROM subjects")
            for subject in subjects:
                sort_order = request.form.get(f"sort_{subject['id']}")
                category = request.form.get(f"category_{subject['id']}")
                if sort_order is not None and str(sort_order).strip() != "":
                    db.execute("UPDATE subjects SET sort_order = ?, category = ? WHERE id = ?", sort_order, category, subject['id'])
            log_action("Updated Subject Master Settings")
            flash("Subjects successfully updated!", "success")
            
        elif action == "delete_subject":
            sub_id = request.form.get("subject_id")
            # SECURITY: Don't let them delete a subject if grades are attached!
            grade_count = db.execute("SELECT COUNT(*) as count FROM grades WHERE subject_id = ?", sub_id)[0]['count']
            if grade_count > 0:
                flash(f"Cannot delete! There are {grade_count} grades linked to this subject. Change their grades first.", "danger")
            else:
                sub_name = db.execute("SELECT name FROM subjects WHERE id = ?", sub_id)[0]['name']
                db.execute("DELETE FROM subjects WHERE id = ?", sub_id)
                log_action(f"Deleted Subject: {sub_name}")
                flash(f"Subject '{sub_name}' permanently deleted.", "success")

        # ==========================================
        # PROGRAM MANAGEMENT
        # ==========================================
        elif action == "add_program":
            name = request.form.get("program_name")
            icon = request.form.get("program_icon", "bi-circle")
            if name:
                db.execute("INSERT INTO programs (name, icon) VALUES (?, ?)", name, icon)
                log_action(f"Added new NGO Program: {name}")
                flash(f"Program '{name}' added successfully!", "success")
                
        elif action == "edit_program":
            prog_id = request.form.get("program_id")
            name = request.form.get("program_name")
            icon = request.form.get("program_icon")
            db.execute("UPDATE programs SET name = ?, icon = ? WHERE id = ?", name, icon, prog_id)
            log_action(f"Updated NGO Program ID: {prog_id}")
            flash("Program updated successfully!", "success")
            
        elif action == "delete_program":
            prog_id = request.form.get("program_id")
            # Protect Core Programs from being deleted
            if int(prog_id) in [0, 1]:
                flash("Security Error: Cannot delete core system programs (Global / EEP).", "danger")
            else:
                student_count = db.execute("SELECT COUNT(*) as count FROM students WHERE program_id = ?", prog_id)[0]['count']
                if student_count > 0:
                    flash(f"Cannot delete! {student_count} students are enrolled in this program.", "danger")
                else:
                    db.execute("DELETE FROM programs WHERE id = ?", prog_id)
                    log_action("Deleted an NGO Program")
                    flash("Program successfully deleted.", "success")

        # ==========================================
        # SYSTEM VARIABLES
        # ==========================================
        elif action == "update_system":
            acad_year = request.form.get("current_academic_year")
            if acad_year:
                db.execute("UPDATE system_settings SET value = ? WHERE key = 'current_academic_year'", acad_year)
                log_action(f"Updated Global Academic Year to {acad_year}")
                flash("System variables updated successfully!", "success")

        return redirect("/settings")

    # --- GET REQUEST: Load the page data ---
    subjects = db.execute("SELECT * FROM subjects ORDER BY category ASC, sort_order ASC, name ASC")
    programs = db.execute("SELECT * FROM programs ORDER BY id ASC")
    
    # Extract system settings into a simple dictionary for Jinja
    sys_raw = db.execute("SELECT * FROM system_settings")
    sys_settings = {row['key']: row['value'] for row in sys_raw}

    return render_template("settings.html", subjects=subjects, programs=programs, sys_settings=sys_settings)


# ==============================================================================
# NEIGHBORHOOD: AUTHENTICATION & STAFF MANAGEMENT
# ==============================================================================

@app.route("/manage_staff", methods=["GET", "POST"])
@login_required
@admin_required
def manage_staff():
    """Enterprise dashboard to add, edit, and reset staff accounts."""
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            username = request.form.get("username")
            password = request.form.get("password")
            role = request.form.get("role")
            program_scope = request.form.get("program_scope")
            
            if not username or not password or not role or not program_scope:
                flash("Error: All fields are required to create an account.", "danger")
                return redirect("/manage_staff")
                
            hash_pass = generate_password_hash(password)
            try:
                db.execute("INSERT INTO staff (username, hash, role, program_scope) VALUES (?, ?, ?, ?)", 
                           username, hash_pass, role, program_scope)
                log_action(f"Registered new staff member: {username} ({role})")
                flash(f"Account created successfully for {username}!", "success")
            except ValueError:
                flash("Error: Username already exists.", "danger")
                
        elif action == "edit":
            staff_id = request.form.get("staff_id")
            new_role = request.form.get("role")
            new_scope = request.form.get("program_scope")
            
            if int(staff_id) == session["user_id"] and new_role != "Admin":
                flash("Security Warning: You cannot remove your own Admin privileges.", "warning")
            else:
                db.execute("UPDATE staff SET role = ?, program_scope = ? WHERE id = ?", new_role, new_scope, staff_id)
                log_action(f"Updated permissions for Staff ID {staff_id} to {new_role}/{new_scope}")
                flash("Staff permissions updated successfully.", "success")
                
        elif action == "reset_password":
            staff_id = request.form.get("staff_id")
            new_hash = generate_password_hash("123456")
            db.execute("UPDATE staff SET hash = ? WHERE id = ?", new_hash, staff_id)
            
            staff_name = db.execute("SELECT username FROM staff WHERE id = ?", staff_id)[0]['username']
            log_action(f"Forced password reset for {staff_name}")
            flash(f"Password for {staff_name} has been reset to '123456'. Tell them to log in and change it immediately.", "info")

        return redirect("/manage_staff")

    else:
        staff_members = db.execute("SELECT id, username, role, program_scope FROM staff ORDER BY role ASC, username ASC")
        return render_template("manage_staff.html", staff_members=staff_members)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Public registration: Users create account, but stay 'Pending' until Admin approves"""
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username or not password or password != confirmation:
            flash("Invalid input or passwords do not match.", "danger")
            return redirect("/register")

        hash_pass = generate_password_hash(password)
        try:
            db.execute("INSERT INTO staff (username, hash, role, program_scope) VALUES (?, ?, 'Pending', 'None')", 
                       username, hash_pass)
            
            log_action(f"New public account request submitted: {username}")
            flash("Account requested! Please wait for an Administrator to approve your access.", "success")
            return redirect("/login")
        except ValueError:
            flash("That username already exists.", "danger")
            return redirect("/register")
    else:
        return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash("Error: Must provide username and password", "danger")
            return redirect("/login")

        rows = db.execute("SELECT * FROM staff WHERE username = ?", username)

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            flash("Error: Invalid username and/or password", "danger")
            return redirect("/login")
            
        if rows[0]["role"] == "Pending":
            flash("Your account is currently pending. Please ask your Administrator to approve your access.", "warning")
            return redirect("/login")

        session["user_id"] = rows[0]["id"]
        session["role"] = rows[0]["role"]
        
        program_id = rows[0].get("program_id", 1) 
        try:
            program_info = db.execute("SELECT name, icon FROM programs WHERE id = ?", program_id)
            if program_info:
                session["program_id"] = program_id
                session["program_name"] = program_info[0]["name"]
                session["program_icon"] = program_info[0]["icon"]
            else:
                session["program_id"] = 0
                session["program_name"] = "Central Administration"
                session["program_icon"] = "bi-buildings-fill"
        except Exception:
            session["program_id"] = 1
            session["program_name"] = "EEP Program"
            session["program_icon"] = "bi-book-fill"
        
        log_action("Logged into the system")
        return redirect("/")

    return render_template("login.html")

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow users to securely change their own password"""
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirmation = request.form.get("confirmation")

        if not old_password or not new_password or not confirmation:
            flash("Error: All fields are required.", "danger")
            return redirect("/change_password")

        if new_password != confirmation:
            flash("Error: New passwords do not match.", "danger")
            return redirect("/change_password")

        user = db.execute("SELECT hash FROM staff WHERE id = ?", session["user_id"])
        if not check_password_hash(user[0]["hash"], old_password):
            flash("Error: Incorrect current password.", "danger")
            return redirect("/change_password")

        new_hash = generate_password_hash(new_password)
        db.execute("UPDATE staff SET hash = ? WHERE id = ?", new_hash, session["user_id"])
        
        log_action("Changed their account password")
        flash("Success! Your password has been securely updated.", "success")
        return redirect("/")

    else:
        return render_template("change_password.html")

@app.route("/switch_program/<int:pid>")
@login_required
def switch_program(pid):
    """Allows Admins/Directors to switch their active program view"""
    if session.get("role") not in ["Admin", "Director"]:
        flash("Unauthorized: Only Admins can switch program views.", "danger")
        return redirect(request.referrer or "/")
        
    if pid == 0:
        session["program_id"] = 0
        session["program_name"] = "Central Administration"
        session["program_icon"] = "bi-buildings-fill"
    else:
        program = db.execute("SELECT name, icon FROM programs WHERE id = ?", pid)
        if program:
            session["program_id"] = pid
            session["program_name"] = program[0]["name"]
            session["program_icon"] = program[0]["icon"]
            
    flash(f"Switched context to: {session['program_name']}", "info")
    return redirect(request.referrer or "/")

@app.route("/logout")
def logout():
    """Log user out"""
    log_action("Logged out of the system")
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)