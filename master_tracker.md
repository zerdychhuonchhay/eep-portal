# 📋 ELM Enterprise Portal: Master Tracker (Version 4.8)

*Architecture: Python, Flask, raw SQLite3, HTML/Bootstrap/Tailwind, Vanilla JS.*
*Scope: Multi-Program NGO Management System*

## 🏗️ PHASE 1: The Vault & Security (COMPLETED)
*Goal: Set up the database, authentication, and security protocols.*
* [x] **Project Setup:** `app.py`, `helpers.py`, and the `uploads` folders created.
* [x] **Core Schema:** Tables built.
* [x] **Authentication:** Secure Login and Registration forms with password hashing.
* [x] **Role-Based Access Control (RBAC):** Built `@admin_required` to protect delete routes.
* [x] **The Audit Trail:** Created the `log_action()` helper and `audit_logs` table.

## 🚦 PHASE 2: Core UI & Roster Management (COMPLETED)
*Goal: Build the interfaces so staff can interact with the database.*
* [x] **The Layout:** Responsive `layout.html` with dual-font support.
* [x] **Impact Dashboard:** Executive view (`/dashboard`) showing stats.
* [x] **The Roster:** Main `index.html` featuring DataTables search.
* [x] **Student Profiles:** Massive `/student/<id>` view.
* [x] **Digital Filing Cabinet:** Secure file uploads.

## 📝 PHASE 3: Academic & Assessment Engine (COMPLETED)
*Goal: Replace the messy Excel sheets and paper forms.*
* [x] **Smart Grade Entry:** The split-pane `/add_report` form with hover-to-zoom image preview.
* [x] **Subject Filtering:** JavaScript logic hiding/showing subjects.
* [x] **The Math Engine:** Automated GPA calculation (`calculate_gpa`).
* [x] **Social Work Follow-Ups:** Tabbed risk assessment interface.
* [x] **Bulk Actions:** The `/bulk_followup` route for multiple siblings.
* [x] **Export Tools:** CSV "Escape Hatches".

## 👨‍👩‍👧‍👦 PHASE 4: The Household Engine & UI Polish (COMPLETED)
*Goal: Sync parents and siblings so staff never have to type duplicate family data.*
* [x] **Database Architecture:** Created `households` table and updated `students`.
* [x] **Foreign Key Link:** Linked children to a centralized household ID.
* [x] **Household UI:** Built the "Household Profile" showing all siblings.
* [x] **Smart Profile Updates:** `<datalist>` auto-completes and synced parent data.
* [x] **Accessibility (A11y) Polish:** Two-column mobile-ready layout.

## 🏢 PHASE 5: Multi-Program Architecture & Enterprise Admin (COMPLETED)
*Goal: Transform the app from a single "EEP" tool into the Master NGO Portal for all programs.*
* [x] **Database Architecture:** Added `program_id` & `program_scope` to `staff` and `students`.
* [x] **The Context Switcher:** Built the dynamic dropdown in the Navbar to switch hats.
* [x] **Scoped Queries:** Updated routes to act as "Traffic Cops" pointing to different templates.
* [x] **Staff Manager UI:** Built `/manage_staff` for Admins to assign roles and reset passwords.
* [x] **User Security Fix:** Built `/change_password` for secure user password updates.

---

## 📍 WE ARE HERE: CHOOSE YOUR NEXT TARGET

### 🇰🇭 PHASE 6: The Localization Engine (Khmer Translation)
*Goal: Make the entire application accessible for non-English speaking Khmer staff.*
* [ ] **Language Toggle UI:** Add a language switcher `[ 🇰🇭 KH | 🇺🇸 EN ]` in the layout navbar.
* [ ] **The Translation Dictionary:** Create a `translations.json` file for English-to-Khmer mappings.
* [ ] **Jinja Injection:** Replace hardcoded HTML text with a custom Jinja helper.

### 🏛️ PHASE 8: HR & Compliance Module
*Goal: Automate your Government Affairs tracking so you never miss a Ministry deadline.*
* [ ] **Database Architecture:** Create a `compliance_deadlines` table for Govt reports, visas, etc.
* [ ] **The HR Tracker:** Update `hr_roster.html` to pull real contract renewal and hire dates.
* [ ] **Compliance Dashboard:** Connect `dashboard_global.html` to live deadline data to trigger warnings.

### 📅 PHASE 7: Task Management & Calendar
*Goal: Stop forgetting when a student needs a follow-up or a document is due.*
* [ ] **Database Architecture:** Create a `tasks` table.
* [ ] **The Calendar UI:** Integrate `FullCalendar.js` into a dedicated `/calendar` route.

---

## 🚀 FUTURE HORIZONS (The Backlog)

### 🖨️ PHASE 9: The Automation Engine (Bulk Print & Donor Reports)
* [ ] **Pre-Filled Form Generator:** Build `/batch_print` to generate physical forms.
* [ ] **Automated Donor Reports:** Instantly generate PDFs for sponsors.
* [ ] **Smart CSV Import Wizard:** Bulk update existing records.

### 🏥 PHASE 10: Health, Growth & Asset Tracking
* [ ] **BMI & Growth Charts:** Add height/weight tracking using `Chart.js`.
* [ ] **Asset Ledger:** Create an `assets` table to track bicycles, laptops, etc.

### 🎓 PHASE 11: University, Career & Alumni Engine
* [ ] **Database Architecture:** Create `universities`, `career_plans`, and `alumni_status` tables.
* [ ] **Alumni Tracking:** Track graduated students' current employment and salary.

### 💰 PHASE 12: The NGO Ledger (Financial Tracking)
* [ ] **Database Update:** Create the `student_expenses` table.
* [ ] **Budget Burn-Rate Visuals:** Add financial charts to the Executive Dashboard.

### 📱 PHASE 13: The Native Mobile Experience (PWA)
* [ ] **Progressive Web App (PWA):** Create a `manifest.json` and Service Worker.
* [ ] **Offline Mode Sync:** Cache forms for areas with 0% 4G coverage.

### 🌟 PHASE 14: External Portals & AI (The SaaS Level)
* [ ] **Secure Sponsor Portal:** Generate secure, expiring "Magic Links" for sponsors.
* [ ] **AI Document Translation:** Integrate OpenAI API to auto-translate Khmer case notes.