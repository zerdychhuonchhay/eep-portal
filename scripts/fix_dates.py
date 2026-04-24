import sqlite3
from datetime import datetime

# 1. Open the vault
conn = sqlite3.connect("eep.db")
db = conn.cursor()

# 2. Grab all students
db.execute("SELECT id, dob, joined_date, first_name FROM students")
students = db.fetchall()

fixed_count = 0

print("🔍 Scanning database for Excel-formatted dates...")

# 3. Loop through and fix the dates
for student in students:
    student_id = student[0]
    dob = student[1]
    joined = student[2]
    name = student[3]

    new_dob = dob
    new_joined = joined
    needs_update = False

    # Check and fix DOB
    if dob and '/' in dob:
        try:
            # Convert '10/8/2020' to '2020-10-08'
            new_dob = datetime.strptime(dob, "%m/%d/%Y").strftime("%Y-%m-%d")
            needs_update = True
        except ValueError:
            pass

    # Check and fix Joined Date
    if joined and '/' in joined:
        try:
            new_joined = datetime.strptime(joined, "%m/%d/%Y").strftime("%Y-%m-%d")
            needs_update = True
        except ValueError:
            pass

    # Save to database if changes were made
    if needs_update:
        db.execute("UPDATE students SET dob = ?, joined_date = ? WHERE id = ?", (new_dob, new_joined, student_id))
        fixed_count += 1
        print(f"✅ Fixed dates for {name}: DOB({new_dob})")

# 4. Lock the vault
conn.commit()
conn.close()

print(f"\n🎉 DONE! {fixed_count} student records were reformatted for HTML compatibility.")
