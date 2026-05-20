import sqlite3
import os

def upgrade_database():
    db_path = "eep.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Could not find '{db_path}'. Please ensure the script is in the same folder as your database.")
        return

    print(f"🔌 Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Upgrading Database for v2.9 (Academic & Official Reports)...")

    # ---------------------------------------------------------
    # 1. CREATE NEW TABLE FOR OFFICIAL REPORT BUILDER
    # ---------------------------------------------------------
    print("\n📦 Checking 'program_reports' table...")
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS program_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            program_id INTEGER DEFAULT 1,
            month TEXT NOT NULL,
            year TEXT NOT NULL,
            achievements TEXT,
            goals TEXT,
            challenges TEXT
        )
        """)
        print("  [+] Verified/Created table: program_reports")
    except Exception as e:
        print(f"  [!] Error creating program_reports: {e}")

    # ---------------------------------------------------------
    # 2. UPGRADE ACADEMIC REPORTS FOR FAST MATH QUERIES
    # ---------------------------------------------------------
    print("\n📊 Checking 'monthly_reports' table for Academic Review metrics...")
    academic_columns = [
        ("total_score", "REAL"),
        ("overall_average", "REAL"),
        ("overall_grade", "TEXT"),
        ("flexible_rank", "TEXT")
    ]

    for col_name, col_type in academic_columns:
        try:
            cursor.execute(f"ALTER TABLE monthly_reports ADD COLUMN {col_name} {col_type};")
            print(f"  [+] Added column to monthly_reports: {col_name} ({col_type})")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"  [✓] Skipped: Column '{col_name}' already exists.")
            else:
                print(f"  [!] Error adding {col_name}: {e}")

    # Save changes and close the connection
    conn.commit()
    conn.close()
    print("\n✅ Database upgrade complete! Your new UI tools will now work perfectly.")

if __name__ == "__main__":
    upgrade_database()