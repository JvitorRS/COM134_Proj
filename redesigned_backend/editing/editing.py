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
        """Remove the sheet's record from the Database via Retrieve_Database."""
        # TODO (DB group): retrieve_database.py only has approval/email-log
        # methods right now — needs a real doc-delete method once the DB
        # group's document schema exists, e.g. Retrieve_Database.delete_doc(self.doc_id)
        raise NotImplementedError("Wire up Retrieve_Database.delete_doc(...) here")

    def log_history(self, editor_name, deleted_date):
        """Record the deletion in the History Log [Date / Who / Version]."""
        # TODO (DB group): e.g.
        # Retrieve_Database.log_history(self.doc_id, editor_name, deleted_date, action="deleted")
        raise NotImplementedError("Wire up the History Log call here")

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
    def __init__(self):
        super().__init__()
        self.sheet = None       # the UnitOutline instance being saved
        self.source = None      # "CreateNewDoc" or "Frontend"

    def receive_sheet(self, sheet, source):
        """[CreateNewDoc] [Frontend] Accept either a fresh blank sheet or a frontend-edited one.

        `sheet` is expected to be a UnitOutline instance (e.g. CreateNewDoc().outline,
        or one rebuilt from frontend-submitted field values). `source` records where
        it came from, e.g. "CreateNewDoc" or "Frontend".
        """
        self.sheet = sheet
        self.source = source
        return self

    def save_to_database(self, editor_name, edited_date):
        """[Database] Save the sheet's content, tagged with who edited it and when."""
        if self.sheet is None:
            raise ValueError("No sheet has been received yet; call receive_sheet() first.")
        # TODO (DB group): needs a real doc-save method once the DB
        # group's document schema exists, e.g.
        # Retrieve_Database.save_doc(self.sheet, editor=editor_name, edited_date=edited_date)
        raise NotImplementedError("Wire up Retrieve_Database.save_doc(...) here")

    def log_history(self, editor_name, edited_date, version):
        """[Database] Append an entry to the History Log: Date / Who / Version."""
        # TODO (DB group): e.g.
        # Retrieve_Database.log_history(self.sheet, editor_name, edited_date, version)
        raise NotImplementedError("Wire up the History Log call here")

    def run(self, sheet, source, editor_name, edited_date, version, approval: ApprovalReq):
        """
        Receive, persist, and log a sheet — but only once `approval`
        reports the change as Approved.
        """
        if approval.check_status() != "Approved":
            raise PermissionError("Cannot save: change has not been approved yet.")
        self.receive_sheet(sheet, source)
        self.save_to_database(editor_name, edited_date)
        self.log_history(editor_name, edited_date, version)
        return self.sheet


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
