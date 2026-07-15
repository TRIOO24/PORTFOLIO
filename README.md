
# Portfolio backend (Flask + SQLite)

A small backend for the portfolio site. It stores projects, skills,
experience, education, certifications, testimonials and contact messages
in SQLite, exposes a public read API the site uses to render itself, and
a password-protected admin panel to edit everything without touching code.

## What's included

- `app.py` — the Flask app (API + serves the frontend)
- `static/index.html` — the public site (pulls its content from the API)
- `static/admin.html` — the admin dashboard (`/admin.html`)
- `requirements.txt`

## Run it locally

```bash
python -m venv venv
# Activate the venv:
# Linux / macOS:
source venv/bin/activate
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (cmd.exe):
venv\Scripts\activate.bat

pip install -r requirements.txt

# Development (Flask builtin server; shows debug info):
# PowerShell:
$env:FLASK_DEBUG = "1"
python app.py
# Unix / Bash:
FLASK_DEBUG=1 python app.py

# Production (Waitress WSGI server — the app prefers Waitress when not in debug):
python app.py
# Force Waitress explicitly:
$env:USE_WAITRESS = "1" && python app.py

# Optional (Linux) using gunicorn:
gunicorn -w 4 -b 0.0.0.0:8000 "app:app"
```

Open:
- Site: http://localhost:5000
- Admin: http://localhost:5000/admin.html

First run creates `portfolio.db` automatically, seeded with placeholder
content and one admin account:

```
username: admin
password: changeme123
```

**Change this password immediately** — log in, go to the "Account" tab,
and set a new one (minimum 8 characters).

## How it fits together

- The site (`index.html`) fetches `/api/projects`, `/api/skills`,
  `/api/experience`, `/api/education`, `/api/certifications`, and
  `/api/testimonials` on page load and renders them. Edit content in the
  admin panel and refresh the site to see it update — no redeploy needed.
- The contact form POSTs to `/api/contact` and messages are stored in the
  database. Read them in the admin panel's "Messages" tab.
- Admin write routes (`/api/admin/...`) require a JWT obtained from
  `/api/admin/login`, sent as `Authorization: Bearer <token>`. Tokens
  expire after 12 hours.

## Environment variables

| Variable      | Purpose                                   | Default              |
|---------------|--------------------------------------------|----------------------|
| `SECRET_KEY`  | Signs admin JWTs — set a real secret in production | `dev-secret-change-me` |
| `PORT`        | Port the app listens on                    | `5000`                |

Set a strong `SECRET_KEY` before deploying:
```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

## Deploying

The app is a standard Flask app, deployable anywhere that runs Python:

**Render / Railway / Fly.io**
1. Push this folder to a GitHub repo.
2. Create a new web service, set the start command to:
   `gunicorn app:app`
3. Set the `SECRET_KEY` environment variable.
4. Note: SQLite is a single file on local disk — on platforms with
   ephemeral filesystems (some free tiers) the database resets on
   redeploy. For anything long-lived, use a host with a persistent disk
   (e.g. Render's persistent disk add-on) or swap SQLite for a managed
   Postgres database later.

**PythonAnywhere**
Straightforward for a Flask app with SQLite since it gives you a
persistent filesystem — upload the folder, set up a virtualenv, point
the WSGI file at `app.app`.

## Extending

- Contact messages are stored, not emailed. To get email notifications,
  add an SMTP call (e.g. with `smtplib` or a service like SendGrid)
  inside `submit_contact()` in `app.py`.
- All CRUD resources (`projects`, `skills`, `experience`, `education`,
  `certifications`, `testimonials`) are generated from one table in
  `RESOURCES` near the top of `app.py` — adding a new field means adding
  a column to the relevant `CREATE TABLE` statement and to that list.
