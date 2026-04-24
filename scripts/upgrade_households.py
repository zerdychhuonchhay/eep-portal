import sqlite3

print("👷 Upgrading Households Table for Blended Families...")

conn = sqlite3.connect("eep.db")
db = conn.cursor()

columns_to_add = [
    ("caregiver_picture", "TEXT"),
    ("adults_in_home", "TEXT"),
    ("total_headcount", "INTEGER")
]

for col_name, col_type in columns_to_add:
    try:
        db.execute(f"ALTER TABLE households ADD COLUMN {col_name} {col_type}")
        print(f"✅ Added '{col_name}' column.")
    except sqlite3.OperationalError:
        print(f"⚠️ '{col_name}' already exists.")

conn.commit()
conn.close()
print("🎉 UPGRADE COMPLETE! Your households can now track step-parents and photos.")