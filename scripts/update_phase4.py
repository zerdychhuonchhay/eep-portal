import sqlite3

print("\n🤖 Initiating Path A: The Household Automator (Last Name Only)...")

# 1. Connect to the vault
conn = sqlite3.connect("eep.db")
conn.row_factory = sqlite3.Row
db = conn.cursor()

# Find all students who don't have a household yet
db.execute("""
    SELECT id, first_name, last_name, guardian_name, phone_number, slum_area 
    FROM students 
    WHERE household_id IS NULL 
""")
unlinked_students = db.fetchall()

if not unlinked_students:
    print("🤷 No unlinked students found. Everyone is already in a household!")
else:
    print(f"🔍 Found {len(unlinked_students)} students to process.")
    
    families = {}
    household_data = {}
    
    # Group siblings by Guardian Name OR strictly by Last Name
    for student in unlinked_students:
        last_name = student['last_name'].strip() if student['last_name'] else "Unknown"
        g_name = student['guardian_name'].strip() if student['guardian_name'] else ""
        phone = student['phone_number'].strip() if student['phone_number'] else ""
        slum = student['slum_area'].strip() if student['slum_area'] else ""
        
        # SMART GROUPING LOGIC (Removed Slum Area Requirement)
        if g_name:
            # If we have a guardian, group by guardian + phone
            family_key = f"GUARDIAN_{g_name}_{phone}"
            hh_name = g_name
        else:
            # If no guardian, group PURELY by last name
            family_key = f"LASTNAME_{last_name}"
            hh_name = f"The {last_name} Family"
            
        if family_key not in families:
            families[family_key] = []
            household_data[family_key] = {
                "guardian_name": hh_name,
                "phone": phone,
                "slum": slum # Will just save the first slum area it finds for the family
            }
            
        families[family_key].append(student['id'])
        
    print(f"👨‍👩‍👧‍👦 Identified {len(families)} unique households from those students.")
    
    households_created = 0
    students_linked = 0
    
    # Build the households and link the kids
    for key, student_ids in families.items():
        data = household_data[key]
        
        # Create the household record
        db.execute("""
            INSERT INTO households (guardian_name, phone_number, slum_area)
            VALUES (?, ?, ?)
        """, (data['guardian_name'], data['phone'], data['slum']))
        
        new_household_id = db.lastrowid
        households_created += 1
        
        # Link all matching siblings to this new household
        for sid in student_ids:
            db.execute("UPDATE students SET household_id = ? WHERE id = ?", (new_household_id, sid))
            students_linked += 1
            
    print(f"✅ SUCCESS! Created {households_created} new households and linked {students_linked} students.")

# Lock the vault
conn.commit()
conn.close()

print("\n🎉 UPGRADE COMPLETE! Your database is fully automated and ready for Phase 4.")