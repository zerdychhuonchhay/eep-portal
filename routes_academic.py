import os
import calendar
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, session, flash, redirect, jsonify, current_app

# Import our shared tools from helpers
from helpers import login_required, permission_required, calculate_gpa, get_subject_grade_data, handle_file_upload, db, log_action

# Define the Blueprint
academic_bp = Blueprint('academic_bp', __name__)

# ==============================================================================
# MASTER GRADEBOOK
# ==============================================================================
@academic_bp.route("/academics")
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

    active_students = db.execute("SELECT id, first_name, last_name, ngo_id, profile_picture, grade_level FROM students WHERE status = 'Active' AND (program_id = ? OR ? = 0) ORDER BY first_name", pid, pid)

    today = datetime.now()
    first_of_this_month = today.replace(day=1)
    last_month_date = first_of_this_month - timedelta(days=1)
    last_month_name = last_month_date.strftime('%B')

    sys_raw = db.execute("SELECT value FROM system_settings WHERE key = 'current_academic_year'")
    current_year_default = sys_raw[0]['value'] if sys_raw else "2025-2026"

    missing_audit = db.execute("""
        SELECT id, first_name, last_name, ngo_id, profile_picture, grade_level
        FROM students
        WHERE status = 'Active' AND (program_id = ? OR ? = 0)
        AND grade_level NOT LIKE '%University%'
        AND grade_level NOT LIKE '%Vocational%'
        AND id NOT IN (
            SELECT student_id FROM monthly_reports
            WHERE month = ? AND academic_year = ?
        )
        ORDER BY first_name ASC
    """, pid, pid, last_month_name, current_year_default)

    return render_template("academics/academics.html", 
                           academic_records=academic_records_raw, 
                           active_students=active_students,
                           missing_audit=missing_audit,
                           audit_month=last_month_name,
                           audit_year=current_year_default)

# ==============================================================================
# ADD REPORT CARD
# ==============================================================================
@academic_bp.route("/add_report/<int:student_id>", methods=["GET", "POST"])
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
        scanned_filename, _ = handle_file_upload(file, student_id, "report", current_app.config['UPLOAD_FOLDER'])

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

        custom_names = request.form.getlist("custom_subject_name[]")
        custom_scores = request.form.getlist("custom_score[]")
        custom_maxes = request.form.getlist("custom_max_score[]")

        for i in range(len(custom_scores)):
            c_score = custom_scores[i]
            c_name = custom_names[i] if i < len(custom_names) else "Custom Subject"
            c_max = custom_maxes[i] if i < len(custom_maxes) else "100"

            if c_score and str(c_score).strip() != "":
                db.execute("INSERT INTO grades (report_id, subject_id, score, max_score, custom_subject_name) VALUES (?, 0, ?, ?, ?)",
                           report_id, c_score, c_max, c_name)
                try:
                    calculated_total += float(c_score)
                    if c_max and str(c_max).strip() != "":
                        calculated_max += float(c_max)
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
    
    schools_raw = db.execute("SELECT DISTINCT current_school FROM students WHERE current_school IS NOT NULL AND current_school != '' ORDER BY current_school")
    schools = [s['current_school'] for s in schools_raw]
    
    return render_template("academics/add_report.html", student=student, subjects=subjects, schools=schools)

# ==============================================================================
# EDIT REPORT CARD
# ==============================================================================
@academic_bp.route("/edit_report/<int:report_id>", methods=["GET", "POST"])
@login_required
@permission_required("can_update_academics")
def edit_report(report_id):
    """Edit an existing monthly academic report"""
    report_data = db.execute("SELECT * FROM monthly_reports WHERE id = ?", report_id)
    if not report_data:
        flash("Error: Academic report not found.", "danger")
        return redirect(request.referrer or "/roster")
    
    report = report_data[0]
    student_id = report['student_id']

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
            WHERE student_id = ? AND month = ? AND academic_year = ? AND IFNULL(semester, '') = IFNULL(?, '') AND id != ?
        """, student_id, month, academic_year, semester, report_id)

        if existing_report:
            return render_template("_layouts/apology.html", message=f"A {semester if semester else 'Regular'} report for {month} {academic_year} already exists! Please use your browser's BACK arrow to return to the form.")

        file = request.files.get('scanned_document')
        if file and file.filename != '':
            scanned_filename, _ = handle_file_upload(file, student_id, "report", current_app.config['UPLOAD_FOLDER'])
            db.execute("UPDATE monthly_reports SET scanned_document = ? WHERE id = ?", scanned_filename, report_id)

        db.execute("""
            UPDATE monthly_reports 
            SET month = ?, academic_year = ?, semester = ?, class_rank = ?, teacher_comment = ?, attendance_days = ?, grade_level = ?, school_name = ?
            WHERE id = ?
        """, month, academic_year, semester, class_rank, teacher_comment, attendance_days, grade_level, school_name, report_id)

        subjects = db.execute("SELECT * FROM subjects")
        calculated_total = 0.0
        calculated_max = 0.0
        has_numeric = False
        missing_max = False

        for subject in subjects:
            sub_id = subject['id']
            score = request.form.get(f"score_{sub_id}")
            max_score = request.form.get(f"max_score_{sub_id}")

            if score and str(score).strip() != "":
                existing_grade = db.execute("SELECT id FROM grades WHERE report_id = ? AND subject_id = ?", report_id, sub_id)
                
                if existing_grade:
                    db.execute("UPDATE grades SET score = ?, max_score = ? WHERE report_id = ? AND subject_id = ?", 
                               score, max_score, report_id, sub_id)
                else:
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
            else:
                db.execute("DELETE FROM grades WHERE report_id = ? AND subject_id = ?", report_id, sub_id)

        db.execute("DELETE FROM grades WHERE report_id = ? AND subject_id = 0", report_id)

        custom_names = request.form.getlist("custom_subject_name[]")
        custom_scores = request.form.getlist("custom_score[]")
        custom_maxes = request.form.getlist("custom_max_score[]")

        for i in range(len(custom_scores)):
            c_score = custom_scores[i]
            c_name = custom_names[i] if i < len(custom_names) else "Custom Subject"
            c_max = custom_maxes[i] if i < len(custom_maxes) else "100"

            if c_score and str(c_score).strip() != "":
                db.execute("INSERT INTO grades (report_id, subject_id, score, max_score, custom_subject_name) VALUES (?, 0, ?, ?, ?)",
                           report_id, c_score, c_max, c_name)
                try:
                    calculated_total += float(c_score)
                    if c_max and str(c_max).strip() != "":
                        calculated_max += float(c_max)
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

        log_action(f"Updated academic report for Student ID: {student_id}")
        flash("Academic report successfully updated!", "success")
        return redirect(source_url) if source_url else redirect(f"/student/{student_id}")

    student = db.execute("SELECT * FROM students WHERE id = ?", student_id)[0]
    subjects = db.execute("SELECT * FROM subjects ORDER BY category ASC, sort_order ASC, name ASC")
    
    schools_raw = db.execute("SELECT DISTINCT current_school FROM students WHERE current_school IS NOT NULL AND current_school != '' ORDER BY current_school")
    schools = [s['current_school'] for s in schools_raw]
    
    grades_raw = db.execute("SELECT * FROM grades WHERE report_id = ?", report_id)
    existing_grades = {g['subject_id']: g for g in grades_raw if g['subject_id'] != 0}
    custom_grades = [g for g in grades_raw if g['subject_id'] == 0]

    return render_template("academics/edit_report.html", 
                           student=student, 
                           report=report, 
                           subjects=subjects, 
                           schools=schools,
                           existing_grades=existing_grades,
                           custom_grades=custom_grades)

# ==============================================================================
# DELETE REPORT CARD
# ==============================================================================
@academic_bp.route("/delete_report/<int:report_id>", methods=["POST"])
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
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], scanned_doc)
        if os.path.exists(file_path):
            os.remove(file_path)

    db.execute("DELETE FROM grades WHERE report_id = ?", report_id)
    db.execute("DELETE FROM monthly_reports WHERE id = ?", report_id)

    log_action(f"DELETED academic report #{report_id} for Student ID: {student_id}")
    flash("Academic record deleted successfully.", "success")
    return redirect(request.referrer or f"/student/{student_id}")

# ==============================================================================
# ACADEMIC REVIEW DASHBOARD
# ==============================================================================
@academic_bp.route("/academic_review", methods=["GET"])
@login_required
@permission_required("can_manage_academics")
def academic_review():
    """A powerful query tool to filter, tier, and analyze students by academic standing."""
    program_id = session.get("program_id")
    
    sys_raw = db.execute("SELECT value FROM system_settings WHERE key = 'current_academic_year'")
    current_year_default = sys_raw[0]['value'] if sys_raw else "2025-2026"
    
    academic_year = request.args.get("academic_year", current_year_default)
    timeframe = request.args.get("timeframe", "latest") 
    
    available_years = [r['academic_year'] for r in db.execute("SELECT DISTINCT academic_year FROM monthly_reports ORDER BY academic_year DESC")]
    
    months_raw = db.execute("""
        SELECT DISTINCT m.month 
        FROM monthly_reports m
        JOIN students s ON m.student_id = s.id
        WHERE m.academic_year = ? AND s.program_id = ?
    """, academic_year, program_id)
    
    academic_order = ['August', 'September', 'October', 'November', 'December', 'January', 'February', 'March', 'April', 'May', 'June', 'July']
    available_months = [r['month'] for r in months_raw]
    available_months.sort(key=lambda x: academic_order.index(x) if x in academic_order else 99)

    if timeframe == "latest":
        query = """
            SELECT s.id, s.first_name, s.last_name, s.khmer_name, s.ngo_id, s.grade_level, s.profile_picture,
                   m.month, m.overall_average, m.overall_grade, m.teacher_comment, m.id as report_id
            FROM students s
            JOIN monthly_reports m ON s.id = m.student_id
            INNER JOIN (
                SELECT student_id, MAX(id) as max_id 
                FROM monthly_reports 
                WHERE academic_year = ? 
                GROUP BY student_id
            ) latest ON m.id = latest.max_id
            WHERE s.status = 'Active' AND s.program_id = ?
            AND m.overall_average IS NOT NULL
        """
        raw_reports = db.execute(query, academic_year, program_id)
        timeframe_label = "Latest Report (Current Status)"
    else:
        query = """
            SELECT s.id, s.first_name, s.last_name, s.khmer_name, s.ngo_id, s.grade_level, s.profile_picture,
                   m.month, m.overall_average, m.overall_grade, m.teacher_comment, m.id as report_id
            FROM students s
            JOIN monthly_reports m ON s.id = m.student_id
            WHERE s.status = 'Active' AND s.program_id = ? AND m.academic_year = ?
            AND m.month = ? AND m.overall_average IS NOT NULL
        """
        raw_reports = db.execute(query, program_id, academic_year, timeframe)
        timeframe_label = f"{timeframe} Report"

    report_ids = [r['report_id'] for r in raw_reports if r['report_id']]
    grades_by_report = {}
    
    if report_ids:
        placeholders = ','.join(['?'] * len(report_ids))
        grades_raw = db.execute(f"""
            SELECT g.report_id, g.score, g.max_score, COALESCE(s.name, g.custom_subject_name) as subject_name
            FROM grades g
            LEFT JOIN subjects s ON g.subject_id = s.id
            WHERE g.report_id IN ({placeholders})
        """, *report_ids)
        
        for g in grades_raw:
            try:
                score = float(g['score'])
                max_score = float(g['max_score']) if g['max_score'] else 100.0
                pct = (score / max_score) * 100
                rid = g['report_id']
                
                if rid not in grades_by_report:
                    grades_by_report[rid] = {'poor': [], 'good': []}
                    
                s_name = g['subject_name'] if g['subject_name'] else 'Unknown'
                
                if pct < 50:
                    grades_by_report[rid]['poor'].append(s_name)
                elif pct >= 80:
                    grades_by_report[rid]['good'].append(s_name)
            except (ValueError, TypeError):
                pass

    critical = [] 
    at_risk = []  
    passing = []  
    
    for r in raw_reports:
        avg = float(r['overall_average'])
        r['overall_average'] = round(avg, 1)
        
        rid = r['report_id']
        poor_list = grades_by_report.get(rid, {}).get('poor', [])
        good_list = grades_by_report.get(rid, {}).get('good', [])
        r['poor_str'] = ", ".join(poor_list) if poor_list else "None"
        r['good_str'] = ", ".join(good_list) if good_list else "None"
        r['poor_raw'] = poor_list
        r['good_raw'] = good_list
        
        if avg < 50:
            r['category'] = 'Critical'
            r['badge'] = 'danger'
            critical.append(r)
        elif avg < 70:
            r['category'] = 'At Risk'
            r['badge'] = 'warning'
            at_risk.append(r)
        else:
            r['category'] = 'On Track'
            r['badge'] = 'success'
            passing.append(r)
            
    critical.sort(key=lambda x: x['overall_average'])
    at_risk.sort(key=lambda x: x['overall_average'])
    passing.sort(key=lambda x: x['overall_average'], reverse=True)
    
    total_active_raw = db.execute("SELECT COUNT(id) as count FROM students WHERE status='Active' AND program_id = ?", program_id)
    total_active = total_active_raw[0]['count'] if total_active_raw else 0
    
    return render_template("operations/academic_review.html",
                           critical=critical, 
                           at_risk=at_risk, 
                           passing=passing,
                           total_active=total_active,
                           academic_year=academic_year,
                           timeframe=timeframe,
                           timeframe_label=timeframe_label,
                           available_years=available_years,
                           available_months=available_months)

# ==============================================================================
# OFFICIAL REPORTS EXPORT TOOL
# ==============================================================================
@academic_bp.route("/report_builder", methods=["GET"])
@login_required
@permission_required("can_export_data")  
def report_builder():
    """Renders the UI to build the official monthly NGO report"""
    return render_template("operations/report_builder.html")

@academic_bp.route("/api/get_program_report", methods=["GET"])
@login_required
def get_program_report():
    """API Endpoint to fetch a saved report draft"""
    month = request.args.get("month")
    year = request.args.get("year")
    program_id = session.get("program_id")
    
    if not month or not year:
         return jsonify({"success": False, "error": "Missing parameters"})
         
    try:
        report = db.execute("SELECT achievements, goals, challenges FROM program_reports WHERE month = ? AND year = ? AND program_id = ?", month, year, program_id)
        if report:
            return jsonify({"success": True, "report": report[0]})
        return jsonify({"success": False})
    except Exception:
        return jsonify({"success": False})

@academic_bp.route("/generate_monthly_report", methods=["POST"])
@login_required
def generate_monthly_report():
    """Processes the form, calculates DB statistics, and generates the printable A4 report"""
    
    program_id = session.get("program_id")
    month_name = request.form.get("report_month")
    year = request.form.get("report_year")
    achievements = request.form.get("achievements")
    goals = request.form.get("goals")
    challenges = request.form.get("challenges")
    
    try:
        db.execute("CREATE TABLE IF NOT EXISTS program_reports (id INTEGER PRIMARY KEY AUTOINCREMENT, program_id INTEGER, month TEXT, year TEXT, achievements TEXT, goals TEXT, challenges TEXT)")
        
        existing = db.execute("SELECT id FROM program_reports WHERE month = ? AND year = ? AND program_id = ?", month_name, year, program_id)
        if existing:
            db.execute("UPDATE program_reports SET achievements = ?, goals = ?, challenges = ? WHERE id = ?", achievements, goals, challenges, existing[0]['id'])
        else:
            db.execute("INSERT INTO program_reports (program_id, month, year, achievements, goals, challenges) VALUES (?, ?, ?, ?, ?, ?)", program_id, month_name, year, achievements, goals, challenges)
    except Exception as e:
        print(f"Error saving report draft: {e}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True})
        
    khmer_months = {
        "January": "មករា", "February": "កុម្ភៈ", "March": "មីនា", "April": "មេសា",
        "May": "ឧសភា", "June": "មិថុនា", "July": "កក្កដា", "August": "សីហា",
        "September": "កញ្ញា", "October": "តុលា", "November": "វិច្ឆិកា", "December": "ធ្នូ"
    }
    month_kh = khmer_months.get(month_name, month_name)

    month_index = list(calendar.month_name).index(month_name)
    month_num = str(month_index).zfill(2)
    search_date_prefix = f"{year}-{month_num}"

    new_kids = db.execute("""
        SELECT first_name, last_name, khmer_name, gender, dob, grade_level, current_school 
        FROM students 
        WHERE strftime('%Y-%m', joined_date) = ? AND program_id = ?
    """, search_date_prefix, program_id)

    try:
        family_visits = db.execute("""
            SELECT COUNT(f.id) as count FROM followups f
            JOIN students s ON f.student_id = s.id
            WHERE strftime('%Y-%m', f.followup_date) = ? AND f.location = 'Home Visit' AND s.program_id = ?
        """, search_date_prefix, program_id)[0]['count']
    except IndexError:
        family_visits = 0

    try:
        meal_data = db.execute("""
            SELECT COUNT(DISTINCT srv.student_id) as count FROM student_services srv
            JOIN students s ON srv.student_id = s.id
            WHERE strftime('%Y-%m', srv.service_date) = ? 
            AND (srv.service_type = 'Monthly Groceries' OR srv.service_type = 'Missed Hot Lunch')
            AND s.program_id = ?
        """, search_date_prefix, program_id)[0]['count']
    except IndexError:
        meal_data = 0
        
    if meal_data == 0:
        try:
            meal_data = db.execute("SELECT COUNT(id) as count FROM students WHERE status='Active' AND meal_plan != 'None' AND meal_plan != '' AND program_id = ?", program_id)[0]['count']
        except IndexError:
            meal_data = 0

    return render_template("print/monthly_report.html", 
                           month=month_name, year=year, month_kh=month_kh,
                           achievements=achievements, goals=goals, challenges=challenges,
                           new_kids=new_kids, family_visits=family_visits, meal_count=meal_data)