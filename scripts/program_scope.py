import sqlite3

print("🔐 Upgrading Staff Permissions Matrix...")

conn = sqlite3.connect("eep.db")
db = conn.cursor()

try:
    # Add the new column
    db.execute("ALTER TABLE staff ADD COLUMN program_scope TEXT DEFAULT 'EEP'")
    print("✅ Added 'program_scope' column to staff table.")
    
    # Upgrade existing Admins to Global access automatically
    db.execute("UPDATE staff SET program_scope = 'Global' WHERE role IN ('Admin', 'Director')")
    print("✅ Upgraded existing Admins to Global Scope.")
    
except sqlite3.OperationalError:
    print("⚠️ Column 'program_scope' already exists. No structural changes made.")

conn.commit()
conn.close()
print("🎉 DB UPGRADE COMPLETE! Your Vault is ready for granular permissions.")