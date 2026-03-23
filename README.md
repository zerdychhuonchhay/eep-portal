# 🎓 EEP Management PortalVideo Demo

$$Insert your YouTube Link Here$$

## Overview & The Problem

The EEP (Education Empowerment Program) Management Portal is a comprehensive, full-stack internal web application designed specifically for a non-governmental organization (NGO) operating in Phnom Penh, Cambodia.

Before the creation of this application, the NGO's social work and education tracking was crippled by "Excel Chaos." Staff members relied on a decentralized, fragile system of massive spreadsheets, physical paper report cards, and scattered desktop folders to track the progress of over 50 vulnerable students. This archaic system resulted in frequent data loss, severe bottlenecks when generating monthly impact reports for donors, and hours of manual, repetitive labor calculating GPAs and tracking attendance.

The EEP Portal completely eliminates this friction. It centralizes student demographics, academic performance, case management, and digital file storage into a single, secure, and intuitive web interface. It allows social workers to spend less time fighting with spreadsheets and more time serving the community.

## Core Features & Architecture

The application is built using **Python** and **Flask** on the backend, supported by a relational **SQLite3** database. The frontend utilizes **HTML5**, **Bootstrap 5** for responsive layout, **Jinja** for templating, and vanilla **JavaScript** for client-side interactivity.

### 1. Centralized Roster & Smart Profiles

The app replaces standard spreadsheets with a secure, searchable database. Each student has a dedicated profile acting as a "Single Source of Truth."

* **Resilient Avatar System:** Uses a custom JavaScript integration with the UI-Avatars API to generate initials-based profile pictures dynamically if a student lacks an uploaded photo.

* **Printable Dossiers:** Custom CSS `@media print` rules strip away the web UI (navbars, buttons) and force hidden accordions open, allowing social workers to generate clean, physical case files with a single click.

### 2. The Academic Engine (Split-Pane Data Entry)

The most significant bottleneck for the NGO was transcribing physical report cards.

* **Split-Pane UI:** I designed a custom interface where the user uploads a photo of the physical report card. The image renders dynamically on the left half of the screen using JavaScript `URL.createObjectURL`, while the data entry form sits perfectly alongside it on the right.

* **Hover-to-Zoom Engine:** A custom vanilla JavaScript script tracks mouse coordinates and allows the user to hover over the scanned image to magnify it by 2.5x, making it easy to read blurry handwriting.

* **Automated Badging:** The Python backend calculates the overall GPA automatically but allows for "Smart Overrides". Grades are rendered using a custom Jinja filter (`@app.template_filter('get_badge')`) that color-codes scores based on NGO standards.

### 3. Case Management & Executive Tracking

* **Tabbed Risk Assessments:** The portal digitizes a complex 5-page risk assessment into a clean, tabbed HTML form.

* **Audit Trail Security:** A silent backend helper (`log_action()`) records the User-Agent (Device) and timestamp of every action (edits, deletions, uploads). Non-admin staff are physically blocked from deleting data, ensuring total accountability.

## Comprehensive Files Overview

* `app.py`: The core engine of the application (\~1,000 lines). Handles all routing, form validation, impact calculations, and DB executions.

* `eep.db`: The relational SQLite database containing 7 interconnected tables linked via foreign keys.

* `helpers.py`: Contains the `@login_required` decorator function to secure routes.

* `templates/`: Contains all HTML Jinja templates (Dashboard, Profiles, Modals, Forms).

* `static/uploads/`: The secure directories holding physical document scans and photos.

## 🤔 Design Decisions (The "Why")

1. **Why SQLite instead of PostgreSQL?**
   Chosen for extreme portability. Small NGOs often lack IT departments. Using SQLite means the entire database is a single file (`eep.db`) that can be easily backed up without configuring external servers.

2. **Raw SQL (`cs50.SQL`) vs. an ORM:**
   A deliberate educational choice to solidify my understanding of relational database architecture, complex `LEFT JOIN` statements, and SQL aggregate functions (`SUM`, `COUNT`).

3. **Vanilla JavaScript over React/Vue:**
   To keep the application lightweight and avoid complex build steps (like Node.js dependencies), I used Vanilla JS. Features like the "Hover-to-Zoom" and dynamic select filtering proved modern Vanilla JS is highly capable.

## Local Setup & Installation

To run this application safely on a new local machine without creating package conflicts, it is highly recommended to use a Python Virtual Environment (`venv`).

1. **Clone the repository:**

   ```bash
   git clone [https://github.com/zerdychhuonchhay/eep-portal.git](https://github.com/zerdychhuonchhay/eep-portal.git)
   cd eep-portal
   ```

2. **Create and Activate a Virtual Environment (`venv`):**
   This isolates the project's dependencies from your global Python environment.

   *On Windows (Command Prompt):*

   ```cmd
   python -m venv venv
   venv\Scripts\activate
   ```

   *On Windows (PowerShell):*
   (Note: If PowerShell gives you a red error saying scripts are disabled, run the first line to fix it!)

   ```powershell
   Set-ExecutionPolicy Unrestricted -Scope CurrentUser
   python -m venv venv
   .\venv\Scripts\activate
   ```

   *On macOS / Linux (Ubuntu, Debian, etc.):*

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

   *(Linux Tip: If it says 'venv not found', you may need to run `sudo apt install python3-venv` first).*

3. **Install Required Libraries:**
   Once the virtual environment is active (you will see `(venv)` in your terminal prompt), install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   *(If `requirements.txt` is missing, run: `pip install Flask cs50 Werkzeug pandas`)*

4. **Start the Application:**

   ```bash
   flask run
   ```

5. **Access the Portal:**
   Open your browser and navigate to `http://127.0.0.1:5000`.

## 🔄 The Deployment Pipeline (Git Flow)

This project uses a professional "Code vs. State" deployment pipeline connecting a local VS Code environment to a live PythonAnywhere production server via GitHub.

**⚠️ THE GOLDEN RULE OF THIS REPO:** The SQLite database (`eep.db`) and user-uploaded files (`static/uploads/`) are considered **State Data**. They live *exclusively* on the live server and are strictly ignored by `.gitignore`. **Never commit local databases to GitHub to prevent overwriting live NGO data.**

**The Standard Developer Workflow:**

1. **Build Locally:** Write and test new code on your local laptop using VS Code (`flask run`).

2. **Push Code:** Once a feature works perfectly, send it to the GitHub vault:

   ```bash
   git add .
   git commit -m "Brief description of the new feature or fix"
   git push
   ```

3. **Pull to Production:** Open the PythonAnywhere Bash Console and pull the new code down to the live server:

   ```bash
   git pull
   ```

4. **Reload:** Click the green "Reload" button on the PythonAnywhere Web Dashboard to immediately make the updates live for the NGO staff.

## 🤖 AI Integration & Academic Honesty

In accordance with CS50's academic honesty guidelines for the Final Project, I utilized AI tools (specifically Google Gemini) as an assistant during development.

The core data architecture, application logic, database schema, and project management strategy remain my own original work. Gemini was used primarily as an advanced autocomplete and styling tool to accelerate development. Specifically, AI was used to:

* Generate boilerplate HTML and complex Bootstrap 5 CSS layouts.

* Refine custom vanilla JavaScript logic, specifically for the "Hover-to-Zoom" image preview feature.

* Assist in debugging syntax errors within complex SQL statements.

Citation comments have been included at the top of relevant files to clearly demarcate where AI assistance was utilized.$$
