🎓 EEP Management Portal

Video Demo:

$$Insert your YouTube Link Here$$

🌍 Overview & The Problem

The EEP (Education Empowerment Program) Management Portal is a comprehensive, full-stack internal web application designed specifically for a non-governmental organization (NGO) operating in Phnom Penh, Cambodia.

Before the creation of this application, the NGO's social work and education tracking was crippled by "Excel Chaos." Staff members relied on a decentralized, fragile system of massive spreadsheets, physical paper report cards, and scattered desktop folders to track the progress of over 50 vulnerable students. This archaic system resulted in frequent data loss, severe bottlenecks when generating monthly impact reports for donors, and hours of manual, repetitive labor calculating GPAs and tracking attendance.

The EEP Portal completely eliminates this friction. It centralizes student demographics, academic performance, case management, and digital file storage into a single, secure, and intuitive web interface. It allows social workers to spend less time fighting with spreadsheets and more time serving the community.

🏗️ Core Features & Architecture

The application is built using Python and Flask on the backend, supported by a relational SQLite3 database. The frontend utilizes HTML5, Bootstrap 5 for responsive layout, Jinja for templating, and vanilla JavaScript for client-side interactivity.

1. Centralized Roster & Smart Profiles

The app replaces standard spreadsheets with a secure, searchable database. Each student has a dedicated profile acting as a "Single Source of Truth."

Resilient Avatar System: Uses a custom JavaScript integration with the UI-Avatars API to generate initials-based profile pictures dynamically if a student lacks an uploaded photo. It includes a "Facebook-style" asynchronous loading spinner for smooth photo updates.

Printable Dossiers: Custom CSS @media print rules strip away the web UI (navbars, buttons) and force hidden accordions open, allowing social workers to generate clean, physical case files with a single click.

2. The Academic Engine (Split-Pane Data Entry)

The most significant bottleneck for the NGO was transcribing physical report cards.

Split-Pane UI: I designed a custom interface where the user uploads a photo of the physical report card. The image renders dynamically on the left half of the screen using JavaScript URL.createObjectURL, while the data entry form sits perfectly alongside it on the right.

Hover-to-Zoom Engine: A custom vanilla JavaScript script tracks mouse coordinates and allows the user to hover over the scanned image to magnify it by 2.5x, making it easy to read blurry handwriting without leaving the page.

Automated Badging: The Python backend calculates the overall GPA automatically but allows for "Smart Overrides" for non-standard grading. Grades are rendered on the profile using a custom Jinja filter (@app.template_filter('get_badge')) that color-codes scores based on NGO standards.

3. Case Management & Priority Alerts

Social workers conduct monthly home visits to assess physical health, living conditions, and child protection risks.

The portal digitizes a complex 5-page risk assessment into a clean, tabbed HTML form.

Priority Alerts: If a social worker flags a "Child Protection Concern", the backend instantly pushes this student to the top of the Executive Dashboard in a red priority queue, requiring managerial review and resolution.

📁 Comprehensive Files Overview

The project is modularized to maintain clean code and separate the backend logic from the frontend presentation.

app.py: The core engine of the application. It contains roughly 1,000 lines of Python code divided into modular "Neighborhoods" (Setup, Dashboard, Profiles, Academic Logic, File CRUD). It handles all routing, form validation, and database executions.

eep.db: The relational SQLite database. It contains 6 interconnected tables: staff, students, monthly_reports, grades, followups, and documents, all linked via foreign key relationships (Student IDs).

helpers.py: Contains the @login_required decorator function to secure routes and manage session states, ensuring unauthorized users cannot access sensitive child data.

templates/layout.html: The master Jinja template containing the Bootstrap CDN, DataTables integration, and the dynamic Navigation Bar that changes based on user session state.

templates/index.html: The Roster Dashboard. It utilizes DataTables.js to provide instant sorting, pagination, and searching across the entire student body.

templates/student_profile.html: The most complex view in the app. It aggregates data from 4 different SQL tables to build a unified dossier, featuring expanding accordions for academic history and social work follow-ups.

templates/add_report.html & edit_report.html: The split-pane grading interfaces featuring the custom JavaScript image-zoom logic.

templates/add_followup.html & edit_followup.html: The 5-tab Bootstrap forms used by social workers to input detailed monthly home-visit data and risk assessments.

templates/executive_dashboard.html: The high-level KPI view for the NGO Director.

templates/register.html & login.html: The authentication forms that securely pass user credentials to app.py for hashing via Werkzeug.

static/uploads/: The secure, local storage directories configured in app.py to hold physical document scans and profile pictures.

🤔 Design Decisions (The "Why")

Building this application required several deliberate architectural choices to ensure it was actually usable by a small NGO.

Why SQLite instead of PostgreSQL?
While PostgreSQL is the industry standard for enterprise, SQLite was chosen specifically for its extreme portability. Small NGOs often lack dedicated IT departments or DevOps engineers. Using SQLite means the entire database is a single file (eep.db) that can be easily backed up, copied, and deployed without configuring a massive external database server.

Raw SQL (cs50.SQL) vs. an ORM (SQLAlchemy):
I opted to use raw SQL queries rather than an Object-Relational Mapper. This was a deliberate educational choice to solidify my understanding of relational database architecture, complex JOIN statements, and SQL aggregate functions (SUM, COUNT) which power the Executive Dashboard.

Bootstrap 5 over Custom CSS / Tailwind:
Time and responsive reliability were paramount. Social workers often access this data in the field via tablets and smartphones. Bootstrap 5 allowed me to build a highly professional, trustworthy, and inherently mobile-responsive UI instantly, allowing me to focus my engineering time on complex backend logic rather than writing media queries from scratch.

Vanilla JavaScript over React/Vue:
To keep the application lightweight and avoid complex build steps (like Webpack or Node.js dependencies), I used Vanilla JS to manipulate the Document Object Model (DOM). Features like the "Hover-to-Zoom" image viewer and the "Facebook-style" async loading spinners proved that modern Vanilla JS is more than powerful enough to create a highly interactive UI within standard Jinja templates.

Collision Protection Strategy:
To handle the Digital Filing Cabinet, I anticipated that multiple students might upload a file named birth_certificate.pdf. To prevent data overwriting, the Flask backend utilizes secure_filename and appends Unix timestamps (int(time.time())) to dynamically alter the saved filename on the server while displaying the original, clean filename to the user on the frontend.

🤖 AI Integration & Academic Honesty

In accordance with CS50's academic honesty guidelines for the Final Project, I utilized AI tools (specifically Google Gemini) as an assistant during development.

The core data architecture, application logic, database schema, and project management strategy remain my own original work. Gemini was used primarily as an advanced autocomplete and styling tool to accelerate development. Specifically, AI was used to:

Generate boilerplate HTML and complex Bootstrap 5 CSS layouts (e.g., the responsive grid for the Executive Dashboard).

Refine custom vanilla JavaScript logic, specifically for the "Hover-to-Zoom" image preview feature and the dynamic form filtering based on student grade levels.

Assist in debugging syntax errors within complex SQL JOIN statements and Flask routing logic.

Citation comments have also been included at the top of relevant files (such as app.py and edit_report.html) to clearly demarcate where AI assistance was utilized for specific functions.

🚀 How to Run

Ensure Python 3 is installed.

Install the required libraries: pip install Flask CS50 Werkzeug

Start the application: flask run

Access via the provided localhost URL. You must register an account to view the roster.
