import csv
import sqlite3

# 1. Open the vault
conn = sqlite3.connect("eep.db")
db = conn.cursor()

# 2. Open your CSV file
# Updated to match your exact uploaded filename!
file_name = "Students Profile.csv"

try:
    with open(file_name, "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        imported_count = 0
        skipped_count = 0

        for row in reader:
            # 3. Insert each row into the database
            # ADDED 'OR IGNORE': This skips students that are already in the database!
            db.execute("""
                INSERT OR IGNORE INTO students (
                    ngo_id, first_name, last_name, khmer_name, gender,
                    dob, joined_date, current_school, grade_level, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['ngo_id'],
                row['first_name'],
                row['last_name'],
                row['khmer_Name'],
                row['gender'],
                row['dob'],
                row['joined_date'],
                row['school'],
                row['grade'],
                'Active'
            ))

            # Check if the database actually inserted a new row
            if db.rowcount > 0:
                imported_count += 1
                print(f"✅ Imported: {row['first_name']} {row['last_name']}")
            else:
                skipped_count += 1
                print(f"⏭️ Skipped (Already exists): {row['first_name']} {row['last_name']}")

    # 4. Lock the vault and save the changes
    conn.commit()
    print(f"\n🎉 DONE! {imported_count} students added. {skipped_count} were skipped because they already existed.")

except FileNotFoundError:
    print(f"❌ ERROR: Could not find '{file_name}'. Make sure it's in the same folder as this script!")
except KeyError as e:
    print(f"❌ ERROR: Your CSV is missing a column header: {e}")
finally:
    conn.close()
