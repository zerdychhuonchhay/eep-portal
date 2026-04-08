import os
import time
from functools import wraps
from flask import redirect, session, flash, request
from werkzeug.utils import secure_filename

# =========================================================
# 1. THE SECURITY BOUNCERS
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
        if session.get("role") != "Admin":
            flash("Unauthorized Action: Only Admins can perform this action.", "danger")
            return redirect(request.referrer or "/")
        return f(*args, **kwargs)
    return decorated_function

def real_admin_required(f):
    """Ensures the user is genuinely an Admin, even if they are using 'View As' to test a lower role."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        actual_role = session.get("real_role", session.get("role"))
        if actual_role != "Admin":
            flash("System Security: Only true Admins can use the View As feature.", "danger")
            return redirect(request.referrer or "/")
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_key):
    """Checks the granular RBAC permissions loaded into the user session at login."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Always allow Admins, otherwise check specific boolean flag
            if session.get("role") != "Admin" and not session.get(permission_key):
                flash(f"Unauthorized Access: You lack the required permission to perform this action.", "danger")
                return redirect(request.referrer or "/")
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =========================================================
# 2. THE MATH ENGINE
# =========================================================
def calculate_gpa(calculated_total, calculated_max, has_numeric, missing_max):
    """Calculates the average and assigns an automated letter grade."""
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
            if pct >= 85:
                grade_letter, color = 'A', 'success'
            elif pct >= 80:
                grade_letter, color = 'B', 'success'
            elif pct >= 70:
                grade_letter, color = 'C', 'warning'
            elif pct >= 60:
                grade_letter, color = 'D', 'danger'
            elif pct >= 50:
                grade_letter, color = 'E', 'danger'
            else:
                grade_letter, color = 'F', 'danger'
                
            box_class = f'bg-{color} bg-opacity-10 border-{color} border-opacity-25'
            text_class = f'text-{color}'
            badge_class = f'bg-{color}'
            
    except ValueError:
        # Handles manual text grades like "A" or "Pass"
        text_upper = score_str.upper()
        if text_upper in ['A', 'B', 'A+', 'A-', 'B+', 'B-', 'GOOD', 'EXCELLENT', 'PASS']:
            color = 'success'
        elif text_upper in ['C', 'C+', 'C-', 'AVERAGE', 'FAIR']:
            color = 'warning'
        elif text_upper in ['D', 'E', 'F', 'POOR', 'FAIL']:
            color = 'danger'
        else:
            color = None
            
        if color:
            box_class = f'bg-{color} bg-opacity-10 border-{color} border-opacity-25'
            text_class = f'text-{color}'

    return grade_letter, box_class, text_class, badge_class

# =========================================================
# 3. THE FILE UPLOAD MANAGER
# =========================================================
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'doc', 'docx', 'webp', 'heic', 'heif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def handle_file_upload(file, prefix_id, prefix_type, upload_folder):
    """Safely processes, renames with a timestamp, and saves an uploaded file."""
    if file and file.filename != '' and allowed_file(file.filename):
        original_name = secure_filename(file.filename)
        # Result example: report_5_1678888_math.pdf
        saved_name = f"{prefix_type}_{prefix_id}_{int(time.time())}_{original_name}"
        file_path = os.path.join(upload_folder, saved_name)
        file.save(file_path)
        return saved_name, original_name
    return None, None