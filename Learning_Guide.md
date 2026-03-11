🧠 EEP Portal: CS50 Final Project Learning Guide

This document is your personal cheat sheet. It breaks down the most complex logic in the EEP Portal. Review this before recording your 3-minute demo video so you can speak about your code like a true software engineer!

1. The Database Architecture (Relational SQL)

Your app doesn't just use one massive Excel sheet; it uses a Relational Database.

Foreign Keys (student_id): This is the glue of your application. The students table is the "parent." The grades, documents, and followups tables are "children." They all have a student_id column. When you load a profile, Python says: "Go into the Grades table and only bring me the rows where student_id equals 5."

The Wildcard Query (LEFT JOIN & COALESCE):
In app.py, you have a very advanced SQL query in the /academics route:

SELECT g.report_id, COALESCE(s.name, g.custom_subject_name) as subject_name
FROM grades g LEFT JOIN subjects s ON g.subject_id = s.id


Why a LEFT JOIN? A normal JOIN only returns a row if it exists in BOTH tables. Because your custom "Wildcard" subjects (like "April Field Trip") don't exist in the master subjects table, a normal JOIN would delete them! A LEFT JOIN says: "Give me ALL the grades, even if the subject isn't in the master list."

What is COALESCE? It's a fallback mechanism. It says: "Try to use the official Master Subject name (s.name). If that is empty (NULL), fall back to the Custom Subject name (g.custom_subject_name)."

2. The Python Backend (Flask & Werkzeug)

Routing & Methods (GET vs. POST):
Every route (like @app.route("/add_report")) handles traffic.

GET: The user just typed the URL or clicked a link. They want to look at the blank form.

POST: The user clicked the "Submit" button. They are sending a package of data to the server to be processed and saved.

Data Handoff (request.form.get):
How does Python know what the user typed? It uses request.form.get("first_name"). The string inside the quotes must exactly match the name="first_name" attribute in your HTML file.

File Upload Safety (secure_filename):
When users upload a report card scan, you run it through secure_filename(file.filename) and append a time.time() timestamp to it.

Why? First, it prevents hackers from uploading files named ../../../system32/virus.exe. Second, if two different students upload a file called report.pdf, the timestamp ensures the second file doesn't overwrite the first file on your computer's hard drive!

3. The Frontend Bridge (Jinja2)

Jinja is what allows you to inject Python variables directly into your HTML files.

Dynamic Rendering ({% for %} loops):
When you pass students=students to your index.html, Jinja uses {% for student in students %} to create a new table row <tr> for every single person in your database automatically.

Smart Badging ({% if %} statements):
You use Jinja logic to calculate color codes on the fly. For example:
{% if record.overall_average >= 85 %}bg-success{% else %}bg-danger{% endif %}
This is what makes the grade badges turn green, yellow, or red without you having to manually color them.

4. Client-Side Interactivity (Vanilla JavaScript)

You used plain JavaScript directly in the browser to make the app feel fast and modern without relying on heavy frameworks like React.

Live Image Previews (URL.createObjectURL):
When a user selects a file from their computer, the image immediately appears on the screen before they even click "Submit." The JS creates a temporary, fake URL for the file sitting on their hard drive so the browser can display it instantly.

The Smart Subject Filter (filterSubjects()):
In add_report.html, you wrote a JS function that listens for a change in the "Grade Level" dropdown. It grabs all the subject rows (document.querySelectorAll('.subject-row')) and looks at their data-category. If the student is in Kindergarten, the JS uses row.style.display = 'none' to instantly hide all the High School and University subjects, keeping the form clean and simple!
