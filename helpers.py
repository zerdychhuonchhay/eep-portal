import os
import time
from functools import wraps
from flask import redirect, session, flash, request
from werkzeug.utils import secure_filename
from cs50 import SQL

# =========================================================
# 1. CENTRALIZED DATABASE CONNECTION & AUDIT LOGGER
# =========================================================
# This centralizes the connection so Blueprints don't cause circular imports!
db = SQL("sqlite:///eep.db")

def log_action(description):
    """Silently record what a staff member just did across the entire app"""
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


# =========================================================
# 2. LIVE DATABASE CHECKERS (Fixed Concurrency)
# =========================================================
def get_live_role(user_id):
    """Fetches the user's role directly from the database (No more raw SQLite locks!)"""
    if not user_id:
        return None
    try:
        user = db.execute("SELECT role FROM staff WHERE id = ?", user_id)
        return user[0]["role"] if user else None
    except Exception:
        return session.get("role")

def get_live_permission(role, permission_key):
    """Fetches the exact granular permission for a role directly from the database"""
    if role == "Admin":
        return True
    try:
        perms = db.execute("SELECT * FROM role_permissions WHERE role = ?", role)
        if perms and permission_key in perms[0] and perms[0][permission_key] == 1:
            return True
        return False
    except Exception:
        return session.get(permission_key)

# =========================================================
# 3. THE SECURITY BOUNCERS
# =========================================================
def login_required(f):
    """Ensures a user is logged in before viewing a page."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Ensures ONLY Admins can perform destructive actions like Delete."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("real_role"):
            active_role = session.get("role")
        else:
            active_role = get_live_role(session.get("user_id"))

        if active_role != "Admin":
            flash("Unauthorized Action: Only Admins can perform this action.", "danger")
            return redirect(request.referrer or "/")
        return f(*args, **kwargs)
    return decorated_function

def real_admin_required(f):
    """Ensures the user is genuinely an Admin, even if they are using 'View As' to test a lower role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        actual_role = get_live_role(session.get("user_id"))
        if actual_role != "Admin":
            flash("System Security: Only true Admins can use the View As feature.", "danger")
            return redirect(request.referrer or "/")
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_key):
    """Checks the LIVE granular RBAC permissions from the database."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            
            if session.get("real_role"):
                active_role = session.get("role")
            else:
                active_role = get_live_role(user_id)
            
            if active_role != "Admin" and not get_live_permission(active_role, permission_key):
                flash("Unauthorized Access: You lack the required permission to perform this action.", "danger")
                return redirect(request.referrer or "/")
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =========================================================
# 4. THE MATH & GRADING ENGINE
# =========================================================
def evaluate_grade(percentage):
    """ MASTER GRADING SCALE """
    if percentage >= 90: return "A", "success"
    elif percentage >= 80: return "B", "success"
    elif percentage >= 70: return "C", "warning"
    elif percentage >= 60: return "D", "danger"
    elif percentage >= 50: return "E", "danger"
    else: return "F", "danger"

def calculate_gpa(calculated_total, calculated_max, has_numeric, missing_max):
    """Calculates the overall average and assigns an automated letter grade."""
    if has_numeric and calculated_max > 0 and not missing_max:
        calculated_avg = round((calculated_total / calculated_max) * 100, 2)
    else:
        calculated_avg = None

    if calculated_avg is not None:
        calculated_grade, _ = evaluate_grade(calculated_avg)
    else:
        calculated_grade = "N/A"
        
    return calculated_avg, calculated_grade


def get_subject_grade_data(score_raw, max_raw):
    """Calculates A-F and CSS color classes for an individual subject score"""
    box_class = 'bg-light border-secondary border-opacity-10'
    text_class = 'text-dark'
    badge_class = ''
    grade_letter = ''

    if not score_raw or score_raw == '-' or str(score_raw).strip() == '':
        return grade_letter, box_class, text_class, badge_class

    score_str = str(score_raw).strip()
    
    try:
        score = float(score_str)
        max_score = float(max_raw) if max_raw and str(max_raw).strip() != '' else 100.0
        
        if max_score > 0:
            pct = (score / max_score) * 100
            grade_letter, color = evaluate_grade(pct)
            box_class = f'bg-{color} bg-opacity-10 border-{color} border-opacity-25'
            text_class = f'text-{color}'
            badge_class = f'bg-{color}'
            
    except ValueError:
        # Handles manual text grades like "A" or "Pass"
        text_upper = score_str.upper()
        if text_upper in ['A', 'B', 'A+', 'A-', 'B+', 'B-', 'GOOD', 'EXCELLENT', 'PASS']: color = 'success'
        elif text_upper in ['C', 'C+', 'C-', 'AVERAGE', 'FAIR']: color = 'warning'
        elif text_upper in ['D', 'E', 'F', 'POOR', 'FAIL']: color = 'danger'
        else: color = None
            
        if color:
            box_class = f'bg-{color} bg-opacity-10 border-{color} border-opacity-25'
            text_class = f'text-{color}'

    return grade_letter, box_class, text_class, badge_class


# =========================================================
# 5. THE FILE UPLOAD MANAGER
# =========================================================
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'webp', 'heic', 'heif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_file_upload(file, prefix_id, prefix_type, upload_folder):
    """Safely processes, renames with a timestamp, and saves an uploaded file."""
    if file and file.filename != '' and allowed_file(file.filename):
        original_name = secure_filename(file.filename)
        saved_name = f"{prefix_type}_{prefix_id}_{int(time.time())}_{original_name}"
        file_path = os.path.join(upload_folder, saved_name)
        file.save(file_path)
        return saved_name, original_name
    return None, None