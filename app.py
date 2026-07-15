"""
Portfolio backend — Flask + SQLite.

Serves:
  - Public read API for projects, skills, experience, education,
    certifications and testimonials (used by the frontend to render
    dynamic content).
  - A contact form endpoint that stores messages in the database.
  - A JWT-protected admin API for creating/editing/deleting all content
    and viewing contact messages.
  - The static frontend (index.html for visitors, admin.html for you).

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000  (site)  and  http://localhost:5000/admin.html  (admin panel).

On first run a SQLite database (portfolio.db) is created and seeded with
placeholder content plus a default admin account:
    username: admin
    password: changeme123
CHANGE THIS PASSWORD before deploying — see README.md.
"""

import os
import sqlite3
import datetime
import functools

import jwt  # type: ignore
try:
    from flask import Flask, g, jsonify, request, send_from_directory  # type: ignore
except Exception as e:  # ImportError or environment issues
    import sys
    print("Error importing Flask or its symbols:", e)
    print("Make sure Flask is installed: pip install flask")
    sys.exit(1)
try:
    from werkzeug.security import generate_password_hash, check_password_hash  # type: ignore
except Exception:
    # Lightweight fallback if Werkzeug isn't available. Uses PBKDF2-HMAC-SHA256.
    import hashlib
    import os

    def generate_password_hash(password: str) -> str:
        salt = os.urandom(16)
        iterations = 100000
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return f"pbkdf2_sha256${iterations}${salt.hex()}${dk.hex()}"

    def check_password_hash(pwhash: str, password: str) -> bool:
        try:
            algo, iter_str, salt_hex, dk_hex = pwhash.split("$")
            if algo != "pbkdf2_sha256":
                return False
            iterations = int(iter_str)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(dk_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
            return hashlib.compare_digest(dk, expected)
        except Exception:
            return False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "portfolio.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
TOKEN_TTL_HOURS = 12

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


# --------------------------------------------------------------------------
# Database helpers
# --------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    tech TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT 'web',
    github_url TEXT NOT NULL DEFAULT '',
    demo_url TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS experience (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    company TEXT NOT NULL,
    date_range TEXT NOT NULL DEFAULT '',
    bullets TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    degree TEXT NOT NULL,
    institution TEXT NOT NULL,
    date_range TEXT NOT NULL DEFAULT '',
    meta TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS certifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    issuer TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS testimonials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT '',
    quote TEXT NOT NULL DEFAULT '',
    initials TEXT NOT NULL DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);
"""


def seed_if_empty(db):
    cur = db.execute("SELECT COUNT(*) AS c FROM admin_user")
    if cur.fetchone()["c"] == 0:
        db.execute(
            "INSERT INTO admin_user (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("changeme123")),
        )

    cur = db.execute("SELECT COUNT(*) AS c FROM projects")
    if cur.fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO projects (title, description, tech, category, github_url, demo_url, sort_order) "
            "VALUES (?,?,?,?,?,?,?)",
            [
                ("[Project Name]", "[One or two lines describing the problem it solves and your role.]",
                 "React,Node.js", "web", "[GitHub URL]", "[Live Demo URL]", 1),
                ("[Project Name]", "[One or two lines describing the problem it solves and your role.]",
                 "Python,scikit-learn", "ml", "[GitHub URL]", "[Live Demo URL]", 2),
                ("[Project Name]", "[One or two lines describing the problem it solves and your role.]",
                 "Python,CLI", "tools", "[GitHub URL]", "[Live Demo URL]", 3),
                ("[Project Name]", "[One or two lines describing the problem it solves and your role.]",
                 "HTML,CSS,JS", "web", "[GitHub URL]", "[Live Demo URL]", 4),
            ],
        )

    cur = db.execute("SELECT COUNT(*) AS c FROM skills")
    if cur.fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO skills (category, tags, sort_order) VALUES (?,?,?)",
            [
                ("Languages", "Python,JavaScript,Java,C++", 1),
                ("Frontend", "HTML/CSS,React,Tailwind", 2),
                ("Backend", "Flask,Node.js,REST APIs", 3),
                ("Databases", "SQLite,MySQL,MongoDB", 4),
                ("Cloud & DevOps", "Git,GitHub Actions,Vercel", 5),
                ("Tools", "VS Code,Postman,Figma", 6),
                ("Soft skills", "Problem solving,Communication,Teamwork", 7),
            ],
        )

    cur = db.execute("SELECT COUNT(*) AS c FROM experience")
    if cur.fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO experience (role, company, date_range, bullets, sort_order) VALUES (?,?,?,?,?)",
            [
                ("[Your Role]", "[Company Name]", "[Start] – [End]",
                 "[Responsibility or achievement]\n[Responsibility or achievement]\n[Tech stack used]", 1),
                ("[Internship / Role]", "[Company Name]", "[Start] – [End]",
                 "[Responsibility or achievement]\n[Responsibility or achievement]", 2),
            ],
        )

    cur = db.execute("SELECT COUNT(*) AS c FROM education")
    if cur.fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO education (degree, institution, date_range, meta, sort_order) VALUES (?,?,?,?,?)",
            [
                ("[Degree, e.g. B.Tech in Computer Science]", "[Institution Name]",
                 "[Start Year] – [End Year]", "GPA: [Your GPA]", 1),
                ("[Higher Secondary / Diploma]", "[Institution Name]", "[Start Year] – [End Year]", "", 2),
            ],
        )

    cur = db.execute("SELECT COUNT(*) AS c FROM certifications")
    if cur.fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO certifications (name, issuer, date, sort_order) VALUES (?,?,?,?)",
            [
                ("[Certification Name]", "[Issuer]", "[Date]", 1),
                ("[Certification Name]", "[Issuer]", "[Date]", 2),
                ("[Certification Name]", "[Issuer]", "[Date]", 3),
            ],
        )

    cur = db.execute("SELECT COUNT(*) AS c FROM testimonials")
    if cur.fetchone()["c"] == 0:
        db.executemany(
            "INSERT INTO testimonials (name, role, quote, initials, sort_order) VALUES (?,?,?,?,?)",
            [
                ("[Name]", "[Role, Company]", "[Testimonial quote about working with you.]", "JD", 1),
                ("[Name]", "[Role, Company]", "[Testimonial quote about working with you.]", "AK", 2),
            ],
        )
    db.commit()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    db.row_factory = sqlite3.Row
    seed_if_empty(db)
    db.close()


# --------------------------------------------------------------------------
# CORS (manual — lets the frontend be opened/served separately during dev)
# --------------------------------------------------------------------------

@app.after_request
def add_cors_headers(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return resp


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return "", 204


# --------------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------------

def make_token(username):
    payload = {
        "sub": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_TTL_HOURS),
        "iat": datetime.datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def require_admin(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth.split(" ", 1)[1]
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Session expired, please log in again"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        return fn(*args, **kwargs)
    return wrapper


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    db = get_db()
    row = db.execute("SELECT * FROM admin_user WHERE username = ?", (username,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401
    return jsonify({"token": make_token(username)})


@app.route("/api/admin/change-password", methods=["POST"])
@require_admin
def change_password():
    data = request.get_json(silent=True) or {}
    new_password = data.get("new_password") or ""
    if len(new_password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    db = get_db()
    db.execute("UPDATE admin_user SET password_hash = ? WHERE username = 'admin'",
               (generate_password_hash(new_password),))
    db.commit()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Generic CRUD resource builder
# --------------------------------------------------------------------------
# Each resource: table name, list of editable columns (order matters for insert),
# and the public read endpoint name.

RESOURCES = {
    "projects": ["title", "description", "tech", "category", "github_url", "demo_url", "sort_order"],
    "skills": ["category", "tags", "sort_order"],
    "experience": ["role", "company", "date_range", "bullets", "sort_order"],
    "education": ["degree", "institution", "date_range", "meta", "sort_order"],
    "certifications": ["name", "issuer", "date", "sort_order"],
    "testimonials": ["name", "role", "quote", "initials", "sort_order"],
}


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


def register_resource(name, columns):
    # Public: list all rows, ordered
    def list_public():
        db = get_db()
        rows = db.execute(f"SELECT * FROM {name} ORDER BY sort_order ASC, id ASC").fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    list_public.__name__ = f"list_public_{name}"
    app.add_url_rule(f"/api/{name}", view_func=list_public, methods=["GET"])

    # Admin: create
    def create_item():
        data = request.get_json(silent=True) or {}
        values = [data.get(col, "") for col in columns]
        db = get_db()
        placeholders = ",".join("?" for _ in columns)
        cur = db.execute(f"INSERT INTO {name} ({','.join(columns)}) VALUES ({placeholders})", values)
        db.commit()
        row = db.execute(f"SELECT * FROM {name} WHERE id = ?", (cur.lastrowid,)).fetchone()
        return jsonify(row_to_dict(row)), 201

    create_item.__name__ = f"create_{name}"
    app.add_url_rule(f"/api/admin/{name}", view_func=require_admin(create_item), methods=["POST"])

    # Admin: update
    def update_item(item_id):
        data = request.get_json(silent=True) or {}
        db = get_db()
        existing = db.execute(f"SELECT * FROM {name} WHERE id = ?", (item_id,)).fetchone()
        if not existing:
            return jsonify({"error": "Not found"}), 404
        updates = {col: data.get(col, existing[col]) for col in columns}
        set_clause = ",".join(f"{col} = ?" for col in columns)
        db.execute(f"UPDATE {name} SET {set_clause} WHERE id = ?", [*updates.values(), item_id])
        db.commit()
        row = db.execute(f"SELECT * FROM {name} WHERE id = ?", (item_id,)).fetchone()
        return jsonify(row_to_dict(row))

    update_item.__name__ = f"update_{name}"
    app.add_url_rule(f"/api/admin/{name}/<int:item_id>", view_func=require_admin(update_item), methods=["PUT"])

    # Admin: delete
    def delete_item(item_id):
        db = get_db()
        db.execute(f"DELETE FROM {name} WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"ok": True})

    delete_item.__name__ = f"delete_{name}"
    app.add_url_rule(f"/api/admin/{name}/<int:item_id>", view_func=require_admin(delete_item), methods=["DELETE"])


for res_name, cols in RESOURCES.items():
    register_resource(res_name, cols)


# --------------------------------------------------------------------------
# Contact form + admin message inbox
# --------------------------------------------------------------------------

@app.route("/api/contact", methods=["POST"])
def submit_contact():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or not message:
        return jsonify({"error": "Name, email and message are all required"}), 400
    if "@" not in email or "." not in email.split("@")[-1]:
        return jsonify({"error": "Please provide a valid email address"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO messages (name, email, message, created_at, read) VALUES (?,?,?,?,0)",
        (name, email, message, datetime.datetime.utcnow().isoformat()),
    )
    db.commit()
    return jsonify({"ok": True, "message": "Thanks — your message has been received."}), 201


@app.route("/api/admin/messages", methods=["GET"])
@require_admin
def list_messages():
    db = get_db()
    rows = db.execute("SELECT * FROM messages ORDER BY created_at DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/api/admin/messages/<int:msg_id>/read", methods=["PUT"])
@require_admin
def mark_message_read(msg_id):
    db = get_db()
    db.execute("UPDATE messages SET read = 1 WHERE id = ?", (msg_id,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/admin/messages/<int:msg_id>", methods=["DELETE"])
@require_admin
def delete_message(msg_id):
    db = get_db()
    db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    db.commit()
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Static frontend
# --------------------------------------------------------------------------

@app.route("/")
def serve_index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)


# Simple health-check endpoint for load balancers and uptime checks.
@app.route("/health")
def health_check():
    # Responds 200 when the app can access the database; keeps lightweight.
    try:
        db = get_db()
        cur = db.execute("SELECT 1 AS ok").fetchone()
        ok = bool(cur and cur["ok"] == 1)
    except Exception:
        ok = False
    status = {"status": "ok" if ok else "error", "db": ok}
    return jsonify(status), (200 if ok else 503)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    # Allow opting into a production WSGI server. Set `USE_WAITRESS=1`
    # to run with Waitress (works on Windows).
    # By default: if `FLASK_DEBUG` is enabled we run Flask's builtin
    # server for development; otherwise prefer Waitress so the
    # development-server warning is not shown when running `python app.py`.
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    use_waitress_env = os.environ.get("USE_WAITRESS", "").lower() in ("1", "true", "yes")
    use_waitress = use_waitress_env or (not debug)

    if use_waitress:
        try:
            from waitress import serve  # type: ignore
        except Exception:
            print("Waitress is not installed. Install it with: pip install waitress")
            raise
        serve(app, host="0.0.0.0", port=port)
    else:
        app.run(host="0.0.0.0", port=port, debug=debug)
else:
    # also initialise when imported by a WSGI server (gunicorn etc.)
    init_db()
