"""
==========================================================
  SECURE PDF VIEWER
  Cloudinary (PDF storage) + SQLite (users) + Flask
==========================================================
"""

import io
import os
import secrets
import string
import random
import sqlite3
import tempfile
import urllib.request
from functools import wraps
from datetime import datetime

import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask import (
    Flask, request, jsonify, render_template,
    session, send_file, abort, redirect, url_for
)
from pdf2image import convert_from_bytes
from PIL import Image

app = Flask(__name__)
app.secret_key = os.environ.get("test123", secrets.token_hex(32))

# ─────────────────────────────────────────────
# CLOUDINARY CONFIG — Environment variables se aata hai
# ─────────────────────────────────────────────
cloudinary.config(
    cloud_name = os.environ.get("dfpilv1om"),
    api_key    = os.environ.get("322893952695546"),
    api_secret = os.environ.get("CXgo0IFbyzmCuGXRQtPISwB-fnA"),
    secure     = True
)

# Poppler path — local Windows ke liye, Render pe None rehega (Linux pe auto-detect)
POPPLER_PATH = os.environ.get("POPPLER_PATH", None)
DB_FILE      = "secure_pdf.db"
DPI          = 150


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db():
    db = sqlite3.connect(DB_FILE)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email           TEXT UNIQUE NOT NULL,
        name            TEXT NOT NULL,
        password        TEXT NOT NULL,
        cloudinary_id   TEXT NOT NULL,
        pdf_name        TEXT NOT NULL,
        total_pages     INTEGER DEFAULT 0,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
        last_access     TEXT
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS access_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id   INTEGER,
        action    TEXT,
        ip        TEXT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    db.commit()
    db.close()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def generate_password(length=14):
    chars = string.ascii_letters + string.digits + "!@#$%"
    pwd   = [
        random.choice(string.ascii_uppercase),
        random.choice(string.ascii_lowercase),
        random.choice(string.digits),
        random.choice("!@#$%"),
    ]
    pwd += random.choices(chars, k=length - 4)
    random.shuffle(pwd)
    return "".join(pwd)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

def log_action(user_id, action):
    db = get_db()
    db.execute(
        "INSERT INTO access_log (user_id, action, ip) VALUES (?,?,?)",
        (user_id, action, request.remote_addr)
    )
    db.execute(
        "UPDATE users SET last_access=? WHERE id=?",
        (datetime.now().isoformat(), user_id)
    )
    db.commit()
    db.close()

def download_pdf_from_cloudinary(cloudinary_id):
    """Cloudinary se PDF bytes download karo"""
    url      = cloudinary.utils.cloudinary_url(
        cloudinary_id,
        resource_type="raw",
        sign_url=True
    )[0]
    with urllib.request.urlopen(url) as response:
        return response.read()


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("viewer") if "user_id" in session else url_for("login_page"))

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def do_login():
    email    = request.json.get("email", "").strip().lower()
    password = request.json.get("password", "").strip()

    db   = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email=? AND password=?",
        (email, password)
    ).fetchone()
    db.close()

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    session["user_id"]       = user["id"]
    session["user_name"]     = user["name"]
    session["cloudinary_id"] = user["cloudinary_id"]
    session["total_pages"]   = user["total_pages"]
    session["token"]         = secrets.token_urlsafe(16)

    log_action(user["id"], "login")
    return jsonify({"ok": True})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ─────────────────────────────────────────────
# VIEWER
# ─────────────────────────────────────────────

@app.route("/viewer")
@login_required
def viewer():
    return render_template(
        "viewer.html",
        user_name   = session["user_name"],
        token       = session["token"],
        total_pages = session["total_pages"]
    )


# ─────────────────────────────────────────────
# SECURE PAGE IMAGE API
# ─────────────────────────────────────────────

@app.route("/page/<int:page_num>")
@login_required
def get_page(page_num):
    """PDF Cloudinary se fetch karo, page image bana ke bhejo"""

    if request.args.get("t") != session.get("token"):
        abort(403)

    total = session.get("total_pages", 0)
    if page_num < 1 or (total > 0 and page_num > total):
        abort(404)

    try:
        # PDF bytes Cloudinary se download karo
        pdf_bytes = download_pdf_from_cloudinary(session["cloudinary_id"])

        # PDF page → Image
        pages = convert_from_bytes(
            pdf_bytes,
            dpi        = DPI,
            first_page = page_num,
            last_page  = page_num,
            poppler_path = POPPLER_PATH
        )
    except Exception as e:
        print(f"Page error: {e}")
        abort(500)

    if not pages:
        abort(404)

    # JPEG mein convert karo memory mein
    buf = io.BytesIO()
    pages[0].convert("RGB").save(buf, format="JPEG", quality=85)
    buf.seek(0)

    response = send_file(buf, mimetype="image/jpeg", as_attachment=False)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    response.headers["Pragma"]        = "no-cache"
    response.headers["Expires"]       = "0"

    log_action(session["user_id"], f"view_page_{page_num}")
    return response

@app.route("/page_count")
@login_required
def page_count():
    if request.args.get("t") != session.get("token"):
        abort(403)
    return jsonify({"pages": session.get("total_pages", 0)})


# ─────────────────────────────────────────────
# ADMIN — PDF Upload
# ─────────────────────────────────────────────

@app.route("/admin/upload-pdf", methods=["POST"])
def admin_upload_pdf():
    """
    PDF Cloudinary pe upload karo.
    Returns: cloudinary_id jo user add karte waqt use hoga.

    Usage:
        curl -X POST http://localhost:5000/admin/upload-pdf
             -F "file=@document.pdf"
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files allowed"}), 400

    try:
        result = cloudinary.uploader.upload(
            f,
            resource_type = "raw",
            folder        = "secure_pdfs",
            use_filename  = True,
            unique_filename = True
        )
        cloudinary_id = result["public_id"]

        # Page count nikalo
        from pypdf import PdfReader
        f.seek(0)
        reader      = PdfReader(f)
        total_pages = len(reader.pages)

        return jsonify({
            "message":      "PDF uploaded to Cloudinary",
            "cloudinary_id": cloudinary_id,
            "total_pages":  total_pages,
            "filename":     f.filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# ADMIN — User Add
# ─────────────────────────────────────────────

@app.route("/admin/add-user", methods=["POST"])
def admin_add_user():
    """
    User add karo with unique password.

    Body: {
        "name":          "Rahul Sharma",
        "email":         "rahul@gmail.com",
        "cloudinary_id": "secure_pdfs/document_abc123",
        "total_pages":   10
    }
    """
    data          = request.json or {}
    name          = data.get("name", "").strip()
    email         = data.get("email", "").strip().lower()
    cloudinary_id = data.get("cloudinary_id", "").strip()
    total_pages   = data.get("total_pages", 0)

    if not all([name, email, cloudinary_id]):
        return jsonify({"error": "name, email, cloudinary_id required"}), 400

    password = generate_password()

    try:
        db = get_db()
        db.execute(
            "INSERT INTO users (email, name, password, cloudinary_id, pdf_name, total_pages) VALUES (?,?,?,?,?,?)",
            (email, name, password, cloudinary_id, cloudinary_id.split("/")[-1], total_pages)
        )
        db.commit()
        db.close()
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 409

    return jsonify({
        "message":  f"User {name} added successfully",
        "email":    email,
        "password": password,      # Yeh user ko email karo!
    })

@app.route("/admin/users")
def admin_list_users():
    db    = get_db()
    users = db.execute(
        "SELECT id, name, email, pdf_name, total_pages, created_at, last_access FROM users"
    ).fetchall()
    db.close()
    return jsonify([dict(u) for u in users])


# ─────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Secure PDF Viewer → http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)