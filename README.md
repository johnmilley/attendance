# Attendance

Simple Flask app for tracking student attendance in classes. Students are organized by cohort, assigned to classes, and marked present/absent with a single click.

## Setup

```bash
git clone https://github.com/johnmilley/attendance.git
cd attendance
pip install -r requirements.txt
flask init-db
flask run
```

Then open http://127.0.0.1:5000.

## Usage

1. Go to **Manage** — create a cohort (e.g. SD2025), add classes under it
2. Paste a student list (`Last, First` per line) and import
3. Go to **Home** — click a class to take attendance
4. Check/uncheck students — changes save instantly
5. Click **Report** to see attendance percentages per student
