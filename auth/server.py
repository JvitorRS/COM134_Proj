"""
server.py — Microsoft login routes, now as a Flask Blueprint.

Still no auth logic of its own — everything auth-related stays delegated
to login.py (unchanged; it never depended on http.server in the first
place, which is exactly why this move didn't touch it). This file only
translates HTTP requests into calls on those classes.

Dev-only. In production, run behind a real server and terminate TLS at a
reverse proxy, and set COOKIES_SECURE = True.
"""

from urllib.parse import quote
import os

from flask import Blueprint, request, redirect, make_response, jsonify

from auth.login import (
    MicrosoftAuthHandler,
    UserLogin,
    UserRole,
    UserSignOut,
    SessionManager,
    LoginStateStore,
)

auth_bp = Blueprint("auth", __name__)

# Set to True only when actually served over HTTPS.
COOKIES_SECURE = False

# =====================================================================
# DEV LOGIN — bypasses Microsoft entirely, ONLY when DEV_MODE is set.
#
# This exists so the rest of the app (dashboard, course CRUD, change
# requests/approval, everything role-gated) can be built and tested
# before the real Azure AD app registration exists. It creates a
# session the exact same way real login does (SessionManager, same
# shape of user_info dict), so /api/session, _require_admin(), etc.
# all work completely unchanged — nothing downstream needs to know
# the difference. Once real Azure credentials are in and DEV_MODE is
# unset, these routes refuse to work at all.
#
# Enable with:  export DEV_MODE=1
# NEVER set DEV_MODE on anything publicly reachable — it lets anyone
# who knows the URL log in as any role with zero credentials.
# =====================================================================
DEV_MODE = os.environ.get("DEV_MODE", "").lower() in ("1", "true", "yes")

DEV_USERS = {
    "admin": {"email": "dev-admin@spi.edu.au", "name": "Dev Admin", "roles": ["admin"], "is_dev_session": True},
    "course_coord": {"email": "dev-coursecoord@spi.edu.au", "name": "Dev Course Coordinator", "roles": ["course_coord"], "is_dev_session": True},
    "unit_coord": {"email": "dev-unitcoord@spi.edu.au", "name": "Dev Unit Coordinator", "roles": ["unit_coord"], "is_dev_session": True},
    # No "hr" role — confirmed there are only 3 roles in this system.
}


@auth_bp.route("/api/dev-mode")
def api_dev_mode():
    """The frontend checks this to decide whether to show the dev-login buttons at all."""
    return jsonify({"enabled": DEV_MODE})


@auth_bp.route("/dev-login/<role>")
def dev_login(role):
    if not DEV_MODE:
        return "Dev login is disabled. Set the DEV_MODE environment variable to enable it.", 403

    user_info = DEV_USERS.get(role)
    if not user_info:
        return f"Unknown dev role '{role}'. Choose one of: {', '.join(DEV_USERS)}", 400

    session_id = SessionManager.create_session(user_info)

    resp = make_response(redirect("/"))
    resp.set_cookie(
        "session_id",
        session_id,
        httponly=True,
        samesite="Lax",
        secure=COOKIES_SECURE,
        path="/",
    )
    return resp


@auth_bp.route("/login")
def login():
    state = LoginStateStore.issue_state()
    login_url = MicrosoftAuthHandler().get_login_url(state)
    return redirect(login_url)


@auth_bp.route("/auth/callback")
def auth_callback():
    auth_code = request.args.get("code")
    state = request.args.get("state")

    # Redirect back to the login screen with the error in the query
    # string (instead of returning a bare error page) so the frontend
    # can show it inline on #loginError — see showLoginErrorFromUrl()
    # in script.js.
    if not state or not LoginStateStore.verify_and_consume(state):
        return redirect("/?login_error=" + quote("Invalid or expired login attempt. Please try again."))

    if not auth_code:
        return redirect("/?login_error=" + quote("Missing auth code."))

    try:
        user_info = UserLogin().login_with_code(auth_code)
        session_id = SessionManager.create_session(user_info)

        resp = make_response(redirect("/"))
        resp.set_cookie(
            "session_id",
            session_id,
            httponly=True,
            samesite="Lax",
            secure=COOKIES_SECURE,
            path="/",
        )
        return resp
    except PermissionError as e:
        return redirect("/?login_error=" + quote(str(e)))


@auth_bp.route("/logout")
def logout():
    session_id = request.cookies.get("session_id")
    if not session_id:
        return redirect("/")

    session = SessionManager.get_session(session_id)
    is_dev_session = bool(session and session["user"].get("is_dev_session"))

    if is_dev_session:
        # Dev-login never touched Microsoft, so there's no Microsoft
        # session to sign out of — just clear the local cookie and go
        # home. Sending this through UserSignOut() would build a
        # Microsoft logout URL from AZURE_TENANT_ID, which is exactly
        # what broke before: an unconfigured/misconfigured tenant ID
        # produces a broken URL like .../None/oauth2/v2.0/logout,
        # which Microsoft correctly reports as "page can't be found."
        SessionManager.destroy_session(session_id)
        resp = make_response(redirect("/"))
        resp.set_cookie(
            "session_id", "", expires=0,
            httponly=True, samesite="Lax", secure=COOKIES_SECURE, path="/",
        )
        return resp

    microsoft_logout_url = UserSignOut().sign_out(session_id)

    resp = make_response(redirect(microsoft_logout_url))
    resp.set_cookie(
        "session_id",
        "",
        expires=0,
        httponly=True,
        samesite="Lax",
        secure=COOKIES_SECURE,
        path="/",
    )
    return resp


@auth_bp.route("/whoami")
def whoami():
    """Human-readable version, handy for checking session state directly in a browser tab."""
    session_id = request.cookies.get("session_id")
    session = SessionManager.get_session(session_id) if session_id else None

    if session:
        return f"Logged in as {session['user']['email']}."
    return "Not logged in. Go to /login to sign in with Microsoft."


@auth_bp.route("/api/session")
def api_session():
    """
    JSON session-state endpoint — this is what script.js actually calls
    on page load (checkAuthSession()) instead of trusting whatever was
    last cached in localStorage.
    """
    session_id = request.cookies.get("session_id")
    session = SessionManager.get_session(session_id) if session_id else None

    if not session:
        return jsonify({"logged_in": False})

    user_info = session["user"]  # {"email": ..., "name": ..., "roles": [...]}
    role = UserRole(user_info).get_role()

    return jsonify({
        "logged_in": True,
        "name": user_info.get("name") or user_info.get("email"),
        "email": user_info.get("email"),
        # NOTE: this is the raw Azure AD App Role value assigned to this
        # user. script.js's roleLabels/permission checks expect exactly
        # "admin" / "course_coord" / "unit_coord" (case-sensitive)
        # — confirm these are the actual App Role values configured in
        # Azure AD before relying on this, or add a mapping layer here
        # if they end up named differently.
        "role": role,
    })
