"""
retrieve_database.py — data-access layer for the SPI Staff Outline System.

Every other module goes through THIS file to read/write persisted data.
No other module should import a database library or hold its own DB
connection directly — that's the whole point of keeping this in one
file.

This version connects to a real MySQL database matching the schema
already agreed with the DB group:

    approvals, email_logs, unit_outlines, history_log, courses,
    staff_course_access

=== SETUP — do this before running anything that imports this file ===

    pip install mysql-connector-python

Then set these environment variables (same pattern as
MAIL_USERNAME/MAIL_PASSWORD elsewhere in this project):

    export DB_HOST="localhost"
    export DB_USER="your_mysql_user"
    export DB_PASSWORD="your_mysql_password"
    export DB_NAME="spi_outline_system"

If any of these aren't set, connecting fails immediately with a clear
message (see _get_connection() below) instead of failing confusingly
deep inside a query.

=== How connections work here ===

Every method opens its own short-lived connection, runs one query,
and closes it. That's simple and correct for a small app like this.
If this ever needs to handle real concurrent load, switch to a
connection pool (mysql.connector.pooling) instead — not needed yet,
don't add it pre-emptively.

=== Method map — where each table is used ===

    approvals              -> create_approval, get_approval, update_approval_status
    email_logs             -> log_email_sent, update_email_log_status, get_all_email_logs
    unit_outlines          -> save_doc, get_doc, delete_doc   (NOT wired up to editing.py yet — see note below)
    history_log            -> log_history                     (NOT wired up to editing.py yet — see note below)
    courses                -> get_all_courses, get_course, create_course, update_course, delete_course  (wired to dashboard.py)
    staff_course_access    -> get_courses_for_staff                                                       (wired to dashboard.py)

The approvals/email_logs methods are already called by ApprovalReq
(editing.py) and the email routes (app.py) — those work as-is, no
other file needs to change for them.

The unit_outlines/history_log methods are new and ready to use, but
nothing calls them yet: editing.py's SaveDoc.save_to_database /
DeleteDoc.delete_from_database / their log_history() methods still
raise NotImplementedError — swap those for calls to save_doc() /
delete_doc() / log_history() below when you're ready to wire that up
(still waiting on the editing group's decision on outline content
shape).

The courses/staff_course_access methods ARE wired up now — see
dashboard.py's /dashboard/api/courses routes.
"""

import os
import uuid
from dataclasses import dataclass
from datetime import date, datetime

import mysql.connector


def _get_connection():
    """
    Opens one MySQL connection using DB_HOST / DB_USER / DB_PASSWORD /
    DB_NAME environment variables. Raises immediately, with a clear
    message, if any are missing.
    """
    required = ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"Missing database environment variable(s): {', '.join(missing)}. "
            f"Set them before running the app — see the SETUP comment at "
            f"the top of retrieve_database.py."
        )

    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
    )


# ---------------------------------------------------------------------------
# Shared data shapes returned to callers. These field names matter more
# than the MySQL column names — other files (ApprovalReq, email_service.py,
# app.py's routes) read attributes like `record.status` or `log.id`, so
# these stay the same even though some underlying columns are named
# differently (e.g. `email_log_id` instead of `id`) — see the `AS id`
# aliases in the SELECT queries below, that's what keeps this consistent.
# ---------------------------------------------------------------------------
@dataclass
class ApprovalRecord:
    token: str
    unit_code: str
    coordinator_email: str
    status: str
    reason: str | None
    created_at: datetime


@dataclass
class EmailLogRecord:
    id: int
    recipient: str
    subject: str
    status: str
    token: str | None
    action_status: str
    rejection_reason: str | None
    sent_at: datetime


@dataclass
class UnitOutlineRecord:
    id: int
    unit_code: str
    content: str
    last_edited_by: str
    last_edited_at: datetime
    version: int


@dataclass
class HistoryLogRecord:
    id: int
    unit_outline_id: int
    action: str
    editor_email: str
    edited_at: datetime
    version: int


@dataclass
class CourseRecord:
    id: int
    code: str
    name: str
    semester: str
    start_date: date
    description: str


class Retrieve_Database:
    """
    Real MySQL-backed data-access layer. Every method opens its own
    connection, runs one query, and closes it — see _get_connection().

    NOTE: intentionally does not inherit from SPIStaffOutlineSystem.
    The old `import SPIStaffOutlineSystem` + `class X(SPIStaffOutlineSystem)`
    pattern used to exist across this codebase and was invalid Python
    (it inherited from a module, not a class) — already removed
    everywhere else, kept removed here too.
    """

    # ======================================================================
    # approvals
    # ======================================================================

    @classmethod
    def create_approval(cls, unit_code: str, coordinator_email: str) -> ApprovalRecord:
        """Create a new pending approval request and return it (with its token)."""
        token = str(uuid.uuid4())
        created_at = datetime.now()

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO approvals (token, unit_code, coordinator_email, status, reason, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (token, unit_code, coordinator_email, "Pending", None, created_at),
            )
            conn.commit()
        finally:
            conn.close()

        return ApprovalRecord(
            token=token,
            unit_code=unit_code,
            coordinator_email=coordinator_email,
            status="Pending",
            reason=None,
            created_at=created_at,
        )

    @classmethod
    def get_approval(cls, token: str) -> ApprovalRecord | None:
        """Look up an approval request by its token."""
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT token, unit_code, coordinator_email, status, reason, created_at "
                "FROM approvals WHERE token = %s",
                (token,),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        if row is None:
            return None
        return ApprovalRecord(**row)

    @classmethod
    def update_approval_status(cls, token: str, status: str, reason: str | None = None) -> ApprovalRecord | None:
        """Mark an approval request Approved/Rejected. Returns the updated record, or None if the token is unknown."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE approvals SET status = %s, reason = %s WHERE token = %s",
                (status, reason, token),
            )
            conn.commit()
            updated = cursor.rowcount > 0
        finally:
            conn.close()

        if not updated:
            return None
        return cls.get_approval(token)

    # ======================================================================
    # email_logs
    # ======================================================================

    @classmethod
    def log_email_sent(cls, recipient: str, subject: str, status: str, token: str | None = None) -> EmailLogRecord:
        """Record that an email was (or wasn't) sent."""
        sent_at = datetime.now()

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO email_logs (recipient, subject, status, token, action_status, rejection_reason, sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (recipient, subject, status, token, "Pending", None, sent_at),
            )
            conn.commit()
            new_id = cursor.lastrowid
        finally:
            conn.close()

        return EmailLogRecord(
            id=new_id,
            recipient=recipient,
            subject=subject,
            status=status,
            token=token,
            action_status="Pending",
            rejection_reason=None,
            sent_at=sent_at,
        )

    @classmethod
    def _get_email_log_by_token(cls, token: str) -> EmailLogRecord | None:
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT email_log_id AS id, recipient, subject, status, token, "
                "action_status, rejection_reason, sent_at "
                "FROM email_logs WHERE token = %s",
                (token,),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        return EmailLogRecord(**row) if row else None

    @classmethod
    def update_email_log_status(cls, token: str, action_status: str, rejection_reason: str | None = None) -> EmailLogRecord | None:
        """Update an email log entry's action_status once the coordinator approves/rejects."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE email_logs SET action_status = %s, rejection_reason = %s WHERE token = %s",
                (action_status, rejection_reason, token),
            )
            conn.commit()
            updated = cursor.rowcount > 0
        finally:
            conn.close()

        if not updated:
            return None
        return cls._get_email_log_by_token(token)

    @classmethod
    def get_all_email_logs(cls) -> list[EmailLogRecord]:
        """Most recent first — matches what the /logs page expects."""
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT email_log_id AS id, recipient, subject, status, token, "
                "action_status, rejection_reason, sent_at "
                "FROM email_logs ORDER BY email_log_id DESC"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [EmailLogRecord(**row) for row in rows]

    # ======================================================================
    # unit_outlines / history_log
    # Not called anywhere yet — see the module docstring above for what
    # still needs wiring up in editing.py.
    # ======================================================================

    @classmethod
    def save_doc(
        cls,
        unit_code: str,
        content: str,
        editor_email: str,
        unit_outline_id: int | None = None,
    ) -> UnitOutlineRecord:
        """
        Create a new outline document (unit_outline_id=None), or save a
        new version of an existing one (unit_outline_id given).

        `content` should be a JSON string (or plain text) of the
        outline's actual fields — how that gets built from a UnitOutline
        object (CreateNewDoc.py) is that file's job, not this one's.
        This method just stores whatever string it's given.
        """
        edited_at = datetime.now()

        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)

            if unit_outline_id is None:
                cursor.execute(
                    """
                    INSERT INTO unit_outlines (unit_code, content, last_edited_by, last_edited_at, version)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (unit_code, content, editor_email, edited_at, 1),
                )
                conn.commit()
                unit_outline_id = cursor.lastrowid
                version = 1
            else:
                cursor.execute(
                    "SELECT version FROM unit_outlines WHERE unit_outline_id = %s",
                    (unit_outline_id,),
                )
                row = cursor.fetchone()
                version = (row["version"] + 1) if row else 1

                cursor.execute(
                    """
                    UPDATE unit_outlines
                    SET content = %s, last_edited_by = %s, last_edited_at = %s, version = %s
                    WHERE unit_outline_id = %s
                    """,
                    (content, editor_email, edited_at, version, unit_outline_id),
                )
                conn.commit()
        finally:
            conn.close()

        return UnitOutlineRecord(
            id=unit_outline_id,
            unit_code=unit_code,
            content=content,
            last_edited_by=editor_email,
            last_edited_at=edited_at,
            version=version,
        )

    @classmethod
    def get_doc(cls, unit_outline_id: int) -> UnitOutlineRecord | None:
        """Look up a single outline document by its ID."""
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT unit_outline_id AS id, unit_code, content, last_edited_by, last_edited_at, version "
                "FROM unit_outlines WHERE unit_outline_id = %s",
                (unit_outline_id,),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        return UnitOutlineRecord(**row) if row else None

    @classmethod
    def delete_doc(cls, unit_outline_id: int) -> bool:
        """Delete an outline document by its ID. Returns True if a row was actually deleted."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM unit_outlines WHERE unit_outline_id = %s", (unit_outline_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        finally:
            conn.close()

        return deleted

    @classmethod
    def log_history(cls, unit_outline_id: int, action: str, editor_email: str, version: int) -> HistoryLogRecord:
        """Record a save/delete event. `action` should be 'saved' or 'deleted'."""
        edited_at = datetime.now()

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO history_log (unit_outline_id, action, editor_email, edited_at, version)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (unit_outline_id, action, editor_email, edited_at, version),
            )
            conn.commit()
            new_id = cursor.lastrowid
        finally:
            conn.close()

        return HistoryLogRecord(
            id=new_id,
            unit_outline_id=unit_outline_id,
            action=action,
            editor_email=editor_email,
            edited_at=edited_at,
            version=version,
        )

    # ======================================================================
    # courses / staff_course_access
    # Not called anywhere yet — dashboard.py is still a placeholder route.
    # ======================================================================

    @classmethod
    def get_all_courses(cls) -> list[CourseRecord]:
        """Every course — what an Administrator sees on the dashboard."""
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT course_id AS id, code, name, semester, start_date, description FROM courses"
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [CourseRecord(**row) for row in rows]

    @classmethod
    def get_courses_for_staff(cls, staff_email: str) -> list[CourseRecord]:
        """Only the courses a given logged-in user has access to (via staff_course_access)."""
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT c.course_id AS id, c.code, c.name, c.semester, c.start_date, c.description
                FROM courses c
                JOIN staff_course_access sca ON sca.course_id = c.course_id
                WHERE sca.staff_email = %s
                """,
                (staff_email,),
            )
            rows = cursor.fetchall()
        finally:
            conn.close()

        return [CourseRecord(**row) for row in rows]

    @classmethod
    def get_course(cls, course_id: int) -> CourseRecord | None:
        """Look up a single course by its ID."""
        conn = _get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT course_id AS id, code, name, semester, start_date, description "
                "FROM courses WHERE course_id = %s",
                (course_id,),
            )
            row = cursor.fetchone()
        finally:
            conn.close()

        return CourseRecord(**row) if row else None

    @classmethod
    def create_course(cls, code: str, name: str, semester: str, start_date, description: str) -> CourseRecord:
        """Add a new course to the master list. Used by the Admin 'Add Course' button."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO courses (code, name, semester, start_date, description)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (code, name, semester, start_date, description),
            )
            conn.commit()
            new_id = cursor.lastrowid
        finally:
            conn.close()

        return CourseRecord(id=new_id, code=code, name=name, semester=semester, start_date=start_date, description=description)

    @classmethod
    def update_course(cls, course_id: int, **fields) -> CourseRecord | None:
        """
        Update one or more fields of an existing course. `fields` may
        include any of: code, name, semester, start_date, description.
        Only the keys actually passed are updated. Returns the updated
        record, or None if course_id doesn't exist.
        """
        allowed_columns = {"code", "name", "semester", "start_date", "description"}
        updates = {column: value for column, value in fields.items() if column in allowed_columns}
        if not updates:
            return cls.get_course(course_id)

        set_clause = ", ".join(f"{column} = %s" for column in updates)
        values = list(updates.values()) + [course_id]

        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE courses SET {set_clause} WHERE course_id = %s", values)
            conn.commit()
            updated = cursor.rowcount > 0
        finally:
            conn.close()

        if not updated:
            return None
        return cls.get_course(course_id)

    @classmethod
    def delete_course(cls, course_id: int) -> bool:
        """Delete a course. Returns True if a row was actually deleted."""
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM courses WHERE course_id = %s", (course_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        finally:
            conn.close()

        return deleted
