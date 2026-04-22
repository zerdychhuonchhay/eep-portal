"""
CS50 FINAL PROJECT CITATION:
The core architecture, routing map, and database schema for this application
are my original work. Google Gemini was utilized as an AI coding assistant to
help generate boilerplate HTML, refine complex CSS/Bootstrap styling, architect
the dynamic JavaScript filtering/zoom logic, and assist in debugging SQL syntax.
"""

# ==============================================================================
# NEIGHBORHOOD: SETUP & CONFIG
# ==============================================================================
import io
import csv
import os
import time
import json
import calendar
from datetime import datetime, timedelta
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for, Response, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# 🚨 THE DRY REFACTOR: Importing all our tools from helpers.py!
from helpers import login_required, admin_required, permission_required, real_admin_required, calculate_gpa, get_subject_grade_data, allowed_file, handle_file_upload

# 1. Turn on the flask application
app = Flask(__name__)

# SECURITY: Flask needs a secret key to use 'session' memory
app.secret_key = "super_secret_eep_key"

# PWA LOGOUT FIX: Make sessions last 30 days instead of expiring when app closes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# --- FILE UPLOAD CONFIGURATION ---
UPLOAD_FOLDER = 'static/uploads/documents'
PROFILE_UPLOAD_FOLDER = 'static/uploads/profiles'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_UPLOAD_FOLDER'] = PROFILE_UPLOAD_FOLDER

# Ensure both upload directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_UPLOAD_FOLDER, exist_ok=True)

# 2. Connect to your database
db = SQL("sqlite:///eep.db")


# ==============================================================================
# GLOBAL CONTEXT PROCESSORS & AUDIT LOGS
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

@app.context_processor
def inject_translator():
    """Phase 6: Injects the translation dictionary into all HTML templates"""
    translation_file = os.path.join(app.root_path, 'translations.json')
    translations = {}
    if os.path.exists(translation_file):
        with open(translation_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
            
    def translate(key):
        lang = session.get('lang', 'en') # Defaults to English
        return translations.get(key, {}).get(lang, key) # Fallback to the raw key if missing
        
    return dict(_=translate)

def log_action(description):
    """Silently record what a staff member just did"""
    if "user_id" in session:
        user_agent_raw = request.headers.get('User-Agent', 'Unknown Device')
        device_info = "Unknown Device"
        
        if "Windows" in user_agent_raw: os_name = "Windows"
        elif "Macintosh" in user_agent_raw or "Mac OS" in user_agent_raw: os_name = "Mac"
        elif "iPhone" in user_agent_raw or "iPad" in user_agent_raw: os_name = "iOS"
        elif "Android" in user_agent_raw: os_name = "Android"
        else: os_name = "Unknown OS"

        if "Chrome" in user_agent_raw and "Edg" not in user_agent_raw: browser = "Chrome"
        elif "Edg" in user_agent_raw: browser = "Edge"
        elif "Safari" in user_agent_raw and "Chrome" not in user_agent_raw: browser = "Safari"
        else: browser = "Unknown Browser"
            
        if user_agent_raw != 'Unknown Device':
            device_info = f"{browser} on {os_name}"

        try:
            db.execute("INSERT INTO audit_logs (staff_id, action, device_info, timestamp) VALUES (?, ?, ?, datetime('now', 'localtime'))", 
                       session["user_id"], description, device_info)
        except Exception:
            db.execute("INSERT INTO audit_logs (staff_id, action, timestamp) VALUES (?, ?, datetime('now', 'localtime'))", 
                       session["user_id"], description)


# ==============================================================================
# NEIGHBORHOOD: AUTHENTICATION & STAFF MANAGEMENT
# ==============================================================================

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
            # Hardcoded to 'Pending' so they can't see any data yet!
            db.execute("INSERT INTO staff (username, hash, role, program_id) VALUES (?, ?, 'Pending', 1)", 
                       username, hash_pass)
            
            log_action(f"New public account request submitted: {username}")
            # ✅ UPDATED CUSTOM MESSAGE
            flash("Your request has been submitted! Please wait for approval, or contact an Admin for faster processing.", "success")
            return redirect("/login")
        except ValueError:
            flash("That username already exists.", "danger")
            return redirect("/register")
    else:
        return render_template("auth/register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in and build their permissions backpack"""
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
            
        # 🚨 THE BOUNCER: Reject them if they are still 'Pending'
        if rows[0]["role"] == "Pending":
            flash("Your account is currently pending. Please ask your Administrator to approve your access.", "warning")
            return redirect("/login")

        # Standard Login Success
        session.permanent = True
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        session["role"] = rows[0]["role"]
        
        # 🛡️ THE DYNAMIC CRUD PERMISSIONS MATRIX
        try:
            perms = db.execute("SELECT * FROM role_permissions WHERE role = ?", rows[0]["role"])
            if perms:
                p = perms[0]
                # Coarse legacy fallbacks
                session["can_edit_profiles"] = bool(p["can_edit_profiles"])
                session["can_manage_academics"] = bool(p["can_manage_academics"])
                session["can_manage_followups"] = bool(p["can_manage_followups"])
                session["can_upload_files"] = bool(p["can_upload_files"])
                
                # Granular CRUD 
                session["can_create_profiles"] = bool(p.get("can_create_profiles", p["can_edit_profiles"]))
                session["can_update_profiles"] = bool(p.get("can_update_profiles", p["can_edit_profiles"]))
                session["can_create_academics"] = bool(p.get("can_create_academics", p["can_manage_academics"]))
                session["can_update_academics"] = bool(p.get("can_update_academics", p["can_manage_academics"]))
                session["can_delete_academics"] = bool(p.get("can_delete_academics", 0))
                session["can_create_followups"] = bool(p.get("can_create_followups", p["can_manage_followups"]))
                session["can_update_followups"] = bool(p.get("can_update_followups", p["can_manage_followups"]))
                session["can_create_files"] = bool(p.get("can_create_files", p["can_upload_files"]))
                session["can_delete_files"] = bool(p.get("can_delete_files", 0))
                session["can_create_expenses"] = bool(p.get("can_create_expenses", 0))
                session["can_export_data"] = bool(p["can_export_data"])
            else:
                session["can_create_profiles"] = False
                session["can_update_profiles"] = False
                session["can_create_academics"] = False
                session["can_update_academics"] = False
                session["can_delete_academics"] = False
                session["can_create_followups"] = False
                session["can_update_followups"] = False
                session["can_create_files"] = False
                session["can_delete_files"] = False
                session["can_create_expenses"] = False
                session["can_export_data"] = False
        except Exception as e:
            print("RBAC LOAD ERROR: Make sure /settings has run the auto-healer.", str(e))
            pass
        
        # 🛡️ BULLETPROOF ADMIN OVERRIDE
        # No matter what the database says, Admins ALWAYS get full UI buttons
        if session["role"] == "Admin":
            session["can_edit_profiles"] = True
            session["can_create_profiles"] = True
            session["can_update_profiles"] = True
            session["can_manage_academics"] = True
            session["can_create_academics"] = True
            session["can_update_academics"] = True
            session["can_delete_academics"] = True
            session["can_manage_followups"] = True
            session["can_create_followups"] = True
            session["can_update_followups"] = True
            session["can_upload_files"] = True
            session["can_create_files"] = True
            session["can_delete_files"] = True
            session["can_create_expenses"] = True
            session["can_export_data"] = True

        # Establish Program Context (Hat)
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

    return render_template("auth/login.html")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Allow users to manage their profile, picture, and password"""
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "update_profile":
            new_username = request.form.get("username")
            
            # Handle picture upload
            profile_picture = request.files.get("profile_picture")
            if profile_picture and profile_picture.filename != '':
                # Assuming you have your handle_file_upload helper from students
                saved_name, _ = handle_file_upload(profile_picture, session["user_id"], "staff", app.config['UPLOAD_FOLDER'])
                if saved_name:
                    db.execute("UPDATE staff SET profile_picture = ? WHERE id = ?", saved_name, session["user_id"])
            
            # Handle username change
            if new_username and new_username != session["username"]:
                existing = db.execute("SELECT id FROM staff WHERE username = ? AND id != ?", new_username, session["user_id"])
                if existing:
                    flash("Username already taken.", "danger")
                else:
                    db.execute("UPDATE staff SET username = ? WHERE id = ?", new_username, session["user_id"])
                    session["username"] = new_username
            
            flash("Profile updated successfully.", "success")
            return redirect("/account")

        elif action == "change_password":
            old_password = request.form.get("old_password")
            new_password = request.form.get("new_password")
            confirmation = request.form.get("confirmation")

            if not old_password or not new_password or not confirmation:
                flash("Error: All fields are required.", "danger")
                return redirect("/account")

            if new_password != confirmation:
                flash("Error: New passwords do not match.", "danger")
                return redirect("/account")

            user = db.execute("SELECT hash FROM staff WHERE id = ?", session["user_id"])
            if not check_password_hash(user[0]["hash"], old_password):
                flash("Error: Incorrect current password.", "danger")
                return redirect("/account")

            new_hash = generate_password_hash(new_password)
            db.execute("UPDATE staff SET hash = ? WHERE id = ?", new_hash, session["user_id"])
            
            log_action("Changed their account password")
            flash("Success! Your password has been securely updated.", "success")
            return redirect("/")

    else:
        # Load user info
        user_info = db.execute("SELECT * FROM staff WHERE id = ?", session["user_id"])[0]
        return render_template("auth/account.html", user_info=user_info)
    



@app.route("/manage_staff", methods=["GET", "POST"])
@login_required
@admin_required
def manage_staff():
    """Enterprise dashboard to add, edit, reset, and delete staff accounts."""
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add":
            username = request.form.get("username")
            password = request.form.get("password")
            role = request.form.get("role")
            program_id = request.form.get("program_id")
            
            if not username or not password or not role or not program_id:
                flash("Error: All fields are required to create an account.", "danger")
                return redirect("/manage_staff")
                
            hash_pass = generate_password_hash(password)
            try:
                db.execute("INSERT INTO staff (username, hash, role, program_id) VALUES (?, ?, ?, ?)", 
                           username, hash_pass, role, program_id)
                log_action(f"Registered new staff member: {username} ({role})")
                flash(f"Account created successfully for {username}!", "success")
            except ValueError:
                flash("Error: Username already exists.", "danger")
                
        elif action == "edit":
            staff_id = request.form.get("staff_id")
            new_role = request.form.get("role")
            new_pid = request.form.get("program_id")
            
            if int(staff_id) == session["user_id"] and new_role != "Admin":
                flash("Security Warning: You cannot remove your own Admin privileges.", "warning")
            else:
                db.execute("UPDATE staff SET role = ?, program_id = ? WHERE id = ?", new_role, new_pid, staff_id)
                log_action(f"Updated permissions for Staff ID {staff_id} to {new_role}/Program {new_pid}")
                flash("Staff permissions updated successfully.", "success")
                
        elif action == "reset_password":
            staff_id = request.form.get("staff_id")
            new_hash = generate_password_hash("123456")
            db.execute("UPDATE staff SET hash = ? WHERE id = ?", new_hash, staff_id)
            
            staff_name = db.execute("SELECT username FROM staff WHERE id = ?", staff_id)[0]['username']
            log_action(f"Forced password reset for {staff_name}")
            flash(f"Password for {staff_name} has been reset to '123456'.", "info")

        # ✅ NEW: DELETE / REJECT LOGIC
        elif action == "delete":
            staff_id = request.form.get("staff_id")
            if int(staff_id) == session["user_id"]:
                flash("Security Warning: You cannot delete your own account.", "danger")
            else:
                staff_info = db.execute("SELECT username, role FROM staff WHERE id = ?", staff_id)[0]
                db.execute("DELETE FROM staff WHERE id = ?", staff_id)
                if staff_info['role'] == 'Pending':
                    log_action(f"Rejected and deleted access request for {staff_info['username']}")
                    flash(f"Access request for {staff_info['username']} was rejected.", "success")
                else:
                    log_action(f"Deleted staff account: {staff_info['username']}")
                    flash(f"Staff account for {staff_info['username']} was permanently deleted.", "success")

        return redirect("/manage_staff")
    else:
        # ✅ UPDATED: Now queries for profile_picture
        staff_members = db.execute("""
            SELECT s.id, s.username, s.role, s.program_id, s.profile_picture, p.name as program_name 
            FROM staff s 
            LEFT JOIN programs p ON s.program_id = p.id 
            ORDER BY s.role ASC, s.username ASC
        """)
        programs = db.execute("SELECT * FROM programs ORDER BY id ASC")
        return render_template("admin/manage_staff.html", staff_members=staff_members, programs=programs)


@app.route("/logout")
def logout():
    """Log user out"""
    log_action("Logged out of the system")
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect("/login")


@app.route("/view_as/<role>")
@login_required
@real_admin_required
def view_as(role):
    """Allows an Admin to masquerade as another role to test UI/Permissions."""
    # 1. Save their real admin status if not already saved
    if "real_role" not in session:
        session["real_role"] = session["role"]
        # Save original permissions just in case
        for key in list(session.keys()):
            if key.startswith("can_"):
                session[f"real_{key}"] = session[key]

    # 2. Fetch the permissions for the target role
    perms = db.execute("SELECT * FROM role_permissions WHERE role = ?", role)
    if not perms:
        flash("Role not found.", "danger")
        return redirect(request.referrer or "/")
        
    p = perms[0]
    
    # 3. Apply the fake role and permissions to the active session
    session["role"] = role
    session["can_create_profiles"] = bool(p.get("can_create_profiles", p.get("can_edit_profiles", 0)))
    session["can_update_profiles"] = bool(p.get("can_update_profiles", p.get("can_edit_profiles", 0)))
    session["can_create_academics"] = bool(p.get("can_create_academics", p.get("can_manage_academics", 0)))
    session["can_update_academics"] = bool(p.get("can_update_academics", p.get("can_manage_academics", 0)))
    session["can_delete_academics"] = bool(p.get("can_delete_academics", 0))
    session["can_create_followups"] = bool(p.get("can_create_followups", p.get("can_manage_followups", 0)))
    session["can_update_followups"] = bool(p.get("can_update_followups", p.get("can_manage_followups", 0)))
    session["can_create_files"] = bool(p.get("can_create_files", p.get("can_upload_files", 0)))
    session["can_delete_files"] = bool(p.get("can_delete_files", 0))
    session["can_create_expenses"] = bool(p.get("can_create_expenses", 0))
    session["can_export_data"] = bool(p.get("can_export_data", 0))

    # Map fallbacks for legacy templates
    session["can_edit_profiles"] = session["can_update_profiles"]
    session["can_manage_academics"] = session["can_update_academics"]
    session["can_manage_followups"] = session["can_update_followups"]
    session["can_upload_files"] = session["can_create_files"]

    log_action(f"Started VIEW AS mode: {role}")
    flash(f"You are now viewing the system as a {role}.", "warning")
    return redirect("/")


@app.route("/view_as_revert")
@login_required
@real_admin_required
def view_as_revert():
    """Restores the Admin to their true powers."""
    if "real_role" in session:
        session["role"] = session.pop("real_role")
        
        # Restore all original permissions
        keys_to_restore = [k for k in session.keys() if k.startswith("real_can_")]
        for key in keys_to_restore:
            orig_key = key.replace("real_", "", 1)
            session[orig_key] = session.pop(key)
            
        log_action("Ended VIEW AS mode.")
        flash("Welcome back! Your Admin privileges have been restored.", "success")
        
    return redirect(request.referrer or "/")

@app.route("/set_language/<lang>")
@login_required
def set_language(lang):
    """Phase 6: Toggles the active session language between English and Khmer"""
    if lang in ['en', 'kh']:
        session['lang'] = lang
        
    return redirect(request.referrer or "/")

# ==============================================================================
# NEIGHBORHOOD: DASHBOARD, ROUTING & HUB
# ==============================================================================

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


@app.route("/")
@login_required
def index():
    """Smart Homepage that changes based on the user's active program view"""
    program_id = session.get("program_id", 1) 
    
    if program_id == 0:
        staff_members = db.execute("SELECT * FROM staff ORDER BY role ASC, username ASC")
        # Restored the correct subfolder path: "directory/hr_roster.html"
        return render_template("directory/hr_roster.html", staff_members=staff_members, title="Global HR Directory")
        
    elif program_id > 0:
        staff = db.execute("SELECT username FROM staff WHERE id = ?", session["user_id"])
        username = staff[0]["username"] if staff else "Staff"

        # Fetch all active students for search and demographic calculations
        all_active_students = db.execute("SELECT * FROM students WHERE status = 'Active' AND program_id = ? ORDER BY first_name", program_id)
        
        # --- DYNAMIC ALERTS ENGINE ---
        alerts = []
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        next_week_str = (today + timedelta(days=7)).strftime('%Y-%m-%d')

        # 1. Calendar Alerts (Holidays & High Priority Tasks)
        upcoming_events = db.execute("""
            SELECT title, due_date, status 
            FROM tasks 
            WHERE due_date BETWEEN ? AND ? 
            AND (status = 'Holiday' OR (priority = 'High' AND is_team_task = 1))
            AND program_id = ?
            ORDER BY due_date ASC
        """, today_str, next_week_str, program_id)

        for event in upcoming_events:
            is_holiday = event['status'] == 'Holiday'
            alerts.append({
                "title": f"Upcoming: {event['title']}",
                "message": f"Scheduled for {event['due_date'].split('T')[0]}. Check calendar for details.",
                "icon": "bi-sun-fill" if is_holiday else "bi-calendar-event-fill",
                "color": "warning" if is_holiday else "danger",
                "category": "SYSTEM ALERT",
                "link": "/calendar"
            })

        # 2. Academic Deadlines (Last 7 days of the month)
        last_day = calendar.monthrange(today.year, today.month)[1]
        if today.day >= (last_day - 7):
            alerts.append({
                "title": "Monthly Reports Due Soon",
                "message": f"Academic grades and comments for {today.strftime('%B')} are due.",
                "icon": "bi-journal-check",
                "color": "success",
                "category": "ACADEMICS",
                "link": "/roster"
            })

        # 3. Child Protection & Risk Alerts (Recent High Risk)
        thirty_days_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        critical_risks = db.execute("""
            SELECT f.id, f.student_id, f.risk_level, f.child_protection_concerns, s.first_name, s.last_name 
            FROM followups f
            JOIN students s ON f.student_id = s.id
            WHERE f.followup_date >= ?
            AND (f.risk_level >= 4 OR (f.child_protection_concerns IS NOT NULL AND f.child_protection_concerns != ''))
            AND s.program_id = ?
            ORDER BY f.followup_date DESC LIMIT 3
        """, thirty_days_ago, program_id)

        for risk in critical_risks:
            alerts.append({
                "title": f"Protection Alert: {risk['first_name']} {risk['last_name']}",
                "message": "Critical risk or child protection concern logged recently.",
                "icon": "bi-shield-exclamation-fill",
                "color": "danger",
                "category": "SOCIAL WORK",
                "link": f"/student/{risk['student_id']}/timeline"
            })
            
        # 4. Pending Staff Approvals (If Admin)
        if session.get("role") == "Admin":
            pending_staff = db.execute("SELECT COUNT(*) as count FROM staff WHERE role = 'Pending'")
            if pending_staff and pending_staff[0]['count'] > 0:
                count = pending_staff[0]['count']
                alerts.append({
                    "title": "Action Required: Pending Staff",
                    "message": f"{count} staff member(s) waiting for access approval.",
                    "icon": "bi-person-fill-exclamation",
                    "color": "warning text-darken",
                    "category": "ADMIN TASKS",
                    "link": "/manage_staff"
                })

        # Restored the correct subfolder path: "dashboard/index.html"
        return render_template("dashboard/index.html", 
                               username=username, 
                               students=all_active_students,
                               alerts=alerts)



@app.route("/dashboard")
@login_required
def dashboard():
    """Smart Dashboard Router based on Active Program Context"""
    program_id = session.get("program_id", 1) 
    
    # HAT 1: GOVT AFFAIRS & CENTRAL ADMIN
    if program_id == 0:
        today_date = datetime.now().strftime('%Y-%m-%d')
        return render_template("dashboard/dashboard_global.html", date_now=today_date)
        
    # HAT 2: PROGRAM MANAGEMENT
    elif program_id > 0:
        try:
            months = int(request.args.get('timeframe', 1))
        except ValueError:
            months = 1

        active_kids = db.execute("SELECT gender, COUNT(*) as count FROM students WHERE status = 'Active' AND program_id = ? GROUP BY gender", program_id)
        total_active = sum(row['count'] for row in active_kids)
        boys = next((row['count'] for row in active_kids if row['gender'] == 'Male'), 0)
        girls = next((row['count'] for row in active_kids if row['gender'] == 'Female'), 0)

        uni_kids = db.execute("SELECT COUNT(*) as count FROM students WHERE status = 'Active' AND program_id = ? AND grade_level LIKE '%University%'", program_id)[0]['count']
        vocal_kids = db.execute("SELECT COUNT(*) as count FROM students WHERE status = 'Active' AND program_id = ? AND grade_level LIKE '%Vocational%'", program_id)[0]['count']

        lunch_kids_count = db.execute("SELECT COUNT(*) as count FROM students WHERE status = 'Active' AND program_id = ? AND meal_plan = 'Daily Hot Lunch'", program_id)[0]['count']
        estimated_workdays = months * 22
        max_possible_meals = lunch_kids_count * estimated_workdays

        missed_meals = db.execute("""
            SELECT COUNT(*) as total FROM student_services ss
            JOIN students s ON ss.student_id = s.id
            WHERE ss.service_type = 'Missed Hot Lunch'
            AND ss.service_date >= date('now', ?) AND s.program_id = ?
        """, f'-{months} month', program_id)[0]['total'] or 0

        holidays_logged = db.execute("""
            SELECT COUNT(*) as total FROM student_services ss
            JOIN students s ON ss.student_id = s.id
            WHERE ss.service_type = 'Holiday - No Meals'
            AND ss.service_date >= date('now', ?) AND s.program_id = ?
        """, f'-{months} month', program_id)[0]['total'] or 0
        
        holiday_missed_meals = holidays_logged * lunch_kids_count
        meals = max(0, max_possible_meals - missed_meals - holiday_missed_meals)

        parent_meetings = db.execute("""
            SELECT COUNT(*) as total FROM activities
            WHERE activity_type = 'Parent Meeting' AND activity_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        housing_supports = db.execute("""
            SELECT SUM(attendance_count) as total FROM activities
            WHERE activity_type = 'Housing Support' AND activity_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        other_activities = db.execute("""
            SELECT COUNT(*) as total FROM activities
            WHERE activity_type NOT IN ('Hot Meal', 'Parent Meeting', 'Housing Support')
            AND activity_date >= date('now', ?)
        """, f'-{months} month')[0]['total'] or 0

        top_performers = db.execute("""
            SELECT COUNT(*) as count FROM monthly_reports r
            JOIN students s ON r.student_id = s.id
            WHERE CAST(r.class_rank AS INTEGER) <= 10 AND CAST(r.class_rank AS INTEGER) > 0 AND s.program_id = ?
        """, program_id)[0]['count']
        graduates = db.execute("SELECT COUNT(*) as count FROM students WHERE status = 'Graduated' AND program_id = ?", program_id)[0]['count']

        academic_alerts = db.execute("""
            SELECT s.first_name, s.last_name, s.id, r.overall_average, r.academic_year, r.month
            FROM students s JOIN monthly_reports r ON s.id = r.student_id
            WHERE r.overall_average < 50 AND r.overall_average IS NOT NULL
            AND s.status = 'Active' AND s.program_id = ?
            ORDER BY r.academic_year DESC, r.id DESC LIMIT 5
        """, program_id)

        protection_alerts = db.execute("""
            SELECT s.first_name, s.last_name, s.id, f.id as followup_id, f.child_protection_concerns
            FROM students s JOIN followups f ON s.id = f.student_id
            WHERE f.child_protection_concerns NOT IN ('No', 'None', 'N/A', '')
            AND f.child_protection_concerns IS NOT NULL
            AND (f.alert_status IS NULL OR f.alert_status = 'Active')
            AND s.status = 'Active' AND s.program_id = ?
            ORDER BY f.followup_date DESC LIMIT 5
        """, program_id)

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
            WHERE s.status = 'Active' AND s.program_id = ?
            GROUP BY s.id
            HAVING sent IS NULL OR sent != 'Yes'
            ORDER BY s.first_name ASC
        """, current_quarter, current_year, program_id)

        missing_letters = []
        for student in missing_letters_raw:
            if student['scanned'] == 'Yes':
                student['status_badge'], student['status_color'] = "Ready to Send", "primary"
            elif student['translated'] == 'Yes':
                student['status_badge'], student['status_color'] = "Waiting to Scan", "info"
            elif student['given'] == 'Yes':
                student['status_badge'], student['status_color'] = "Needs Translation", "warning"
            else:
                student['status_badge'], student['status_color'] = "Not Started", "danger"
            missing_letters.append(student)

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

        return render_template("dashboard/executive_dashboard.html",
                               total_active=total_active, boys=boys, girls=girls,
                               uni_kids=uni_kids, vocal_kids=vocal_kids,
                               meals=meals, meetings=parent_meetings,
                               housing_supports=housing_supports, other_activities=other_activities,
                               top_performers=top_performers, graduates=graduates,
                               academic_alerts=academic_alerts, protection_alerts=protection_alerts,
                               missing_letters=missing_letters, current_quarter=current_quarter, current_year=current_year,
                               timeframe=months, date_now=date_now, recent_activity=recent_activity)


# ==============================================================================
# NEIGHBORHOOD: STUDENT ROSTERS & PROFILES
# ==============================================================================

@app.route("/roster")
@login_required
def roster():
    """Show the full active roster"""
    pid = session.get("program_id", 0)
    students = db.execute("SELECT * FROM students WHERE status != 'Dropped Out' AND status != 'Graduated' AND (program_id = ? OR ? = 0) ORDER BY first_name", pid, pid)
    return render_template("directory/roster.html", students=students, title="Active Roster")

@app.route("/archive")
@login_required
def archive():
    """Show dropped out / graduated students"""
    pid = session.get("program_id", 0)
    students = db.execute("SELECT * FROM students WHERE (status = 'Dropped Out' OR status = 'Graduated') AND (program_id = ? OR ? = 0) ORDER BY first_name", pid, pid)
    return render_template("directory/roster.html", students=students, title="Archived Students")

@app.route("/guide")
@login_required
def guide():
    """Show the Beta Testing Instructions"""
    return render_template("dashboard/guide.html")

@app.route("/add_student", methods=["GET", "POST"])
@login_required
@permission_required("can_create_profiles")
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
        previous_school = request.form.get("previous_school")
        current_school = request.form.get("current_school")
        grade = request.form.get("grade_level")
        meal_plan = request.form.get("meal_plan")
        comment = request.form.get("comment")
        household_id = request.form.get("household_id")
        
        caregiver_relationship = request.form.get("caregiver_relationship")
        mother_name = request.form.get("mother_name")
        father_name = request.form.get("father_name")

        if not ngo_id or not first_name or not last_name:
            return render_template("_layouts/apology.html", message="NGO ID, First Name, and Last Name are required.")

        if not household_id:
            if guardian_name:
                # Auto-create the household to prevent orphaned students!
                db.execute("""
                    INSERT INTO households (guardian_name, phone_number, slum_area)
                    VALUES (?, ?, ?)
                """, guardian_name, phone, slum)
                # Grab the newly created ID
                household_id = db.execute("SELECT id FROM households ORDER BY id DESC LIMIT 1")[0]['id']
            else:
                household_id = None 

        pid = session.get("program_id", 1)
        if pid == 0: pid = 1

        try:
            db.execute("""
                INSERT INTO students
                (ngo_id, status, first_name, last_name, khmer_name, gender, dob, joined_date, guardian_name, phone_number, slum_area, previous_school, current_school, grade_level, meal_plan, comment, household_id, caregiver_relationship, mother_name, father_name, program_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, ngo_id, status, first_name, last_name, khmer_name, gender, dob, joined_date, guardian_name, phone, slum, previous_school, current_school, grade, meal_plan, comment, household_id, caregiver_relationship, mother_name, father_name, pid)
            
            student_id = db.execute("SELECT id FROM students WHERE ngo_id = ?", ngo_id)[0]['id']
            
            file = request.files.get('profile_picture')
            if file and file.filename != '':
                filename, _ = handle_file_upload(file, student_id, "profile", app.config['PROFILE_UPLOAD_FOLDER'])
                if filename:
                    db.execute("UPDATE students SET profile_picture = ? WHERE id = ?", filename, student_id)
            
            log_action(f"Added new student profile: {first_name} {last_name}")
            flash(f"{first_name} added successfully!", "success")
            return redirect("/")

        except ValueError:
            return render_template("_layouts/apology.html", message="A student with that NGO ID already exists.")

    else:
        today_date = datetime.now().strftime('%Y-%m-%d')
        households = db.execute("""
            SELECT h.id, h.guardian_name, h.phone_number, h.slum_area
            FROM households h
            ORDER BY h.guardian_name ASC
        """)
        return render_template("student/add_student.html", today_date=today_date, households=households)

@app.route("/edit_student/<int:id>", methods=["GET", "POST"])
@login_required
@permission_required("can_update_profiles")
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
        previous_school = request.form.get("previous_school")
        current_school = request.form.get("current_school")
        grade = request.form.get("grade_level")
        meal_plan = request.form.get("meal_plan")
        comment = request.form.get("comment")
        household_id = request.form.get("household_id")
        
        caregiver_relationship = request.form.get("caregiver_relationship")
        mother_name = request.form.get("mother_name")
        father_name = request.form.get("father_name")

        if not household_id:
            household_id = None 

        if not ngo_id or not first_name or not last_name:
            return render_template("_layouts/apology.html", message="NGO ID, First Name, and Last Name are required.")

        try:
            db.execute("""
                UPDATE students 
                SET ngo_id = ?, first_name = ?, last_name = ?, khmer_name = ?, gender = ?, 
                    dob = ?, joined_date = ?, guardian_name = ?, phone_number = ?, 
                    slum_area = ?, previous_school = ?, current_school = ?, grade_level = ?, meal_plan = ?, 
                    comment = ?, status = ?, household_id = ?, caregiver_relationship = ?, 
                    mother_name = ?, father_name = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, ngo_id, first_name, last_name, khmer_name, gender, dob, joined_date, 
                 guardian_name, phone, slum, previous_school, current_school, grade, meal_plan, comment, status, 
                 household_id, caregiver_relationship, mother_name, father_name, id)
            
            log_action(f"Edited student profile: {first_name} {last_name}")
            flash("Student updated successfully!", "success")
            return redirect(f"/student/{id}")

        except ValueError:
            return render_template("_layouts/apology.html", message="Update failed. NGO ID might conflict with another student.")

    else:
        student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
        if len(student_data) != 1:
            return render_template("_layouts/apology.html", message="Student not found")

        student = student_data[0]
        households = db.execute("""
            SELECT h.id, h.guardian_name, h.slum_area, h.phone_number, GROUP_CONCAT(s.first_name, ', ') as kids
            FROM households h
            LEFT JOIN students s ON h.id = s.household_id
            GROUP BY h.id
            ORDER BY h.guardian_name ASC
        """)
        
        return render_template("student/edit_student.html", student=student, households=households)

@app.route("/update_avatar/<int:id>", methods=["POST"])
@login_required
@permission_required("can_update_profiles")
def update_avatar(id):
    file = request.files.get('profile_picture')
    if file and file.filename != '':
        filename, _ = handle_file_upload(file, id, "profile", app.config['PROFILE_UPLOAD_FOLDER'])
        if filename:
            db.execute("UPDATE students SET profile_picture = ? WHERE id = ?", filename, id)
            log_action(f"Updated profile picture for Student ID: {id}")
            flash("Photo updated!", "success")
    return redirect(f"/student/{id}")


# ==============================================================================
# NEIGHBORHOOD: HOUSEHOLDS
# ==============================================================================

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
            income = request.form.get("household_income")
            headcount = request.form.get("total_headcount")
            adults = request.form.get("adults_in_home")
            living = request.form.get("living_conditions")
            notes = request.form.get("notes")
            
            if not guardian:
                flash("Guardian Name is required.", "danger")
            else:
                db.execute("""
                    INSERT INTO households (
                        guardian_name, phone_number, slum_area, household_income, 
                        total_headcount, adults_in_home, living_conditions, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, guardian, phone, slum, income, headcount, adults, living, notes)
                log_action(f"Created new household: {guardian}")
                flash(f"Family file for {guardian} created successfully!", "success")
        
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
        return render_template("household/manage_households.html", households=households)

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
            income = request.form.get("household_income")
            headcount = request.form.get("total_headcount")
            ledger = request.form.get("adults_in_home")
            living = request.form.get("living_conditions")
            notes = request.form.get("notes")
            
            db.execute("""
                UPDATE households 
                SET guardian_name = ?, phone_number = ?, slum_area = ?, household_income = ?, 
                    total_headcount = ?, adults_in_home = ?, living_conditions = ?, notes = ? 
                WHERE id = ?
            """, guardian, phone, slum, income, headcount, ledger, living, notes, id)
            
            log_action(f"Updated Household ID {id} profile")
            flash("Family details updated successfully.", "success")

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
            return render_template("_layouts/apology.html", message="Household not found")
            
        kids = db.execute("SELECT * FROM students WHERE household_id = ? ORDER BY dob ASC", id)
        return render_template("household/household_profile.html", household=household[0], kids=kids)


# ==============================================================================
# NEIGHBORHOOD: STUDENT PROFILE (The Hub)
# ==============================================================================

@app.route("/student/<int:id>")
@login_required
def student_profile(id):
    """Lightweight Hub for a student's profile."""
    student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
    if not student_data:
        return render_template("_layouts/apology.html", message="Student not found")
    student = student_data[0]

    household = None
    siblings = []
    if student.get("household_id"):
        hh = db.execute("SELECT * FROM households WHERE id = ?", student["household_id"])
        if hh:
            household = hh[0]
            
        siblings = db.execute("""
            SELECT id, first_name, last_name, profile_picture, status, grade_level, caregiver_relationship 
            FROM students 
            WHERE household_id = ? AND id != ?
            ORDER BY dob ASC
        """, student["household_id"], id)

    # Snapshot queries - Lightning fast limit 1
    reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? ORDER BY academic_year DESC, id DESC LIMIT 1", id)
    followups = db.execute("SELECT * FROM followups WHERE student_id = ? ORDER BY followup_date DESC, id DESC LIMIT 1", id)

    return render_template("student/student_profile.html", 
                           student=student, 
                           household=household,
                           siblings=siblings,
                           reports=reports, 
                           followups=followups)

# --- 🚀 NEW NATIVE SUB-PAGES FOR THE STUDENT HUB ---

@app.route("/student/<int:id>/academics")
@login_required
def student_academics(id):
    """Deep Dive: Academic History & Trajectory"""
    student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
    if not student_data:
        return render_template("_layouts/apology.html", message="Student not found")
    student = student_data[0]

    academic_years_raw = db.execute("SELECT DISTINCT academic_year FROM monthly_reports WHERE student_id = ? ORDER BY academic_year DESC", id)
    unique_years = [row['academic_year'] for row in academic_years_raw if row['academic_year']]

    timeframe = request.args.get("timeframe")

    if timeframe and timeframe.isdigit():
        reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? ORDER BY academic_year DESC, id DESC LIMIT ?", id, int(timeframe))
    elif timeframe and "-" in timeframe:
        reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? AND academic_year = ? ORDER BY id DESC", id, timeframe)
    else:
        reports = db.execute("SELECT * FROM monthly_reports WHERE student_id = ? ORDER BY academic_year DESC, id DESC", id)

    for report in reports:
        subjects = db.execute("""
            SELECT COALESCE(s.name, g.custom_subject_name) as subject_name, 
                   g.score, 
                   g.max_score,
                   COALESCE(s.category, 'Custom') as category
            FROM grades g
            LEFT JOIN subjects s ON g.subject_id = s.id
            WHERE g.report_id = ?
            ORDER BY s.sort_order ASC, subject_name ASC
        """, report["id"])
        
        for sub in subjects:
            letter, box, text, badge = get_subject_grade_data(sub['score'], sub['max_score'])
            sub['grade_letter'] = letter
            sub['box_class'] = box
            sub['text_class'] = text
            sub['badge_class'] = badge

        report["subjects"] = subjects

    return render_template("student/student_academics.html", student=student, reports=reports, unique_years=unique_years, timeframe=timeframe)

@app.route("/student/<int:id>/timeline")
@login_required
def student_timeline(id):
    """Deep Dive: Social Work & Notes Timeline"""
    student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
    if not student_data:
        return render_template("_layouts/apology.html", message="Student not found")
    student = student_data[0]
    
    followups = db.execute("SELECT * FROM followups WHERE student_id = ? ORDER BY followup_date DESC, id DESC", id)
    return render_template("student/student_timeline.html", student=student, followups=followups)

@app.route("/student/<int:id>/files")
@login_required
def student_files(id):
    """Deep Dive: Digital Documents"""
    student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
    if not student_data:
        return render_template("_layouts/apology.html", message="Student not found")
    student = student_data[0]
    
    try:
        docs = db.execute("SELECT * FROM documents WHERE student_id = ? ORDER BY upload_date DESC", id)
    except Exception:
        docs = []
    return render_template("student/student_files.html", student=student, docs=docs)

@app.route("/student/<int:id>/finance")
@login_required
def student_finance(id):
    """Deep Dive: Financial Ledger"""
    student_data = db.execute("SELECT * FROM students WHERE id = ?", id)
    if not student_data:
        return render_template("_layouts/apology.html", message="Student not found")
    student = student_data[0]
    
    try:
        expenses = db.execute("SELECT * FROM student_expenses WHERE student_id = ? ORDER BY expense_date DESC", id)
        total_spent_raw = sum(exp['amount'] for exp in expenses) if expenses else 0.00
    except Exception:
        expenses = []
        total_spent_raw = 0.00
        
    total_spent = f"{total_spent_raw:,.2f}"
    return render_template("student/student_finance.html", student=student, expenses=expenses, total_spent=total_spent)


# ==============================================================================
# NEIGHBORHOOD: ACADEMICS (MASTER GRADEBOOK, ADD/EDIT REPORTS)
# ==============================================================================

@app.route("/academics")
@login_required
def academics():
    """Master Gradebook - Shows all students and all grades dynamically"""
    pid = session.get("program_id", 0)
    academic_records_raw = db.execute("""
        SELECT r.*, s.first_name, s.last_name, s.ngo_id, s.khmer_name, s.gender, s.current_school, s.grade_level as student_grade
        FROM monthly_reports r
        JOIN students s ON r.student_id = s.id
        WHERE s.status = 'Active' AND (s.program_id = ? OR ? = 0)
        ORDER BY r.academic_year DESC, r.id DESC
    """, pid, pid)

    raw_grades = db.execute("""
        SELECT g.*, COALESCE(subj.name, g.custom_subject_name) as subject_name,
               COALESCE(subj.category, 'Custom') as category
        FROM grades g
        LEFT JOIN subjects subj ON g.subject_id = subj.id
    """)

    grades_by_report = {}
    for g in raw_grades:
        letter, box, text, badge = get_subject_grade_data(g['score'], g['max_score'])
        g['grade_letter'] = letter
        g['box_class'] = box
        g['text_class'] = text
        g['badge_class'] = badge

        rep_id = g['report_id']
        if rep_id not in grades_by_report:
            grades_by_report[rep_id] = []
        grades_by_report[rep_id].append(g)

    for record in academic_records_raw:
        record['subjects'] = grades_by_report.get(record['id'], [])
        if not record['grade_level']:
            record['grade_level'] = record['student_grade']

    active_students = db.execute("SELECT id, first_name, last_name, ngo_id FROM students WHERE status = 'Active' AND (program_id = ? OR ? = 0) ORDER BY first_name", pid, pid)

    return render_template("academics/academics.html", academic_records=academic_records_raw, active_students=active_students)

@app.route("/add_report/<int:student_id>", methods=["GET", "POST"])
@login_required
@permission_required("can_create_academics")
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
            return render_template("_layouts/apology.html", message="Report Month and Academic Year are required. Please use your browser's BACK arrow to return to the form without losing your typed grades.")

        existing_report = db.execute("""
            SELECT id FROM monthly_reports
            WHERE student_id = ? AND month = ? AND academic_year = ? AND IFNULL(semester, '') = IFNULL(?, '')
        """, student_id, month, academic_year, semester)

        if existing_report:
            return render_template("_layouts/apology.html", message=f"A {semester if semester else 'Regular'} report for {month} {academic_year} already exists! Please use your browser's BACK arrow to return to the form.")

        file = request.files.get('scanned_document')
        scanned_filename, _ = handle_file_upload(file, student_id, "report", app.config['UPLOAD_FOLDER'])

        report_id = db.execute("""
            INSERT INTO monthly_reports (student_id, month, academic_year, semester, class_rank, teacher_comment, attendance_days, scanned_document, grade_level, school_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, student_id, month, academic_year, semester, class_rank, teacher_comment, attendance_days, scanned_filename, grade_level, school_name)

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

        calculated_avg, calculated_grade = calculate_gpa(calculated_total, calculated_max, has_numeric, missing_max)

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
    return render_template("academics/add_report.html", student=student, subjects=subjects)

@app.route("/edit_report/<int:report_id>", methods=["GET", "POST"])
@login_required
@permission_required("can_update_academics")
def edit_report(report_id):
    report_data = db.execute("SELECT * FROM monthly_reports WHERE id = ?", report_id)
    if len(report_data) != 1:
        return render_template("_layouts/apology.html", message="Report not found")
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
            return render_template("_layouts/apology.html", message="Month and Academic Year are required. Please use your browser's BACK arrow to return without losing data.")

        existing_report = db.execute("""
            SELECT id FROM monthly_reports
            WHERE student_id = ? AND month = ? AND academic_year = ? AND IFNULL(semester, '') = IFNULL(?, '') AND id != ?
        """, student_id, month, academic_year, semester, report_id)

        if existing_report:
            return render_template("_layouts/apology.html", message="Another report for this term already exists. Please use your browser's BACK arrow to return.")

        file = request.files.get('scanned_document')
        if file and file.filename != '':
            scanned_filename, _ = handle_file_upload(file, student_id, "report", app.config['UPLOAD_FOLDER'])
            if scanned_filename:
                db.execute("UPDATE monthly_reports SET scanned_document = ? WHERE id = ?", scanned_filename, report_id)

        db.execute("""
            UPDATE monthly_reports
            SET month = ?, academic_year = ?, semester = ?, attendance_days = ?, teacher_comment = ?, class_rank = ?, grade_level = ?, school_name = ?
            WHERE id = ?
        """, month, academic_year, semester, attendance_days, teacher_comment, class_rank, grade_level, school_name, report_id)

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

        calculated_avg, calculated_grade = calculate_gpa(calculated_total, calculated_max, has_numeric, missing_max)

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

    return render_template("academics/edit_report.html", student=student, report=report, subjects=subjects, existing_grades=existing_grades)

@app.route("/delete_report/<int:report_id>", methods=["POST"])
@login_required
@permission_required("can_delete_academics")
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
# NEIGHBORHOOD: SOCIAL WORK & FOLLOW-UPS
# ==============================================================================

@app.route("/add_followup/<int:student_id>", methods=["GET", "POST"])
@login_required
@permission_required("can_create_followups")
def add_followup(student_id):
    if request.method == "POST":
        followup_date = request.form.get("followup_date")
        location = request.form.get("location")
        completed_by = request.form.get("completed_by")

        if not followup_date or not completed_by:
            return render_template("_layouts/apology.html", message="Date and Completed By are required. Please use your browser's BACK arrow to return without losing data.")

        risk_factors_list = request.form.getlist("risk_factors")
        risk_factors = ", ".join(risk_factors_list) if risk_factors_list else "None"

        db.execute("""
            INSERT INTO followups (
                student_id, followup_date, location, completed_by,
                physical_health, physical_health_detail, social_interaction, social_interaction_detail,
                home_life, home_life_detail, evidence_drugs_violence,
                learning_difficulties, behavior_in_class,
                peer_issues, teacher_involvement,
                transportation, tutoring_participation,
                risk_factors, risk_details, child_protection_concerns, trafficking_risk, general_notes,
                letter_quarter, letter_year, letter_given, letter_translated, letter_scanned, letter_sent, letter_notes,
                parent_working_notes, support_level, church_attendance, child_jobs, risk_level, student_story, staff_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, student_id, followup_date, location, completed_by,
             request.form.get("physical_health"), request.form.get("physical_health_detail"),
             request.form.get("social_interaction"), request.form.get("social_interaction_detail"),
             request.form.get("home_life"), request.form.get("home_life_detail"), request.form.get("evidence_drugs_violence"),
             request.form.get("learning_difficulties"), request.form.get("behavior_in_class"),
             request.form.get("peer_issues"), request.form.get("teacher_involvement"),
             request.form.get("transportation"), request.form.get("tutoring_participation"),
             risk_factors, request.form.get("risk_details"), request.form.get("child_protection_concerns"), request.form.get("trafficking_risk"), request.form.get("general_notes"),
             request.form.get("letter_quarter"), request.form.get("letter_year"), request.form.get("letter_given"), request.form.get("letter_translated"), request.form.get("letter_scanned"), request.form.get("letter_sent"), request.form.get("letter_notes"),
             request.form.get("parent_working_notes"), request.form.get("support_level"), request.form.get("church_attendance"), request.form.get("child_jobs"), request.form.get("risk_level"), request.form.get("student_story"), request.form.get("staff_notes")
        )

        log_action(f"Added Social Work Follow-Up for Student ID: {student_id}")
        flash("Follow-up successfully recorded!", "success")
        return redirect(f"/student/{student_id}/timeline")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    current_year = datetime.now().year
    today_date = datetime.now().strftime('%Y-%m-%d')
    staff_query = db.execute("SELECT username FROM staff WHERE id = ?", session["user_id"])
    current_user = staff_query[0]["username"] if staff_query else ""

    return render_template("social_work/add_followup.html", student=student, current_year=current_year, today_date=today_date, current_user=current_user)

@app.route("/edit_followup/<int:followup_id>", methods=["GET", "POST"])
@login_required
@permission_required("can_update_followups")
def edit_followup(followup_id):
    followup_data = db.execute("SELECT * FROM followups WHERE id = ?", followup_id)
    if len(followup_data) != 1:
        return render_template("_layouts/apology.html", message="Follow-up not found")
    followup = followup_data[0]
    student_id = followup["student_id"]

    if request.method == "POST":
        followup_date = request.form.get("followup_date")
        location = request.form.get("location")
        completed_by = request.form.get("completed_by")

        if not followup_date or not completed_by:
            return render_template("_layouts/apology.html", message="Date and Completed By are required. Please use your browser's BACK arrow to return without losing data.")

        risk_factors_list = request.form.getlist("risk_factors")
        risk_factors = ", ".join(risk_factors_list) if risk_factors_list else "None"

        db.execute("""
            UPDATE followups SET
                followup_date = ?, location = ?, completed_by = ?,
                physical_health = ?, physical_health_detail = ?, social_interaction = ?, social_interaction_detail = ?,
                home_life = ?, home_life_detail = ?, evidence_drugs_violence = ?,
                learning_difficulties = ?, behavior_in_class = ?,
                peer_issues = ?, teacher_involvement = ?,
                transportation = ?, tutoring_participation = ?,
                risk_factors = ?, risk_details = ?, child_protection_concerns = ?, trafficking_risk = ?, general_notes = ?,
                letter_quarter = ?, letter_year = ?, letter_given = ?, letter_translated = ?, letter_scanned = ?, letter_sent = ?, letter_notes = ?,
                parent_working_notes = ?, support_level = ?, church_attendance = ?, child_jobs = ?, risk_level = ?, student_story = ?, staff_notes = ?
            WHERE id = ?
        """, followup_date, location, completed_by,
             request.form.get("physical_health"), request.form.get("physical_health_detail"), request.form.get("social_interaction"), request.form.get("social_interaction_detail"),
             request.form.get("home_life"), request.form.get("home_life_detail"), request.form.get("evidence_drugs_violence"),
             request.form.get("learning_difficulties"), request.form.get("behavior_in_class"),
             request.form.get("peer_issues"), request.form.get("teacher_involvement"),
             request.form.get("transportation"), request.form.get("tutoring_participation"),
             risk_factors, request.form.get("risk_details"), request.form.get("child_protection_concerns"), request.form.get("trafficking_risk"), request.form.get("general_notes"),
             request.form.get("letter_quarter"), request.form.get("letter_year"), request.form.get("letter_given"), request.form.get("letter_translated"), request.form.get("letter_scanned"), request.form.get("letter_sent"), request.form.get("letter_notes"),
             request.form.get("parent_working_notes"), request.form.get("support_level"), request.form.get("church_attendance"), request.form.get("child_jobs"), request.form.get("risk_level"), request.form.get("student_story"), request.form.get("staff_notes"),
             followup_id)

        log_action(f"Edited Social Work Follow-Up for Student ID: {student_id}")
        flash("Follow-up successfully updated!", "success")
        return redirect(f"/student/{student_id}/timeline")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    return render_template("social_work/edit_followup.html", student=student, followup=followup)

@app.route("/bulk_followup", methods=["GET", "POST"])
@login_required
@permission_required("can_create_followups")
def bulk_followup():
    """Log a single follow-up note for multiple students at once"""
    if request.method == "POST":
        # 1. Logistics
        followup_date = request.form.get("followup_date")
        completed_by = request.form.get("completed_by")
        location = request.form.get("location")
        
        # 2. Check Toggles
        is_sponsor_update = request.form.get("is_sponsor_update") == "on"
        is_master_update = request.form.get("is_master_update") == "on"

        # 3. Monthly Pulse
        physical_health = request.form.get("physical_health")
        physical_health_detail = request.form.get("physical_health_detail")
        social_interaction = request.form.get("social_interaction")
        social_interaction_detail = request.form.get("social_interaction_detail")
        behavior_in_class = request.form.get("behavior_in_class")
        behavior_in_class_detail = request.form.get("behavior_in_class_detail")
        tutoring_participation = request.form.get("tutoring_participation")
        tutoring_detail = request.form.get("tutoring_detail")
        evidence_drugs_violence = request.form.get("evidence_drugs_violence")
        risk_level = request.form.get("risk_level")

        # 4. Narrative & Action
        general_notes = request.form.get("general_notes")
        child_protection_concerns = request.form.get("child_protection_concerns")
        trafficking_risk = request.form.get("trafficking_risk")
        staff_notes = request.form.get("staff_notes")
        
        # 5. Sponsor Letter fields
        letter_quarter = request.form.get("letter_quarter") if is_sponsor_update else None
        letter_year = request.form.get("letter_year") if is_sponsor_update else None
        letter_given = request.form.get("letter_given") if is_sponsor_update else None
        letter_translated = request.form.get("letter_translated") if is_sponsor_update else None
        letter_scanned = request.form.get("letter_scanned") if is_sponsor_update else None
        letter_sent = request.form.get("letter_sent") if is_sponsor_update else None
        letter_notes = request.form.get("letter_notes") if is_sponsor_update else None

        # 6. Master Data fields
        home_condition = request.form.get("home_condition") if is_master_update else None
        church_attendance = request.form.get("church_attendance") if is_master_update else None
        parent_working_notes = request.form.get("parent_working_notes") if is_master_update else None
        
        risk_factors_list = request.form.getlist("risk_factors") if is_master_update else []
        risk_factors = ", ".join(risk_factors_list) if risk_factors_list else ""

        # 7. Students List
        student_ids = request.form.getlist("student_ids")

        if not followup_date or not completed_by:
            flash("Date and Completed By are required.", "danger")
            return redirect("/roster")

        if not student_ids:
            flash("You must select at least one student from the roster first.", "warning")
            return redirect("/roster")

        alert_status = 'Active' if child_protection_concerns and child_protection_concerns.strip() else None

        for sid in student_ids:
            db.execute("""
                INSERT INTO followups (
                    student_id, followup_date, location, completed_by, general_notes,
                    physical_health, physical_health_detail, social_interaction, social_interaction_detail,
                    behavior_in_class, behavior_in_class_detail, tutoring_participation, tutoring_participation_detail,
                    evidence_drugs_violence, risk_level, child_protection_concerns, trafficking_risk, staff_notes,
                    letter_quarter, letter_year, letter_given, letter_translated, letter_scanned, letter_sent, letter_notes,
                    home_life, church_attendance, parent_working_notes, risk_factors, alert_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, sid, followup_date, location, completed_by, general_notes,
                physical_health, physical_health_detail, social_interaction, social_interaction_detail,
                behavior_in_class, behavior_in_class_detail, tutoring_participation, tutoring_detail,
                evidence_drugs_violence, risk_level, child_protection_concerns, trafficking_risk, staff_notes,
                letter_quarter, letter_year, letter_given, letter_translated, letter_scanned, letter_sent, letter_notes,
                home_condition, church_attendance, parent_working_notes, risk_factors, alert_status)

        log_action(f"Logged Group Follow-Up ({location}) for {len(student_ids)} students")
        flash(f"Successfully logged group follow-up for {len(student_ids)} students!", "success")
        return redirect("/")

    else:
        # === GET REQUEST LOGIC (The Roster Handoff) ===
        student_ids = request.args.getlist("student_ids")
        
        selected_students = []
        if student_ids:
            # Create a string of question marks for the SQL IN clause (?,?,?)
            placeholders = ','.join('?' * len(student_ids))
            query = f"SELECT id, first_name, last_name, ngo_id FROM students WHERE id IN ({placeholders})"
            selected_students = db.execute(query, *student_ids)

        return render_template("social_work/bulk_followup.html", selected_students=selected_students)

@app.route("/resolve_alert/<int:followup_id>", methods=["POST"])
@login_required
@permission_required("can_update_followups")
def resolve_alert(followup_id):
    """Mark a protection alert as resolved"""
    db.execute("UPDATE followups SET alert_status = 'Resolved' WHERE id = ?", followup_id)
    log_action(f"Resolved Risk Alert from Follow-up #{followup_id}")
    flash("Alert marked as resolved!", "success")
    return redirect("/dashboard")

@app.route("/delete_followup/<int:followup_id>", methods=["POST"])
@login_required
@admin_required
def delete_followup(followup_id):
    """Permanently deletes a social work follow-up note (Admins Only)"""
    followup = db.execute("SELECT student_id FROM followups WHERE id = ?", followup_id)
    if not followup:
        flash("Follow-up note not found.", "danger")
        return redirect(request.referrer or "/")

    student_id = followup[0]["student_id"]
    
    db.execute("DELETE FROM followups WHERE id = ?", followup_id)
    
    log_action(f"DELETED Social Work Follow-Up #{followup_id} for Student ID: {student_id}")
    flash("Follow-up note permanently deleted.", "success")
    return redirect(f"/student/{student_id}/timeline")


# ==============================================================================
# NEIGHBORHOOD: FILES & FUNDS
# ==============================================================================

@app.route('/upload_document/<int:student_id>', methods=['POST'])
@login_required
@permission_required("can_create_files")
def upload_document(student_id):
    file = request.files.get('document_file')
    doc_type = request.form.get('document_type')

    if not file or file.filename == '':
        flash("No selected file", "danger")
        return redirect(f"/student/{student_id}/files")

    saved_name, original_name = handle_file_upload(file, student_id, "doc", app.config['UPLOAD_FOLDER'])
    if saved_name:
        db.execute("INSERT INTO documents (student_id, original_filename, saved_filename, document_type) VALUES (?, ?, ?, ?)",
                   student_id, original_name, saved_name, doc_type)
        log_action(f"Uploaded Document '{doc_type}' for Student ID: {student_id}")
        flash(f"{doc_type} successfully uploaded!", "success")
    else:
        flash("Invalid file type.", "danger")

    return redirect(f"/student/{student_id}/files")

@app.route("/delete_document/<int:doc_id>", methods=["POST", "GET"])
@login_required
@permission_required("can_delete_files")
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
    return redirect(f"/student/{student_id}/files")

@app.route("/log_expense/<int:student_id>", methods=["POST"])
@login_required
@permission_required("can_create_expenses")
def log_expense(student_id):
    amount = request.form.get("amount")
    category = request.form.get("category")
    vendor_name = request.form.get("vendor_name")
    expense_date = request.form.get("expense_date")
    
    if amount and category:
        db.execute("INSERT INTO student_expenses (student_id, amount, category, vendor_name, expense_date) VALUES (?, ?, ?, ?, ?)",
                   student_id, amount, category, vendor_name, expense_date)
        log_action(f"Logged ${amount} expense for Student ID: {student_id}")
        flash("Expense logged successfully!", "success")
    else:
        flash("Missing required fields.", "danger")
        
    return redirect(f"/student/{student_id}/finance")


# ==============================================================================
# NEIGHBORHOOD: SERVICES, ACTIVITIES & CALENDAR
# ==============================================================================

@app.route("/log_services", methods=["GET", "POST"])
@login_required
# Make sure your decorator matches your permissions layout. If you don't have a specific
# permission for logging services yet, you can leave it out, or use @admin_required.
def log_services():
    """Log meals, supplies, or absences for multiple students at once"""
    if request.method == "POST":
        service_date = request.form.get("service_date")
        service_type = request.form.get("service_type")
        notes = request.form.get("notes")
        student_ids = request.form.getlist("student_ids")

        if not student_ids:
            flash("You must select at least one student from the Roster.", "warning")
            return redirect("/roster?mode=bulk")

        if not service_date or not service_type:
            flash("Service Date and Type are required.", "danger")
            return redirect("/roster?mode=bulk")

        # Save the logs to the database
        for sid in student_ids:
            db.execute("""
                INSERT INTO student_services (student_id, service_date, service_type, notes)
                VALUES (?, ?, ?, ?)
            """, sid, service_date, service_type, notes)

        log_action(f"Logged '{service_type}' for {len(student_ids)} students")
        flash(f"Successfully logged {service_type} for {len(student_ids)} students!", "success")
        return redirect("/dashboard")

    else:
        # GET REQUEST: Catch the student IDs from the Roster's multi-select URL arguments
        student_ids = request.args.getlist("student_ids")
        
        selected_students = []
        if student_ids:
            # Dynamically create the placeholders (?,?,?) based on how many kids were selected
            placeholders = ','.join('?' * len(student_ids))
            # Include meal_plan so the template can show the indicator badges
            query = f"SELECT id, first_name, last_name, ngo_id, meal_plan FROM students WHERE id IN ({placeholders})"
            selected_students = db.execute(query, *student_ids)

        today_date = datetime.now().strftime('%Y-%m-%d')
        return render_template("operations/log_services.html", selected_students=selected_students, today_date=today_date)

@app.route("/log_activity", methods=["POST"])
@login_required
def log_activity():
    activity_type = request.form.get("activity_type")
    activity_date = request.form.get("activity_date")
    attendance_count = request.form.get("attendance_count")

    db.execute("INSERT INTO activities (activity_type, activity_date, attendance_count) VALUES (?, ?, ?)", 
               activity_type, activity_date, attendance_count)
    log_action(f"Logged Community Activity: {activity_type} ({attendance_count} attendees)")
    flash(f"Successfully logged {activity_type}!", "success")
    return redirect("/dashboard")

@app.route("/setup_calendar")
@login_required
def setup_calendar():
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
    flash("Calendar Database Table successfully created! You are ready to go.", "success")
    return redirect("/calendar")

@app.route("/calendar")
@login_required
def field_calendar():
    """Main view for the Field Calendar"""
    pid = session.get("program_id", 0)
    
    # 1. Fetch active students for the 'Relate to Student' dropdown
    students = db.execute("""
        SELECT id, first_name, last_name, ngo_id 
        FROM students 
        WHERE status = 'Active' AND (program_id = ? OR ? = 0) 
        ORDER BY first_name ASC
    """, pid, pid)
    
    # 2. Fetch Pending Tasks for the Sidebar
    # LOGIC: Show (My Personal Tasks) OR (Any Team Tasks in my Program)
    # Join with staff to get the 'creator_name'
    pending_tasks = db.execute("""
        SELECT t.*, s.first_name, s.last_name, st.username AS creator_name
        FROM tasks t 
        LEFT JOIN students s ON t.student_id = s.id 
        LEFT JOIN staff st ON t.staff_id = st.id
        WHERE t.status = 'Pending' 
        AND (t.program_id = ? OR ? = 0)
        AND (t.staff_id = ? OR t.is_team_task = 1)
        ORDER BY t.due_date ASC LIMIT 20
    """, pid, pid, session["user_id"])
    
    return render_template("operations/calendar.html", students=students, pending_tasks=pending_tasks)

@app.route("/api/tasks")
@login_required
def api_tasks():
    """JSON Feed for FullCalendar grid"""
    view_mode = request.args.get("view", "my")
    pid = session.get("program_id", 0)
    
    # Filter query based on 'My Schedule' vs 'Team View' toggle
    if view_mode == "team":
        tasks = db.execute("""
            SELECT t.*, st.username AS creator_name 
            FROM tasks t 
            LEFT JOIN staff st ON t.staff_id = st.id
            WHERE (t.program_id = ? OR ? = 0)
        """, pid, pid)
    else:
        tasks = db.execute("""
            SELECT t.*, st.username AS creator_name 
            FROM tasks t 
            LEFT JOIN staff st ON t.staff_id = st.id
            WHERE (t.program_id = ? OR ? = 0)
            AND (t.staff_id = ? OR t.is_team_task = 1)
        """, pid, pid, session["user_id"])
        
    events = []
    for t in tasks:
        # Determine Color Logic
        color = "#0d6efd" # Default Blue
        if t["status"] == "Holiday": color = "#ffc107" # Yellow
        elif t["status"] == "Completed": color = "#198754" # Green
        elif t["priority"] == "High": color = "#dc3545" # Red
        elif t["priority"] == "Low": color = "#6c757d" # Gray

        events.append({
            "id": t["id"],
            "title": t["title"],
            "start": t["due_date"],
            "color": color,
            "textColor": "#000" if t["status"] == "Holiday" else "#fff",
            "extendedProps": {
                "description": t["description"],
                "status": t["status"],
                "priority": t["priority"],
                "creator_name": t["creator_name"],
                "is_team_task": t["is_team_task"]
            }
        })
    return jsonify(events)

@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    """Handles both single tasks and holiday date ranges"""
    title = request.form.get("title")
    due_date = request.form.get("due_date") # This is Start Date
    end_date = request.form.get("end_date") # For holidays
    description = request.form.get("description")
    priority = request.form.get("priority")
    student_id = request.form.get("student_id")
    
    # 1. Clean data
    if not student_id or student_id == "None": student_id = None
    is_team_task = 1 if request.form.get("is_team_task") == "1" else 0
    is_holiday = request.form.get("is_holiday") == "1"
    
    if not title or not due_date:
        flash("Title and Date are required.", "danger")
        return redirect("/calendar")
        
    pid = session.get("program_id", 1)
    if pid == 0: pid = 1 
    
    # Holidays do not appear in to-do lists
    status = 'Holiday' if is_holiday else 'Pending'
    
    # 2. HOLIDAY RANGE LOGIC: Loop through dates
    if is_holiday and end_date and end_date != due_date:
        try:
            # Strip time if present to get pure dates
            start_str = due_date.split('T')[0]
            end_str = end_date.split('T')[0]
            
            start_dt = datetime.strptime(start_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_str, '%Y-%m-%d')
            
            current_dt = start_dt
            while current_dt <= end_dt:
                db.execute("""
                    INSERT INTO tasks (title, description, due_date, priority, status, student_id, staff_id, program_id, is_team_task) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, title, description, current_dt.strftime('%Y-%m-%d'), priority, status, student_id, session["user_id"], pid, 1)
                current_dt += timedelta(days=1)
            
            log_action(f"Logged Holiday Range: {title}")
            flash(f"Holiday '{title}' marked for the selected week.", "success")
        except Exception as e:
            flash(f"Error processing range: {e}", "danger")
    else:
        # 3. SINGLE TASK LOGIC
        db.execute("""
            INSERT INTO tasks (title, description, due_date, priority, status, student_id, staff_id, program_id, is_team_task) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, title, description, due_date, priority, status, student_id, session["user_id"], pid, is_team_task)
        
        log_action(f"Created task: {title}")
        flash("Added to calendar!", "success")
        
    return redirect("/calendar")

@app.route("/edit_task", methods=["POST"])
@login_required
def edit_task():
    """Handles updating existing task details"""
    task_id = request.form.get("task_id")
    title = request.form.get("title")
    due_date = request.form.get("due_date")
    description = request.form.get("description")
    priority = request.form.get("priority")
    
    # Permission Check: Ensure the user owns the task or is Admin
    task = db.execute("SELECT staff_id FROM tasks WHERE id = ?", task_id)
    if not task:
        flash("Task not found.", "danger")
        return redirect("/calendar")
        
    if session["role"] not in ["Admin", "Director"] and task[0]["staff_id"] != session["user_id"]:
        flash("Unauthorized: You can only edit your own tasks.", "danger")
        return redirect("/calendar")

    db.execute("""
        UPDATE tasks 
        SET title = ?, due_date = ?, description = ?, priority = ?
        WHERE id = ?
    """, title, due_date, description, priority, task_id)
    
    log_action(f"Updated task: {title}")
    flash("Task details updated successfully.", "success")
    return redirect("/calendar")

@app.route("/complete_task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    db.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", task_id)
    log_action(f"Marked task #{task_id} as Completed")
    flash("Task marked as completed! Great job.", "success")
    return redirect("/calendar")

@app.route("/delete_task/<int:task_id>", methods=["POST"])
@login_required
def delete_task(task_id):
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
# NEIGHBORHOOD: SETTINGS, EXPORTS & UTILITIES
# ==============================================================================

@app.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    """Master Control Panel for the NGO"""
    
    # 1. LOCALIZATION SETUP
    translation_file = os.path.join(app.root_path, 'translations.json')
    if not os.path.exists(translation_file):
        with open(translation_file, 'w', encoding='utf-8') as f:
            json.dump({}, f)

    # 2. DYNAMIC PERMISSIONS SETUP (WITH AUTO-HEALER FOR CRUD UPGRADE)
    db.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role TEXT PRIMARY KEY,
            can_edit_profiles INTEGER DEFAULT 0,
            can_manage_academics INTEGER DEFAULT 0,
            can_manage_followups INTEGER DEFAULT 0,
            can_upload_files INTEGER DEFAULT 0,
            can_export_data INTEGER DEFAULT 0
        )
    """)
    
    # Auto-Healer: Add CRUD Columns if they don't exist
    try:
        db.execute("SELECT can_create_academics FROM role_permissions LIMIT 1")
    except Exception:
        print("Upgrading role_permissions table to Granular CRUD...")
        columns = [
            "can_create_profiles", "can_update_profiles",
            "can_create_academics", "can_update_academics", "can_delete_academics",
            "can_create_followups", "can_update_followups",
            "can_create_files", "can_delete_files", "can_create_expenses"
        ]
        for col in columns:
            try:
                db.execute(f"ALTER TABLE role_permissions ADD COLUMN {col} INTEGER DEFAULT 0")
            except Exception:
                pass
        
        # Migrate old coarse settings to granular
        db.execute("UPDATE role_permissions SET can_create_profiles = can_edit_profiles, can_update_profiles = can_edit_profiles")
        db.execute("UPDATE role_permissions SET can_create_academics = can_manage_academics, can_update_academics = can_manage_academics")
        db.execute("UPDATE role_permissions SET can_create_followups = can_manage_followups, can_update_followups = can_manage_followups")
        db.execute("UPDATE role_permissions SET can_create_files = can_upload_files")
        db.execute("UPDATE role_permissions SET can_delete_academics = 1, can_delete_files = 1, can_create_expenses = 1 WHERE role = 'Admin'")

    existing_roles = db.execute("SELECT COUNT(*) as count FROM role_permissions")[0]['count']
    if existing_roles == 0:
        default_roles = ["Admin", "Director", "Program Manager", "Field Officer", "Teacher"]
        for r in default_roles:
            db.execute("INSERT INTO role_permissions (role) VALUES (?)", r)
        db.execute("UPDATE role_permissions SET can_create_profiles = 1, can_update_profiles = 1, can_create_academics = 1, can_update_academics = 1, can_delete_academics = 1, can_create_followups = 1, can_update_followups = 1, can_create_files = 1, can_delete_files = 1, can_create_expenses = 1, can_export_data = 1 WHERE role = 'Admin'")

    db.execute("CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)")
    if not db.execute("SELECT * FROM system_settings WHERE key = 'current_academic_year'"):
        db.execute("INSERT INTO system_settings (key, value) VALUES ('current_academic_year', '2025-2026')")

    if request.method == "POST":
        action = request.form.get("action")
        
        # SUBJECTS
        if action == "add_subject":
            new_subject = request.form.get("new_subject")
            category = request.form.get("category", "General") 
            if new_subject:
                if db.execute("SELECT id FROM subjects WHERE name = ?", new_subject):
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
                sub_id = subject['id']
                new_name = request.form.get(f"name_{sub_id}")
                sort_order = request.form.get(f"sort_{sub_id}")
                category = request.form.get(f"category_{sub_id}")
                if new_name and sort_order is not None and str(sort_order).strip() != "":
                    db.execute("UPDATE subjects SET name = ?, sort_order = ?, category = ? WHERE id = ?", new_name, sort_order, category, sub_id)
            log_action("Updated Subject Master Settings")
            flash("Subjects successfully updated!", "success")
        elif action == "delete_subject":
            sub_id = request.form.get("subject_id")
            grade_count = db.execute("SELECT COUNT(*) as count FROM grades WHERE subject_id = ?", sub_id)[0]['count']
            if grade_count > 0:
                flash(f"Cannot delete! There are {grade_count} grades linked to this subject.", "danger")
            else:
                sub_name = db.execute("SELECT name FROM subjects WHERE id = ?", sub_id)[0]['name']
                db.execute("DELETE FROM subjects WHERE id = ?", sub_id)
                log_action(f"Deleted Subject: {sub_name}")
                flash(f"Subject '{sub_name}' permanently deleted.", "success")
                
        # PROGRAMS
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
            if int(prog_id) in [0, 1]:
                flash("Security Error: Cannot delete core system programs.", "danger")
            else:
                student_count = db.execute("SELECT COUNT(*) as count FROM students WHERE program_id = ?", prog_id)[0]['count']
                if student_count > 0:
                    flash(f"Cannot delete! {student_count} students are enrolled in this program.", "danger")
                else:
                    db.execute("DELETE FROM programs WHERE id = ?", prog_id)
                    log_action("Deleted an NGO Program")
                    flash("Program successfully deleted.", "success")

        # SYSTEM
        elif action == "update_system":
            # DYNAMIC KEY-VALUE STORE: Upsert ANY form field sent from the System tab
            for key, value in request.form.items():
                if key != "action" and value and value.strip():
                    existing = db.execute("SELECT key FROM system_settings WHERE key = ?", key)
                    if existing:
                        db.execute("UPDATE system_settings SET value = ? WHERE key = ?", value, key)
                    else:
                        db.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", key, value)
            log_action("Updated Global System Configurations")
            flash("System variables updated successfully!", "success")

        # LOCALIZATION
        elif action == "add_translation":
            new_key = request.form.get("new_key", "").strip()
            new_en = request.form.get("new_en", "").strip()
            new_kh = request.form.get("new_kh", "").strip()
            if new_key:
                with open(translation_file, 'r', encoding='utf-8') as f:
                    translations = json.load(f)
                translations[new_key] = {"en": new_en, "kh": new_kh}
                with open(translation_file, 'w', encoding='utf-8') as f:
                    json.dump(translations, f, ensure_ascii=False, indent=4)
                flash(f"Added translation for '{new_key}'.", "success")
        elif action == "update_translations":
            pass 
            flash("Translations deployed successfully!", "success")
        elif action == "delete_translation":
            del_key = request.form.get("translation_key")
            with open(translation_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            if del_key in translations:
                del translations[del_key]
                with open(translation_file, 'w', encoding='utf-8') as f:
                    json.dump(translations, f, ensure_ascii=False, indent=4)
                flash(f"Deleted translation key '{del_key}'.", "success")

        # DYNAMIC PERMISSIONS (CRUD UPDATE)
        elif action == "update_permissions":
            roles = ["Admin", "Director", "Program Manager", "Field Officer", "Teacher"]
            for r in roles:
                c_prof = 1 if request.form.get(f"{r}_create_profiles") else 0
                u_prof = 1 if request.form.get(f"{r}_update_profiles") else 0
                c_acad = 1 if request.form.get(f"{r}_create_academics") else 0
                u_acad = 1 if request.form.get(f"{r}_update_academics") else 0
                d_acad = 1 if request.form.get(f"{r}_delete_academics") else 0
                c_foll = 1 if request.form.get(f"{r}_create_followups") else 0
                u_foll = 1 if request.form.get(f"{r}_update_followups") else 0
                c_file = 1 if request.form.get(f"{r}_create_files") else 0
                d_file = 1 if request.form.get(f"{r}_delete_files") else 0
                c_exp = 1 if request.form.get(f"{r}_create_expenses") else 0
                exp_data = 1 if request.form.get(f"{r}_export_data") else 0
                
                db.execute("""
                    UPDATE role_permissions
                    SET can_edit_profiles = ?, can_create_profiles = ?, can_update_profiles = ?,
                        can_manage_academics = ?, can_create_academics = ?, can_update_academics = ?, can_delete_academics = ?,
                        can_manage_followups = ?, can_create_followups = ?, can_update_followups = ?,
                        can_upload_files = ?, can_create_files = ?, can_delete_files = ?, can_create_expenses = ?,
                        can_export_data = ?
                    WHERE role = ?
                """, u_prof, c_prof, u_prof, 
                     u_acad, c_acad, u_acad, d_acad, 
                     u_foll, c_foll, u_foll, 
                     c_file, c_file, d_file, c_exp, 
                     exp_data, r)
            log_action("Updated Global Role Permissions Matrix")
            flash("Role permissions successfully updated!", "success")

        return redirect("/settings")

    subjects = db.execute("SELECT * FROM subjects ORDER BY category ASC, sort_order ASC, name ASC")
    programs = db.execute("SELECT * FROM programs ORDER BY id ASC")
    sys_raw = db.execute("SELECT * FROM system_settings")
    sys_settings = {row['key']: row['value'] for row in sys_raw}
    role_permissions = db.execute("SELECT * FROM role_permissions ORDER BY role ASC")
    with open(translation_file, 'r', encoding='utf-8') as f:
        translations = json.load(f)

    return render_template("admin/settings.html", subjects=subjects, programs=programs, sys_settings=sys_settings, translations=translations, role_permissions=role_permissions)


@app.route('/export_students')
@login_required
@permission_required("can_export_data")
def export_students():
    pid = session.get("program_id", 0)
    students = db.execute("SELECT id, ngo_id, first_name, last_name, gender, dob, status, slum_area, current_school, grade_level FROM students WHERE (program_id = ? OR ? = 0) ORDER BY last_name", pid, pid)
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
@permission_required("can_export_data")
def export_grades():
    pid = session.get("program_id", 0)
    reports = db.execute("""
        SELECT s.ngo_id, s.first_name, s.last_name, m.academic_year, m.month, m.grade_level, m.overall_average, m.class_rank
        FROM monthly_reports m
        JOIN students s ON m.student_id = s.id
        WHERE (s.program_id = ? OR ? = 0)
        ORDER BY m.academic_year DESC, m.month DESC
    """, pid, pid)
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
    flash("Staff Export feature will be fully activated in Phase 8!", "info")
    return redirect(request.referrer or "/")

@app.route('/export_compliance')
@login_required
def export_compliance():
    flash("Compliance Export feature will be fully activated in Phase 8!", "info")
    return redirect(request.referrer or "/")

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/manifest+json')

if __name__ == "__main__":
    app.run(debug=True)