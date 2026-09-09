"""
SPIStaffOutlineSystem.py — application entry point.

This is the one real "main" file: it builds the Flask app and
registers each group's routes as a Blueprint, so every group keeps
owning its own folder while there's a single app actually running.

=== Project layout ===

    spi_backend/
    ├── SPIStaffOutlineSystem.py   <- this file (run this one)
    ├── frontend_server.py         <- serves frontend/ (root-level, not group-owned)
    ├── auth/                      <- login group
    │   ├── login.py
    │   └── server.py               (auth_bp)
    ├── email_approval/            <- email group
    │   ├── app.py                  (email_bp)
    │   └── email_service.py
    ├── dashboard/                 <- dashboard group
    │   └── dashboard.py            (dashboard_bp)
    ├── editing/                   <- editing group
    │   ├── editing.py
    │   ├── routes.py               (editing_bp)
    │   └── CreateNewDoc.py
    ├── shared/                    <- used by everyone, owned by no one group
    │   ├── retrieve_database.py
    │   └── error.py
    └── frontend/                  <- static frontend files (not Python)
        ├── index_1.html
        ├── script.js
        ├── unit.js
        └── styles.css

Each folder (except frontend/, which isn't Python) has an empty
__init__.py so it can be imported as a package, e.g.
`from auth.login import UserLogin`. Imports between folders are
absolute (`from shared.retrieve_database import ...`), not relative —
that only works if you always run this file FROM the spi_backend/
folder (`python SPIStaffOutlineSystem.py`), not from somewhere else or
by importing it as a module from outside this folder.

Configuration (Azure, mail, database credentials) is read from
environment variables everywhere in this project — never hardcoded.
Locally, put them in a `.env` file (see .env.example) and they load
automatically below. See the "Configuration" section in README.md for
how this differs once the app is actually deployed somewhere.

Run with:
    python SPIStaffOutlineSystem.py

Then visit http://localhost:5000/
"""

import os
from dotenv import load_dotenv

# Loads .env into the environment BEFORE any of this project's other
# modules (auth/login.py, shared/retrieve_database.py, ...) get
# imported and read os.environ.get(...) at their own module level —
# that ordering is why this happens here, at the very top, before
# anything else runs. Silently does nothing if .env doesn't exist
# (e.g. in production, where real env vars are set by the host
# instead — see README.md).
load_dotenv()

from flask import Flask
from flask_mail import Mail


def create_app() -> Flask:
    app = Flask(__name__)

    # --- Mail config (used by the email-approval blueprint) ---
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")

    # Used for session signing if/when Flask sessions get used elsewhere;
    # the Microsoft-login session store in login.py doesn't need this,
    # but Flask itself expects a SECRET_KEY to be set.
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")

    mail = Mail(app)
    # Stashed on the app so blueprints can grab it via current_app.extensions["mail"]
    # instead of importing a module-level `mail` object (which would tie
    # them to this file existing/being imported first).
    app.extensions["mail"] = mail

    if os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes"):
        print("=" * 60)
        print("  DEV_MODE is ON — /dev-login/<role> bypasses Microsoft login.")
        print("  Never run this on anything publicly reachable.")
        print("=" * 60)

    # --- Register each group's blueprint ---
    from auth.server import auth_bp                   # Microsoft login (auth group)
    from email_approval.app import email_bp            # email approval flow (email group)
    from dashboard.dashboard import dashboard_bp        # course dashboard (dashboard group)
    from editing.routes import editing_bp                # unit outline save/load (editing group)
    from frontend_server import frontend_bp             # static frontend files

    app.register_blueprint(auth_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(editing_bp)
    app.register_blueprint(frontend_bp)  # registered last: its "/<path:filename>" is a catch-all

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
