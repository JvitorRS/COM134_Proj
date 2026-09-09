"""
dashboard.py — course dashboard for logged-in staff, as a Flask Blueprint.

The list of courses itself is now real (backed by the `courses` /
`staff_course_access` tables via retrieve_database.py):
  - GET    /dashboard/api/courses          -> every course (admin) or
                                               just the caller's assigned
                                               courses (everyone else)
  - POST   /dashboard/api/courses          -> create a course (admin only)
  - PUT    /dashboard/api/courses/<id>     -> edit a course (admin only)
  - DELETE /dashboard/api/courses/<id>     -> delete a course (admin only)

Role checks happen HERE, not just in the frontend — script.js already
hides the Add/Edit/Delete buttons for non-admins, but that's cosmetic
only; _require_admin() below is the real enforcement.

What's still NOT wired up: the actual unit outline CONTENT inside each
course (learning outcomes, assessments, etc.) — that's still stored
client-side only, waiting on the editing group's decision on how
outline content gets structured (see retrieve_database.py's
save_doc()). This file only manages the course list itself
(code/name/semester/start date/description), which doesn't depend on
that decision.

DisplayUserCourse/CourseFilter below are still stubs — not built out
as part of this pass, the routes above call Retrieve_Database directly
instead (same pattern server.py/app.py already use).
"""

import io
import json
import re
import zipfile
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file
from mysql.connector.errors import IntegrityError

from shared.retrieve_database import Retrieve_Database
from auth.login import SessionManager, UserRole

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _safe_filename(course_code, used_names):
    """
    Turn a course code into a safe .json filename for inside the ZIP.

    Course codes come from the database, where nothing stops someone
    entering "../../etc/passwd" or "CS 101/A" as a code. Anything that
    isn't a letter, digit, dash or underscore is replaced, which also
    removes the path separators and "..", so an entry can never escape
    the archive when extracted.

    `used_names` collects what's already in the archive: two courses
    with codes that sanitise to the same name would otherwise produce
    two entries with one filename, and most extractors silently keep
    only the last one.
    """
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", str(course_code)).strip("_") or "course"

    name = f"{stem}.json"
    counter = 2
    while name in used_names:
        name = f"{stem}-{counter}.json"
        counter += 1

    used_names.add(name)
    return name


class Dashboard:
    def __init__(self):
        pass


# Display the courses which are related to user
class DisplayUserCourse(Dashboard):
    def __init__(self):
        pass


# Filter the course depending on user's requirement
class CourseFilter(Dashboard):
    def __init__(self):
        pass


# ---- helpers ---------------------------------------------------------

def _current_session():
    """The logged-in user's session dict (from login.py), or None."""
    session_id = request.cookies.get("session_id")
    return SessionManager.get_session(session_id) if session_id else None


def _require_admin():
    """
    Returns None if the caller is a logged-in admin. Otherwise returns
    a (response, status) tuple the route should return immediately.
    """
    session = _current_session()
    if not session:
        return jsonify({"error": "Not logged in"}), 401

    role = UserRole(session["user"]).get_role()
    if role != "admin":
        return jsonify({"error": "Admin role required"}), 403

    return None


def _course_to_json(course):
    """CourseRecord -> the shape script.js's course objects already expect."""
    return {
        "id": course.id,
        "code": course.code,
        "name": course.name,
        "semester": course.semester,
        "startDate": str(course.start_date) if course.start_date else None,
        "description": course.description,
    }


# ---- routes ---------------------------------------------------------

@dashboard_bp.route("/")
def dashboard_home():
    # Placeholder — the actual dashboard page is served by frontend.py;
    # this is just a sanity-check route for the blueprint itself.
    return "Dashboard blueprint is running. See /dashboard/api/courses."


@dashboard_bp.route("/api/courses", methods=["GET"])
def api_get_courses():
    session = _current_session()
    if not session:
        return jsonify({"error": "Not logged in"}), 401

    user = session["user"]
    role = UserRole(user).get_role()

    try:
        if role == "admin":
            courses = Retrieve_Database.get_all_courses()
        else:
            courses = Retrieve_Database.get_courses_for_staff(user.get("email"))
    except Exception as err:
        # JSON, not Flask's HTML 500 page: the dashboard reads
        # response.json() to find out WHY it has no courses, and shows
        # that reason instead of a misleading "No courses yet".
        return jsonify({"error": f"Could not reach the database: {err}"}), 500

    return jsonify([_course_to_json(c) for c in courses])


@dashboard_bp.route("/api/courses", methods=["POST"])
def api_create_course():
    denied = _require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not code or not name:
        return jsonify({"error": "code and name are required"}), 400

    try:
        course = Retrieve_Database.create_course(
            code=code,
            name=name,
            semester=data.get("semester", ""),
            start_date=data.get("startDate") or None,
            description=data.get("description", ""),
        )
    except IntegrityError:
        # courses.code is UNIQUE. This is the normal outcome when someone
        # re-imports a file they exported earlier, so it needs a readable
        # message and a 409 — it used to escape as an unhandled
        # IntegrityError and Flask returned a raw HTML 500 page, which
        # the frontend then couldn't even parse to show a reason.
        return jsonify({"error": f"A course with code '{code}' already exists"}), 409
    except Exception as err:
        return jsonify({"error": f"Could not create the course: {err}"}), 500

    return jsonify(_course_to_json(course)), 201


@dashboard_bp.route("/api/courses/<int:course_id>", methods=["PUT"])
def api_update_course(course_id):
    denied = _require_admin()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    fields = {}
    if "code" in data:
        fields["code"] = data["code"]
    if "name" in data:
        fields["name"] = data["name"]
    if "semester" in data:
        fields["semester"] = data["semester"]
    if "startDate" in data:
        fields["start_date"] = data["startDate"] or None
    if "description" in data:
        fields["description"] = data["description"]

    try:
        course = Retrieve_Database.update_course(course_id, **fields)
    except IntegrityError:
        return jsonify({"error": f"Another course already uses code '{fields.get('code')}'"}), 409
    except Exception as err:
        return jsonify({"error": f"Could not update the course: {err}"}), 500

    if not course:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(_course_to_json(course))


@dashboard_bp.route("/api/courses/<int:course_id>", methods=["DELETE"])
def api_delete_course(course_id):
    denied = _require_admin()
    if denied:
        return denied

    try:
        deleted = Retrieve_Database.delete_course(course_id)
    except IntegrityError:
        # staff_course_access.course_id is a FOREIGN KEY to this row, so
        # MySQL refuses to delete a course anyone still has access to.
        return jsonify({
            "error": "This course still has staff assigned to it (staff_course_access). "
                     "Remove those assignments first, then delete the course."
        }), 409
    except Exception as err:
        return jsonify({"error": f"Could not delete the course: {err}"}), 500

    if not deleted:
        return jsonify({"error": "Course not found"}), 404
    return jsonify({"deleted": True})


@dashboard_bp.route("/api/courses/export", methods=["GET"])
def api_export_courses():
    """
    Export every course the caller can see as a ZIP containing ONE JSON
    FILE PER COURSE — CS101.json, IT201.json, and so on — rather than a
    single combined file.

    Why a ZIP rather than several downloads: a browser will not let a
    page start a series of downloads on its own. Chrome shows a
    "Download multiple files?" permission prompt and other browsers
    silently drop everything after the first, so "one file per course"
    delivered as separate downloads is unreliable by design. One ZIP is
    a single download that always works, and the user gets the separate
    files as soon as they extract it.

    Each course's JSON includes its unit outline content from the
    `unit_outlines` table when there is one, so an exported file is the
    whole course, not just its dashboard row.
    """
    session = _current_session()
    if not session:
        return jsonify({"error": "Not logged in"}), 401

    user = session["user"]
    role = UserRole(user).get_role()

    try:
        if role == "admin":
            courses = Retrieve_Database.get_all_courses()
        else:
            courses = Retrieve_Database.get_courses_for_staff(user.get("email"))
    except Exception as err:
        return jsonify({"error": f"Could not reach the database: {err}"}), 500

    if not courses:
        return jsonify({"error": "There are no courses to export"}), 404

    # Built in memory — these files are small (a few KB each) and this
    # avoids writing temporary files to disk and having to clean them up.
    buffer = io.BytesIO()
    used_names = set()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for course in courses:
            payload = _course_to_json(course)

            # Attach the outline content if this unit has been saved.
            # A missing outline is normal (a new course), not an error.
            try:
                outline = Retrieve_Database.get_doc_by_unit_code(course.code)
            except Exception:
                outline = None

            if outline:
                try:
                    payload["outlineData"] = json.loads(outline.content) if outline.content else {}
                except (ValueError, TypeError):
                    payload["outlineDataRaw"] = outline.content
                payload["outlineVersion"] = outline.version
                payload["outlineLastEditedBy"] = outline.last_edited_by
                payload["outlineLastEditedAt"] = (
                    outline.last_edited_at.isoformat() if outline.last_edited_at else None
                )

            archive.writestr(
                _safe_filename(course.code or f"course-{course.id}", used_names),
                json.dumps(payload, indent=2, ensure_ascii=False),
            )

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"spi-courses-{datetime.now():%Y-%m-%d}.zip",
    )
