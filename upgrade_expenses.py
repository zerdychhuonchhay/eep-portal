import sqlite3

print("💰 Initiating Financial Ledger Database Upgrade...")

# 1. Connect to the vault
conn = sqlite3.connect("eep.db")
db = conn.cursor()

# 2. Create the missing student_expenses table safely
try:
    db.execute("""
        CREATE TABLE IF NOT EXISTS student_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            vendor_name TEXT,
            expense_date DATE DEFAULT CURRENT_DATE,
            receipt_image TEXT,
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)
    print("✅ SUCCESS: The 'student_expenses' table has been created!")
except Exception as e:
    print(f"❌ ERROR: Something went wrong: {e}")

# 3. Lock the vault
conn.commit()
conn.close()

print("🎉 UPGRADE COMPLETE! You can now start your Flask server without any crashes.")