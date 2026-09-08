"""
frontend_server.py — serves the static frontend files (index_1.html,
script.js, unit.js, styles.css, all in the frontend/ folder next to
this file) from the same Flask app as the API.

Renamed from frontend.py to frontend_server.py so it doesn't share a
name with the frontend/ folder it serves — the two are unrelated to
Python's import system (frontend/ has no __init__.py, so it was never
actually importable as a package), but having a file and a folder
with the same name sitting next to each other was confusing to read.

Serving them from here — instead of a separate dev server, or opening
index_1.html directly as a file:// page — is what lets the Microsoft
login session cookie actually work: frontend and API end up on the
exact same origin (127.0.0.1:5000), so there's no cross-origin
cookie/CORS setup needed, the same reasoning the old demo server.py
called out for its own static-serving route.

"/" serves index_1.html directly — it used to be a placeholder page
owned by app.py's email_bp; that route was removed once this existed.

Kept at the project root (not inside any group's folder) since it's
tied to the entry point, not owned by a specific team.
"""

import os
from flask import Blueprint, send_from_directory

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")

frontend_bp = Blueprint("frontend", __name__)


@frontend_bp.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index_1.html")


@frontend_bp.route("/<path:filename>")
def static_files(filename):
    # Catches script.js, unit.js, styles.css, etc. Registered after the
    # other blueprints' explicit routes (/login, /logs, /dashboard/, ...)
    # in create_app(), and Flask/Werkzeug always matches the most
    # specific (static-segment) route first, so this only catches
    # requests nothing else claimed.
    return send_from_directory(FRONTEND_DIR, filename)
