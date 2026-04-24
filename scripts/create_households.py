import sqlite3

print("👷 Building the missing Households table...")

# 1. Connect to the vault
conn = sqlite3.connect("eep.db")
db = conn.cursor()

# 2. Create the households table if it doesn't exist
db.execute("""
    CREATE TABLE IF NOT EXISTS households (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guardian_name TEXT NOT NULL,
        phone_number TEXT,
        slum_area TEXT,
        caregiver_picture TEXT,
        adults_in_home TEXT,
        total_headcount INTEGER
    )
""")
print("✅ Created 'households' table.")

# 3. Safely add the linking column to the students table
try:
    db.execute("ALTER TABLE students ADD COLUMN household_id INTEGER")
    print("✅ Added 'household_id' to students table.")
except sqlite3.OperationalError:
    print("⚠️ 'household_id' already exists in students table.")

# 4. Lock the vault
conn.commit()
conn.close()

print("🎉 DATABASE FIX COMPLETE! Start your Flask server and try again.")