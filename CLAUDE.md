# Attendance App

Flask + SQLite attendance tracker. No ORM — uses raw `sqlite3` queries.

## Quick Start

```bash
pip install -r requirements.txt
flask init-db
flask run
```

## Project Structure

- `app.py` — all routes and DB helpers in one file
- `schema.sql` — SQLite schema (cohorts, classes, students, attendance)
- `templates/` — Jinja2 templates (base, index, attendance, manage, report)
- `static/style.css` — dark theme matching kitty/tmux burnt orange palette
- `instance/attendance.db` — SQLite database (gitignored, created by `flask init-db`)

## Key Patterns

- DB connection via `get_db()` stored on Flask `g`, closed on teardown
- Attendance rows are auto-created (INSERT OR IGNORE) when a class/date is viewed
- Checkbox toggling uses HTMX — POST returns a replacement `<input>` element
- Students parsed as `Last, First` per line on import

## Theme

Dark mode with burnt orange accent (`#cc5500`), JetBrains Mono font. Colors pulled from kitty.conf and tmux.conf.
