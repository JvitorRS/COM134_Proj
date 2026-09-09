"""
editing.py — document editing workflow: create, save, delete, approval, PDF.

Fixed two pre-existing bugs so this module can actually import:
  - `import SPIStaffOutlineSystem` + `class Editing(SPIStaffOutlineSystem)`
    inherited from a module, not a class — invalid Python.
  - `import Retrieve_Database` referenced a module name that doesn't
    exist (the file is retrieve_database.py, lowercase) — fixed to the
    correct import.

ApprovalReq used to be a blocking four-step stub
(receive_request -> send_to_email_team -> receive_email_response ->
send_response_to_frontend) that assumed the email reply comes back
synchronously in the same function call. It doesn't — the coordinator
clicks Approve/Reject in their inbox, possibly hours later, which hits
a route in app.py, not this class. ApprovalReq is now a thin adapter:
kick off the request, then let the caller poll check_status() whenever
it needs to know. SaveDoc and DeleteDoc now actually gate on that
status instead of running unconditionally.

There are no HTTP routes for CreateNewDoc/SaveDoc/DeleteDoc yet (there
weren't any before this rewrite either) — once the frontend/routes for
those exist, they're the ones that would create an ApprovalReq, call
request_approval(), and pass the same instance into SaveDoc.run()/
DeleteDoc.run() once check_status() reports "Approved".
"""

import json

from editing.CreateNewDoc import UnitOutline
from shared.retrieve_database import Retrieve_Database
from email_approval.email_service import send_approval_email


class Editing:
    def __init__(self):
        pass


# Create a temporary blank sheet
class CreateNewDoc(Editing):
    def __init__(self):
        super().__init__()
        # UnitOutline() starts fully blank (same as the original template),
        # so this *is* the "temporary blank sheet" this class is meant to hand off.
        self.outline = UnitOutline()

    def blank_sheet(self):
        """Return the UnitOutline builder so the frontend can fill it in."""
        return self.outline

    def build(self):
        """Assemble the current blank/filled sheet into a python-docx Document."""
        return self.outline.build()

    def save(self, path):
        """Save the current sheet to disk. Returns the path."""
        return self.outline.save(path)


# Receive the alter message and reason [Frontend]
# Sent result to emailteam and force user to wait for response [Email]
# Recieve response: Approval, Rejected, More Info [Email]
# Send response to frontend [Frontend]
class ApprovalReq(Editing):
    def __init__(self, mail):
        super().__init__()
        # `mail` is the Flask-Mail instance from the running app, e.g.
        # current_app.extensions["mail"] inside a route — passed in
        # rather than imported so this class doesn't need app context
        # just to exist.
        self.mail = mail
        self.token = None

    def request_approval(self, unit_code: str, coordinator_email: str, change_summary: list | None = None) -> str:
        """
        [Frontend] -> [Email] Create the approval record and send the
        email. `change_summary` (optional) is a list of
        {section, details, reason} dicts — when the frontend's Request
        a Change form provides them, they get included in the email
        body so the approver sees what's actually being asked for.
        Returns the token to track it by.
        """
        record = Retrieve_Database.create_approval(unit_code=unit_code, coordinator_email=coordinator_email)
        send_approval_email(self.mail, coordinator_email, unit_code, record.token, change_summary=change_summary)
        self.token = record.token
        return self.token

    def check_status(self, token: str = None) -> str | None:
        """[Email] -> [Frontend] Poll the current status: 'Pending', 'Approved', 'Rejected', or None if the token is unknown."""
        token = token or self.token
        record = Retrieve_Database.get_approval(token)
        return record.status if record else None

    def get_reason(self, token: str = None) -> str | None:
        """The rejection (or optional approval) comment, once one exists."""
        token = token or self.token
        record = Retrieve_Database.get_approval(token)
        return record.reason if record else None


# Delete the current sheet
# Delete the current sheet in Database
# Save in History Log
class DeleteDoc(Editing):
    def __init__(self, doc_id):
        super().__init__()
        # doc_id identifies which sheet (row in the Database) this instance acts on.
        self.doc_id = doc_id
        self.deleted = False

    def delete_current_sheet(self):
        """Drop/clear the in-memory working copy of the sheet."""
        # TODO: hook up to whatever holds the "current sheet" in memory
        # (e.g. a CreateNewDoc/SaveDoc instance passed in from the frontend).
        self.deleted = True

    def delete_from_database(self):
        """Remove the sheet's record from the Database via Retrieve_Database.

        STILL NOT WIRED UP — deliberately, not by oversight. The plumbing
        exists (Retrieve_Database.delete_doc / log_history), but the
        schema currently makes "delete the outline AND log the deletion"
        impossible: history_log.unit_outline_id is a FOREIGN KEY to
        unit_outlines(unit_outline_id) with no ON DELETE rule, so
        MySQL blocks deleting an outline that has any history rows, and
        blocks inserting a history row for an outline that's already
        gone. Either order fails.

        Fix the schema first, then this becomes two lines. Pick one:
          - ON DELETE CASCADE  -> deleting an outline wipes its history
                                  too (simple, but loses the audit trail)
          - ON DELETE SET NULL -> history rows survive with a NULL
                                  outline id (keeps the audit trail;
                                  needs unit_outline_id to be nullable)
          - soft delete        -> add a `deleted` flag to unit_outlines
                                  and never actually DELETE the row
                                  (keeps everything, recommended for an
                                  approvals-based system like this one)
        """
        raise NotImplementedError(
            "Blocked on the history_log -> unit_outlines foreign key; see this method's docstring."
        )

    def log_history(self, editor_name, deleted_date):
        """Record the deletion in the History Log [Date / Who / Version]."""
        raise NotImplementedError(
            "Blocked on the same foreign key as delete_from_database(); see its docstring."
        )

    def run(self, editor_name, deleted_date, approval: ApprovalReq):
        """
        Delete the sheet locally, in the Database, then log it — but only
        once `approval` reports the change as Approved. Returns True on
        success.
        """
        if approval.check_status() != "Approved":
            raise PermissionError("Cannot delete: change has not been approved yet.")
        self.delete_current_sheet()
        self.delete_from_database()
        self.log_history(editor_name, deleted_date)
        return self.deleted


# Receive the either the blank sheet from CreateNewDoc or modified sheet from frontend [CreateNewDoc] [Frontend]
# Save in Database with editor's name and edited date [Database]
# Save in History Log [Database]  [Date / Who / Version]
class SaveDoc(Editing):
    """
    Persists a unit outline into the `unit_outlines` table (and records
    the save in `history_log`).

    === The outline content shape ===

    `unit_outlines.content` is a TEXT column, so the outline's fields
    have to be flattened into a single string. This class stores them as
    JSON: a plain object mapping the Unit Outline form's field ids to
    their values, exactly as the frontend's collectOutlineData() builds
    it, e.g.

        {"unit_code": "ICT101", "title": "Intro to Computing",
         "lo1": "...", "assessment1_weight": "20", ...}

    JSON was chosen over the .docx bytes because the frontend has to be
    able to read it straight back into the form when a user reopens the
    outline (see the GET route in editing/routes.py) — a .docx would be
    write-only from the app's point of view. Building the .docx stays
    CreateNewDoc.py's job, done on demand at export/print time from
    these same fields.
    """

    def __init__(self):
        super().__init__()
        self.sheet = None       # the outline being saved (dict of fields, or a UnitOutline)
        self.source = None      # "CreateNewDoc" or "Frontend"
        self.record = None      # the UnitOutlineRecord returned by the last save

    def receive_sheet(self, sheet, source):
        """[CreateNewDoc] [Frontend] Accept either a fresh blank sheet or a frontend-edited one.

        `sheet` may be either:
          - a dict of outline field values (what the frontend posts), or
          - a UnitOutline instance (e.g. CreateNewDoc().outline)

        `source` records where it came from, e.g. "CreateNewDoc" or "Frontend".
        """
        self.sheet = sheet
        self.source = source
        return self

    def _content_json(self) -> str:
        """Serialise the received sheet into the string stored in unit_outlines.content."""
        if isinstance(self.sheet, dict):
            fields = self.sheet
        else:
            # A UnitOutline instance: keep only its data attributes, and
            # drop the ones that are about building the .docx rather
            # than about the outline's content (logo_path), plus sets,
            # which aren't JSON-serialisable on their own.
            fields = {}
            for key, value in vars(self.sheet).items():
                if key == "logo_path":
                    continue
                fields[key] = sorted(value) if isinstance(value, set) else value

        return json.dumps(fields, ensure_ascii=False, default=str)

    def save_to_database(self, editor_name, edited_date=None, unit_code=None, unit_outline_id=None):
        """[Database] Save the sheet's content, tagged with who edited it and when.

        Passing `unit_outline_id` saves a NEW VERSION of that existing
        row (content replaced, version bumped); leaving it None inserts
        a brand-new outline row.

        `edited_date` is accepted for backwards compatibility but is not
        used — save_doc() stamps last_edited_at with the real time of
        the write, so a caller can't back-date a save.

        Returns the UnitOutlineRecord, which carries the new version
        number that log_history() needs.
        """
        if self.sheet is None:
            raise ValueError("No sheet has been received yet; call receive_sheet() first.")

        content = self._content_json()

        # Fall back to the unit code carried inside the sheet itself, so
        # callers that already have a filled-in sheet don't have to
        # repeat it.
        if not unit_code:
            if isinstance(self.sheet, dict):
                unit_code = self.sheet.get("unit_code")
            else:
                unit_code = self.sheet.basic_info.get("Unit Code:")
        if not unit_code:
            raise ValueError("Cannot save an outline without a unit code.")

        self.record = Retrieve_Database.save_doc(
            unit_code=unit_code,
            content=content,
            editor_email=editor_name,
            unit_outline_id=unit_outline_id,
        )
        return self.record

    def log_history(self, editor_name, edited_date=None, version=None):
        """[Database] Append an entry to the History Log: Date / Who / Version.

        Call this after save_to_database() — it uses that save's record
        for the outline id and version. `version` can be passed to
        override it; `edited_date` is ignored for the same reason as
        above (log_history() timestamps the row itself).
        """
        if self.record is None:
            raise ValueError("Nothing has been saved yet; call save_to_database() first.")

        return Retrieve_Database.log_history(
            unit_outline_id=self.record.id,
            action="saved",
            editor_email=editor_name,
            version=version if version is not None else self.record.version,
        )

    def run_direct(self, sheet, source, editor_name, unit_code=None, unit_outline_id=None):
        """
        Receive, persist and log a sheet with NO approval gate — this is
        what the frontend's "Save Outline Changes" button uses.

        Direct saving is deliberate: that button is an authorised editor
        saving their own work, and the approval workflow lives on the
        separate "Request a Change" feature (ApprovalReq + the email
        routes), not on every keystroke-level save. Use run() below
        instead when a save genuinely must wait on an approval.

        Returns the UnitOutlineRecord that was written.
        """
        self.receive_sheet(sheet, source)
        record = self.save_to_database(editor_name, unit_code=unit_code, unit_outline_id=unit_outline_id)
        self.log_history(editor_name)
        return record

    def run(self, sheet, source, editor_name, edited_date, version, approval: ApprovalReq,
            unit_code=None, unit_outline_id=None):
        """
        Receive, persist, and log a sheet — but only once `approval`
        reports the change as Approved.
        """
        if approval.check_status() != "Approved":
            raise PermissionError("Cannot save: change has not been approved yet.")
        self.receive_sheet(sheet, source)
        self.save_to_database(editor_name, edited_date, unit_code=unit_code, unit_outline_id=unit_outline_id)
        self.log_history(editor_name, edited_date, version)
        return self.record


# Call PDF group's function
class PrintPDF(Editing):
    def __init__(self, sheet=None):
        super().__init__()
        # sheet is expected to be a UnitOutline instance (or a built python-docx Document).
        self.sheet = sheet

    def generate_pdf(self, output_path):
        """Hand the sheet off to the PDF group's function and return the resulting path."""
        if self.sheet is None:
            raise ValueError("No sheet set to print; pass one to PrintPDF(sheet=...) first.")
        # TODO (PDF group): e.g.
        # from PDFGroupModule import convert_to_pdf
        # return convert_to_pdf(self.sheet.build(), output_path)
        raise NotImplementedError("Wire up the PDF group's conversion function here")
