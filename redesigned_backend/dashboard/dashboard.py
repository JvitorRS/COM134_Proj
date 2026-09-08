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

from flask import Blueprint, request, jsonify

from shared.retrieve_database import Retrieve_Database
from auth.login import SessionManager, UserRole

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


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

    if role == "admin":
        courses = Retrieve_Database.get_all_courses()
    else:
        courses = Retrieve_Database.get_courses_for_staff(user.get("email"))

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

    course = Retrieve_Database.create_course(
        code=code,
        name=name,
        semester=data.get("semester", ""),
        start_date=data.get("startDate") or None,
        description=data.get("description", ""),
    )
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

    course = Retrieve_Database.update_course(course_id, **fields)
    if not course:
        return jsonify({"error": "Course not found"}), 404
    return jsonify(_course_to_json(course))


@dashboard_bp.route("/api/courses/<int:course_id>", methods=["DELETE"])
def api_delete_course(course_id):
    denied = _require_admin()
    if denied:
        return denied

    deleted = Retrieve_Database.delete_course(course_id)
    if not deleted:
        return jsonify({"error": "Course not found"}), 404
    return jsonify({"deleted": True})
