import sqlite3

def upgrade_database():
    conn = sqlite3.connect('eep.db')
    cursor = conn.cursor()

    print("Starting safe database migration...")

    # 1. Add program_id to existing tables if missing
    tables_to_upgrade = ['staff', 'students', 'tasks']
    for table in tables_to_upgrade:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN program_id INTEGER DEFAULT 1")
            print(f"Added program_id to {table}.")
        except sqlite3.OperationalError:
            print(f"Column program_id already exists in {table}.")

    # 2. Add granular CRUD permissions to role_permissions
    crud_columns = [
        "can_create_profiles", "can_update_profiles",
        "can_create_academics", "can_update_academics", "can_delete_academics",
        "can_create_followups", "can_update_followups",
        "can_create_files", "can_delete_files", "can_create_expenses"
    ]
    
    for col in crud_columns:
        try:
            cursor.execute(f"ALTER TABLE role_permissions ADD COLUMN {col} INTEGER DEFAULT 0")
            print(f"Added {col} to role_permissions.")
        except sqlite3.OperationalError:
            pass # Column already exists

    # 3. Migrate old coarse settings to new granular settings safely
    try:
        cursor.execute("UPDATE role_permissions SET can_create_profiles = can_edit_profiles, can_update_profiles = can_edit_profiles")
        cursor.execute("UPDATE role_permissions SET can_create_academics = can_manage_academics, can_update_academics = can_manage_academics")
        cursor.execute("UPDATE role_permissions SET can_create_followups = can_manage_followups, can_update_followups = can_manage_followups")
        cursor.execute("UPDATE role_permissions SET can_create_files = can_upload_files")
        # Give Admin full delete/expense powers
        cursor.execute("UPDATE role_permissions SET can_delete_academics = 1, can_delete_files = 1, can_create_expenses = 1 WHERE role = 'Admin'")
        print("Migrated old permissions to new CRUD format.")
    except Exception as e:
        print(f"Migration step skipped or failed: {e}")

    conn.commit()
    conn.close()
    print("Migration complete! Your data is safe.")

if __name__ == "__main__":
    upgrade_database()