import sqlite3

print("👷 Starting Kinship Database Upgrade...")

# 1. Connect to the vault
conn = sqlite3.connect("eep.db")
db = conn.cursor()

# 2. Define the new columns we need
columns_to_add = [
    ("mother_name", "TEXT"),
    ("father_name", "TEXT"),
    ("caregiver_relationship", "TEXT")
]

# 3. Safely add each column to the students table
print("🔨 Upgrading 'students' table...")
for col_name, col_type in columns_to_add:
    try:
        # If it already exists, SQLite throws an error, which we catch safely.
        db.execute(f"ALTER TABLE students ADD COLUMN {col_name} {col_type}")
        print(f"✅ Successfully added '{col_name}' column.")
    except sqlite3.OperationalError:
        print(f"⚠️ '{col_name}' already exists. Skipping this step.")

# 4. Lock the vault
conn.commit()
conn.close()

print("🎉 UPGRADE COMPLETE! Your database is ready to track complex family trees.")