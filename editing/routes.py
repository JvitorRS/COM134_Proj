"""
routes.py — HTTP routes for the editing group (editing_bp).

This is what finally connects the frontend's "Save Outline Changes"
button to the `unit_outlines` table. Before this file existed, the
button only ever wrote to the browser's localStorage, and
retrieve_database.py's save_doc()/log_history() had nothing calling
them.

    GET  /editing/api/outlines/<unit_code>   -> load a unit's saved outline
    POST /editing/api/outlines/<unit_code>   -> save it (insert, or new version)

=== How a save works ===

1. The frontend posts {"outlineData": {...form fields...}} for a unit code.
2. We look the unit up by code (Retrieve_Database.get_doc_by_unit_code).
   - Found     -> save a NEW VERSION of that row (version bumped).
   - Not found -> INSERT a brand-new row at version 1.
3. SaveDoc (editing.py) serialises the fields to JSON and writes the
   row, then records the save in history_log.

=== Why there's no approval gate here ===

SaveDoc.run() gates on an approved ApprovalReq; this route calls
SaveDoc.run_direct(), which doesn't. That's deliberate — the Save
button is an authorised editor saving their own work in a unit they
already have access to. The approval workflow belongs to the separate
"Request a Change" feature (email_approval/), where someone WITHOUT
edit rights asks for a change. If that ever needs to change, swap
run_direct() for run() here and pass in the ApprovalReq.

=== Permissions ===

You must be logged in (same session cookie every other route uses).
Beyond that, admins can save any unit; everyone else can only save a
unit they have access to via staff_course_access — checked server-side
in _may_edit(), because script.js's field-locking is cosmetic only.
"""

import json

from flask import Blueprint, request, jsonify

from auth.login import SessionManager, UserRole
from editing.editing import SaveDoc
from shared.retrieve_database import Retrieve_Database

editing_bp = Blueprint("editing", __name__, url_prefix="/editing")


# ---- helpers ---------------------------------------------------------

def _current_session():
    """The logged-in user's session dict (from login.py), or None."""
    session_id = request.cookies.get("session_id")
    return SessionManager.get_session(session_id) if session_id else None


def _may_edit(user, unit_code):
    """
    True if this user is allowed to save the given unit.

    Admins can save anything. Everyone else must have the unit in their
    staff_course_access list — matched on the COURSE CODE, which is the
    same string the outline is keyed by.
    """
    if UserRole(user).get_role() == "admin":
        return True

    allowed = Retrieve_Database.get_courses_for_staff(user.get("email"))
    return any(course.code == unit_code for course in allowed)


def _outline_to_json(record):
    """
    UnitOutlineRecord -> the JSON the frontend expects.

    `content` is stored as a JSON string in the database; it's parsed
    back into a real object here so script.js can drop it straight into
    the form. If an older row holds something that isn't valid JSON, we
    hand it back as a raw string under `contentRaw` rather than blowing
    up the whole request.
    """
    try:
        outline_data = json.loads(record.content) if record.content else {}
        content_raw = None
    except (ValueError, TypeError):
        outline_data = None
        content_raw = record.content

    return {
        "id": record.id,
        "unitCode": record.unit_code,
        "outlineData": outline_data,
        "contentRaw": content_raw,
        "lastEditedBy": record.last_edited_by,
        "lastEditedAt": record.last_edited_at.isoformat() if record.last_edited_at else None,
        "version": record.version,
    }


# ---- routes ---------------------------------------------------------

@editing_bp.route("/api/outlines/<unit_code>", methods=["GET"])
def api_get_outline(unit_code):
    """
    Load a unit's saved outline so the form can be populated from the
    database instead of from localStorage.

    Returns 404 when the unit has never been saved — that's a normal,
    expected answer for a brand-new course, not an error. The frontend
    treats it as "show the blank template".
    """
    session = _current_session()
    if not session:
        return jsonify({"error": "Not logged in"}), 401

    try:
        record = Retrieve_Database.get_doc_by_unit_code(unit_code)
    except Exception as err:
        # Most likely the DB_* environment variables aren't set, or MySQL
        # isn't running. Answer with JSON either way — the frontend reads
        # response.json() and would choke on Flask's HTML error page.
        return jsonify({"error": f"Could not reach the database: {err}"}), 500

    if not record:
        return jsonify({"error": "No saved outline for this unit yet"}), 404

    return jsonify(_outline_to_json(record))


@editing_bp.route("/api/outlines/<unit_code>", methods=["POST"])
def api_save_outline(unit_code):
    """
    Save the Unit Outline form into the unit_outlines table, and record
    the save in history_log.

    Body: {"outlineData": { ...field id -> value... }}

    First save for a unit inserts a row at version 1; every save after
    that updates the same row and bumps its version.
    """
    session = _current_session()
    if not session:
        return jsonify({"error": "Not logged in"}), 401

    user = session["user"]

    data = request.get_json(silent=True) or {}
    outline_data = data.get("outlineData")
    if not isinstance(outline_data, dict) or not outline_data:
        return jsonify({"error": "outlineData must be a non-empty object of outline fields"}), 400

    # Keep the stored content honest: the unit code in the URL is the
    # one this outline is filed under, so it wins over whatever the
    # form field happens to contain.
    outline_data = {**outline_data, "unit_code": unit_code}

    editor_email = user.get("email") or user.get("name") or "unknown"

    try:
        if not _may_edit(user, unit_code):
            return jsonify({"error": "You do not have edit access to this unit"}), 403

        # Existing row -> new version of it. No row -> fresh insert.
        existing = Retrieve_Database.get_doc_by_unit_code(unit_code)

        record = SaveDoc().run_direct(
            sheet=outline_data,
            source="Frontend",
            editor_name=editor_email,
            unit_code=unit_code,
            unit_outline_id=existing.id if existing else None,
        )
    except Exception as err:
        # A failed save must not look like a successful one to the user
        # — the frontend shows this message in its error toast. JSON, not
        # Flask's HTML error page, because that's what the frontend reads.
        return jsonify({"error": f"Could not save the outline: {err}"}), 500

    return jsonify(_outline_to_json(record)), 200 if existing else 201
