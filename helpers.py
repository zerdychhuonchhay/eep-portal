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