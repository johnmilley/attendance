import os
import sqlite3
from datetime import date

from flask import Flask, g, redirect, render_template, request, url_for

app = Flask(__name__)
app.config["DATABASE"] = os.path.join(app.instance_path, "attendance.db")

os.makedirs(app.instance_path, exist_ok=True)


# ── Database helpers ──────────────────────────────────────────────


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.cli.command("init-db")
def init_db():
    """Create the database tables."""
    db = get_db()
    with app.open_resource("schema.sql") as f:
        db.executescript(f.read().decode())
    print("Database initialized.")


# ── Routes ────────────────────────────────────────────────────────


@app.route("/")
def index():
    db = get_db()
    cohorts = db.execute("SELECT * FROM cohorts ORDER BY name").fetchall()
    classes_by_cohort = {}
    for cohort in cohorts:
        classes_by_cohort[cohort["id"]] = db.execute(
            "SELECT * FROM classes WHERE cohort_id = ? ORDER BY name",
            (cohort["id"],),
        ).fetchall()
    return render_template(
        "index.html", cohorts=cohorts, classes_by_cohort=classes_by_cohort
    )


# ── Attendance ────────────────────────────────────────────────────


@app.route("/attendance/<int:class_id>")
def attendance(class_id):
    db = get_db()
    cls = db.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if cls is None:
        return "Class not found", 404

    selected_date = request.args.get("date", date.today().isoformat())

    # Get students in this class's cohort
    students = db.execute(
        "SELECT * FROM students WHERE cohort_id = ? ORDER BY last_name, first_name",
        (cls["cohort_id"],),
    ).fetchall()

    # Ensure attendance rows exist for each student on this date
    for student in students:
        db.execute(
            "INSERT OR IGNORE INTO attendance (student_id, class_id, date, present) "
            "VALUES (?, ?, ?, 0)",
            (student["id"], class_id, selected_date),
        )
    db.commit()

    # Fetch attendance status
    attendance_rows = db.execute(
        "SELECT student_id, present FROM attendance "
        "WHERE class_id = ? AND date = ?",
        (class_id, selected_date),
    ).fetchall()
    present_map = {row["student_id"]: row["present"] for row in attendance_rows}

    # Dates that have attendance records for this class
    tracked_dates = db.execute(
        "SELECT DISTINCT date FROM attendance WHERE class_id = ? ORDER BY date DESC",
        (class_id,),
    ).fetchall()
    tracked_dates = [row["date"] for row in tracked_dates]

    return render_template(
        "attendance.html",
        cls=cls,
        students=students,
        present_map=present_map,
        selected_date=selected_date,
        tracked_dates=tracked_dates,
    )


@app.route("/attendance/<int:class_id>/delete-date", methods=["POST"])
def delete_date(class_id):
    db = get_db()
    target_date = request.form["date"]
    db.execute(
        "DELETE FROM attendance WHERE class_id = ? AND date = ?",
        (class_id, target_date),
    )
    db.commit()
    return redirect(url_for("attendance", class_id=class_id))


@app.route("/attendance/<int:class_id>/toggle", methods=["POST"])
def toggle_attendance(class_id):
    db = get_db()
    student_id = request.form["student_id"]
    selected_date = request.form["date"]
    present = int(request.form["present"])

    db.execute(
        "UPDATE attendance SET present = ? "
        "WHERE student_id = ? AND class_id = ? AND date = ?",
        (present, student_id, class_id, selected_date),
    )
    db.commit()

    # Return just the updated checkbox for HTMX swap
    checked = "checked" if present else ""
    return (
        f'<input type="checkbox" name="present" value="1" {checked} '
        f'hx-post="{url_for("toggle_attendance", class_id=class_id)}" '
        f'hx-vals=\'{{"student_id": "{student_id}", "date": "{selected_date}", '
        f'"present": "{1 - present}"}}\' '
        f'hx-swap="outerHTML">'
    )


# ── Management ────────────────────────────────────────────────────


@app.route("/manage")
def manage():
    db = get_db()
    cohorts = db.execute("SELECT * FROM cohorts ORDER BY name").fetchall()

    classes = db.execute(
        "SELECT classes.*, cohorts.name AS cohort_name "
        "FROM classes JOIN cohorts ON classes.cohort_id = cohorts.id "
        "ORDER BY cohorts.name, classes.name"
    ).fetchall()

    students = db.execute(
        "SELECT students.*, cohorts.name AS cohort_name "
        "FROM students JOIN cohorts ON students.cohort_id = cohorts.id "
        "ORDER BY cohorts.name, students.last_name, students.first_name"
    ).fetchall()

    return render_template(
        "manage.html", cohorts=cohorts, classes=classes, students=students
    )


@app.route("/manage/cohort", methods=["POST"])
def create_cohort():
    name = request.form["name"].strip()
    if name:
        db = get_db()
        db.execute("INSERT INTO cohorts (name) VALUES (?)", (name,))
        db.commit()
    return redirect(url_for("manage"))


@app.route("/manage/class", methods=["POST"])
def create_class():
    name = request.form["name"].strip()
    cohort_id = request.form["cohort_id"]
    if name and cohort_id:
        db = get_db()
        db.execute(
            "INSERT INTO classes (name, cohort_id) VALUES (?, ?)", (name, cohort_id)
        )
        db.commit()
    return redirect(url_for("manage"))


@app.route("/manage/students", methods=["POST"])
def import_students():
    cohort_id = request.form["cohort_id"]
    raw = request.form.get("students_text", "")

    # Handle file upload if provided
    file = request.files.get("students_file")
    if file and file.filename:
        raw = file.read().decode("utf-8")

    db = get_db()
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if "," in line:
            parts = line.split(",", 1)
            last_name = parts[0].strip()
            first_name = parts[1].strip() if len(parts) > 1 else ""
        else:
            last_name = line
            first_name = ""
        if last_name:
            db.execute(
                "INSERT INTO students (last_name, first_name, cohort_id) "
                "VALUES (?, ?, ?)",
                (last_name, first_name, cohort_id),
            )
    db.commit()
    return redirect(url_for("manage"))


@app.route("/manage/student/<int:student_id>/edit", methods=["POST"])
def edit_student(student_id):
    last_name = request.form["last_name"].strip()
    first_name = request.form["first_name"].strip()
    if last_name:
        db = get_db()
        db.execute(
            "UPDATE students SET last_name = ?, first_name = ? WHERE id = ?",
            (last_name, first_name, student_id),
        )
        db.commit()
    return redirect(url_for("manage"))


@app.route("/manage/student/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    db = get_db()
    db.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    db.execute("DELETE FROM students WHERE id = ?", (student_id,))
    db.commit()
    return redirect(url_for("manage"))


# ── Reports ───────────────────────────────────────────────────────


@app.route("/report/<int:class_id>")
def report(class_id):
    db = get_db()
    cls = db.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone()
    if cls is None:
        return "Class not found", 404

    students = db.execute(
        "SELECT * FROM students WHERE cohort_id = ? ORDER BY last_name, first_name",
        (cls["cohort_id"],),
    ).fetchall()

    # Total number of distinct dates attendance was taken for this class
    total_days = db.execute(
        "SELECT COUNT(DISTINCT date) FROM attendance WHERE class_id = ?",
        (class_id,),
    ).fetchone()[0]

    report_data = []
    for student in students:
        row = db.execute(
            "SELECT "
            "  SUM(present) AS days_present, "
            "  COUNT(*) AS days_recorded "
            "FROM attendance "
            "WHERE student_id = ? AND class_id = ?",
            (student["id"], class_id),
        ).fetchone()

        days_present = row["days_present"] or 0
        days_recorded = row["days_recorded"] or 0
        days_absent = days_recorded - days_present
        pct = round(days_present / days_recorded * 100) if days_recorded > 0 else 0

        # Get list of absent dates
        absent_dates = db.execute(
            "SELECT date FROM attendance "
            "WHERE student_id = ? AND class_id = ? AND present = 0 "
            "ORDER BY date",
            (student["id"], class_id),
        ).fetchall()

        report_data.append(
            {
                "student": student,
                "days_present": days_present,
                "days_absent": days_absent,
                "pct": pct,
                "absent_dates": [r["date"] for r in absent_dates],
            }
        )

    return render_template(
        "report.html", cls=cls, report_data=report_data, total_days=total_days
    )
