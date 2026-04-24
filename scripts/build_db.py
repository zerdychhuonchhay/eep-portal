import sqlite3

print("👷 Building the EEP Database...")

# 1. Connect to the vault (this automatically creates eep.db!)
conn = sqlite3.connect("eep.db")

# 2. Open the schema.sql file and read the blueprint
with open("schema.sql", "r", encoding="utf-8") as file:
    blueprint = file.read()

# 3. Execute the entire blueprint at once
conn.executescript(blueprint)

# 4. Lock the vault
conn.commit()
conn.close()

print("✅ SUCCESS! The eep.db vault has been created with all 11 tables.")