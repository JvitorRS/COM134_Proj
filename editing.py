import SPIStaffOutlineSystem
import Retrieve_Database
from CreateNewDoc import UnitOutline

class Editing(SPIStaffOutlineSystem):
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
        # TODO: replace with the real Retrieve_Database call, e.g.
        # Retrieve_Database.delete(self.doc_id)
        raise NotImplementedError("Wire up Retrieve_Database.delete(...) here")

    def log_history(self, editor_name, deleted_date):
        """Record the deletion in the History Log [Date / Who / Version]."""
        # TODO: replace with the real Retrieve_Database / History Log call, e.g.
        # Retrieve_Database.log_history(self.doc_id, editor_name, deleted_date, action="deleted")
        raise NotImplementedError("Wire up the History Log call here")

    def run(self, editor_name, deleted_date):
        """Delete the sheet locally, in the Database, then log it. Returns True on success."""
        self.delete_current_sheet()
        self.delete_from_database()
        self.log_history(editor_name, deleted_date)
        return self.deleted


# Receive the alter message and reason [Frontend]
# Sent result to emailteam and force user to wait for response [Email]
# Recieve response: Approval, Rejected, More Info [Email]
# Send response to frontend [Frontend]
class ApprovalReq(Editing):
    #: Possible outcomes of an approval request.
    RESPONSES = ("Approval", "Rejected", "More Info")

    def __init__(self):
        super().__init__()
        self.message = None
        self.reason = None
        self.response = None  # one of RESPONSES once set

    def receive_request(self, message, reason):
        """[Frontend] Receive the alter message and reason from the frontend."""
        self.message = message
        self.reason = reason
        return self

    def send_to_email_team(self):
        """[Email] Send the request to the email team and block until a response arrives."""
        # TODO: replace with the real email integration, e.g.
        # Email.send(to="editteam@spi.nsw.edu.au", subject="Alteration request",
        #            body=f"{self.message}\n\nReason: {self.reason}")
        raise NotImplementedError("Wire up the outgoing email call here")

    def receive_email_response(self):
        """[Email] Receive the email team's decision: Approval, Rejected, or More Info."""
        # TODO: replace with the real inbound-email/polling logic, e.g.
        # self.response = Email.wait_for_reply(...)
        raise NotImplementedError("Wire up the inbound email response here")

    def send_response_to_frontend(self):
        """[Frontend] Forward the decision back to the frontend."""
        if self.response not in self.RESPONSES:
            raise ValueError(f"No valid response to send yet: {self.response!r}")
        # TODO: replace with the real frontend notification call, e.g.
        # Frontend.notify(status=self.response)
        raise NotImplementedError("Wire up the outgoing frontend notification here")

    def run(self, message, reason):
        """Walk through the full approval cycle and return the final response."""
        self.receive_request(message, reason)
        self.send_to_email_team()
        self.receive_email_response()
        self.send_response_to_frontend()
        return self.response


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
        # TODO: replace with the real Retrieve_Database call, e.g.
        # Retrieve_Database.save(self.sheet, editor=editor_name, edited_date=edited_date)
        raise NotImplementedError("Wire up Retrieve_Database.save(...) here")

    def log_history(self, editor_name, edited_date, version):
        """[Database] Append an entry to the History Log: Date / Who / Version."""
        # TODO: replace with the real History Log call, e.g.
        # Retrieve_Database.log_history(self.sheet, editor_name, edited_date, version)
        raise NotImplementedError("Wire up the History Log call here")

    def run(self, sheet, source, editor_name, edited_date, version):
        """Receive, persist, and log a sheet in one call."""
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
        # TODO: replace with the actual PDF group call, e.g.
        # from PDFGroupModule import convert_to_pdf
        # return convert_to_pdf(self.sheet.build(), output_path)
        raise NotImplementedError("Wire up the PDF group's conversion function here")
    def __init__(self):
        pass