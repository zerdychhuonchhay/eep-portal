import sqlite3
import os

def upgrade_staff_table():
    db_path = "eep.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Error: Could not find '{db_path}'.")
        return

    print(f"🔌 Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("🚀 Upgrading 'staff' table for profiles...")
    
    try:
        cursor.execute("ALTER TABLE staff ADD COLUMN profile_picture TEXT;")
        print("  [+] Successfully added column: profile_picture")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("  [✓] Column 'profile_picture' already exists.")
        else:
            print(f"  [!] Error: {e}")

    conn.commit()
    conn.close()
    print("\n✅ Staff table upgraded! Users can now upload profile pictures.")

if __name__ == "__main__":
    upgrade_staff_table()