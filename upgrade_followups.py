import sqlite3
import os

def upgrade_database():
    db_path = "eep.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Could not find '{db_path}' in the current directory.")
        return

    print(f"🔌 Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # The list of new columns required for the Risk Assessment & Monthly Followup UI
    new_columns = [
        ("parent_working_notes", "TEXT"),
        ("support_level", "INTEGER"),
        ("church_attendance", "TEXT"),
        ("child_jobs", "TEXT"),
        ("risk_level", "INTEGER"),
        ("student_story", "TEXT")
    ]

    print("🚀 Upgrading 'followups' table...")
    
    for col_name, col_type in new_columns:
        try:
            # Attempt to add the column
            cursor.execute(f"ALTER TABLE followups ADD COLUMN {col_name} {col_type};")
            print(f"  [+] Successfully added column: {col_name} ({col_type})")
        except sqlite3.OperationalError as e:
            # SQLite throws an OperationalError if the column already exists
            if "duplicate column name" in str(e).lower():
                print(f"  [✓] Skipped: Column '{col_name}' already exists.")
            else:
                print(f"  [!] Error adding '{col_name}': {e}")

    # Save changes and close the connection
    conn.commit()
    conn.close()
    print("\n✅ Database upgrade complete! You can now safely run the app.")

if __name__ == "__main__":
    upgrade_database()