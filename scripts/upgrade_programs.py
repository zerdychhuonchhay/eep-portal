import sqlite3

print("🌍 Initiating Phase 5: Multi-Program Architecture...")

conn = sqlite3.connect("eep.db")
db = conn.cursor()

# 1. Create the new Programs table
db.execute("""
    CREATE TABLE IF NOT EXISTS programs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        icon TEXT
    )
""")

# 2. Insert the 3 primary NGO programs (if they don't exist yet)
db.execute("SELECT COUNT(*) FROM programs")
if db.fetchone()[0] == 0:
    db.execute("INSERT INTO programs (name, icon) VALUES ('EEP (Education)', 'bi-book-fill')")
    db.execute("INSERT INTO programs (name, icon) VALUES ('Foster Care', 'bi-house-heart-fill')")
    db.execute("INSERT INTO programs (name, icon) VALUES ('Govt Affairs & HR', 'bi-file-earmark-text-fill')")
    print("✅ Created default NGO Programs.")

# 3. Add 'program_id' to Staff and Students (Defaulting to 1 for EEP)
for table in ["staff", "students"]:
    try:
        db.execute(f"ALTER TABLE {table} ADD COLUMN program_id INTEGER DEFAULT 1")
        print(f"✅ Added program_id to '{table}' table.")
    except sqlite3.OperationalError:
        print(f"⚠️ '{table}' table already has program_id.")

conn.commit()
conn.close()
print("🎉 UPGRADE COMPLETE! Your database is now Enterprise-ready.")