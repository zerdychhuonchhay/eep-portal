import sqlite3
import os

def upgrade_tasks_table():
    db_path = "eep.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Could not find '{db_path}'.")
        return

    print(f"🔌 Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Upgrading 'tasks' table for v2.7...")
    
    try:
        # Attempt to add the missing is_team_task column
        cursor.execute("ALTER TABLE tasks ADD COLUMN is_team_task INTEGER DEFAULT 0;")
        print("  [+] Successfully added column: is_team_task")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("  [✓] Column 'is_team_task' already exists.")
        else:
            print(f"  [!] Error: {e}")

    conn.commit()
    conn.close()
    print("\n✅ Calendar upgrade complete! You can now log holidays and team tasks.")

if __name__ == "__main__":
    upgrade_tasks_table()