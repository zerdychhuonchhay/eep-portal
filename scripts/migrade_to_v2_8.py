import sqlite3
import os

def migrate_database():
    db_path = "eep.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Could not find '{db_path}'. Please ensure the script is in the same folder as your database.")
        return

    print(f"🔌 Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Define the new columns for the tasks table as per schema v2.8
    # Format: (Column Name, Data Type)
    new_task_columns = [
        ("is_team_task", "INTEGER DEFAULT 0"),
        ("end_date", "DATETIME"),
        ("is_holiday", "INTEGER DEFAULT 0")
    ]

    print("🚀 Auditing 'tasks' table for v2.8 requirements...")
    
    # Get existing columns to avoid "duplicate column" errors
    cursor.execute("PRAGMA table_info(tasks)")
    existing_columns = [info[1] for info in cursor.fetchall()]

    updates_made = 0

    for col_name, col_type in new_task_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE tasks ADD COLUMN {col_name} {col_type};")
                print(f"  [+] Added column: {col_name}")
                updates_made += 1
            except sqlite3.OperationalError as e:
                print(f"  [!] Error adding {col_name}: {e}")
        else:
            print(f"  [✓] Column '{col_name}' already exists.")

    if updates_made > 0:
        conn.commit()
        print(f"\n✅ Migration successful! {updates_made} new columns added.")
    else:
        print("\n✅ No changes needed. Your database is already up to date with schema v2.8.")

    conn.close()

if __name__ == "__main__":
    migrate_database()