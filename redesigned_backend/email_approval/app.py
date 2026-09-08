"""
app.py — email approval routes, as a Flask Blueprint.

No longer the app's entry point (that's SPIStaffOutlineSystem.py now)
and no longer owns a database (that's retrieve_database.py). This file
just serves the manual test-send form, the /approve and /reject links
from the email, and the /logs view.

"/" used to be a placeholder home page owned by this blueprint — it's
now owned by frontend.py instead, since there's a real frontend
(index_1.html) to serve there. /test-create, /logs, /approve, /reject
are still reachable directly at those paths; nothing links to the old
placeholder anymore.

Kept the filename `app.py` since it's one of the three files you asked
to keep — just repurposed as a Blueprint module instead of a
standalone `Flask(__name__)` app.
"""

from flask import Blueprint, request, current_app, jsonify

from shared.retrieve_database import Retrieve_Database
from email_approval.email_service import send_approval_email
from editing.editing import ApprovalReq

email_bp = Blueprint("email", __name__)


@email_bp.route("/api/change-requests", methods=["POST"])
def api_create_change_request():
    """
    What the frontend's "Request a Change" form (script.js's
    submitChangeRequest()) actually calls. Creates a real approval
    record and sends the real email — this IS the "Request a Change"
    feature now, not a separate local simulation.
    """
    data = request.get_json(silent=True) or {}
    unit_code = (data.get("unit_code") or "").strip()
    coordinator_email = (data.get("coordinator_email") or "").strip()
    items = data.get("items") or []

    if not unit_code or not coordinator_email:
        return jsonify({"error": "unit_code and coordinator_email are required"}), 400

    mail = current_app.extensions["mail"]
    approval = ApprovalReq(mail)
    token = approval.request_approval(unit_code, coordinator_email, change_summary=items)

    return jsonify({"token": token, "status": "Pending"}), 201


@email_bp.route("/api/change-requests/<token>", methods=["GET"])
def api_get_change_request_status(token):
    """
    Polled by the frontend's Change Requests screen so a request's
    status reflects what actually happened when the approver clicked
    Approve/Reject in their email — not a manual in-app override.
    """
    record = Retrieve_Database.get_approval(token)
    if not record:
        return jsonify({"error": "Unknown token"}), 404
    return jsonify({"status": record.status, "reason": record.reason})


@email_bp.route("/test-create", methods=["GET", "POST"])
def test_create_outline():
    if request.method == "POST":
        target_email = request.form.get("email", "").strip()
        unit_code = request.form.get("unit_code", "").strip()

        if not target_email or not unit_code:
            return "<h3>❌ Error: Both Email and Unit Code are required!</h3><p><a href='/test-create'>Go Back</a></p>"

        mail = current_app.extensions["mail"]
        record = Retrieve_Database.create_approval(unit_code=unit_code, coordinator_email=target_email)
        send_approval_email(mail, target_email, record.unit_code, record.token)

        return f"""
        <div style="font-family: Arial; max-width: 500px; margin: 40px auto;">
            <h3 style="color: #28a745;">✅ Success! Approval email sent to {target_email} for Unit {unit_code}.</h3>
            <p><a href="/test-create">Send Another</a> | <a href="/logs">View Email Logs</a> | <a href="/">Home</a></p>
        </div>
        """

    return '''
    <div style="font-family: Arial; max-width: 500px; margin: 40px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
        <h2>SPI Outline Test Sender</h2>
        <form method="POST">
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: bold;">Unit Code:</label>
                <input name="unit_code" placeholder="e.g. COM124, IT_PROJ1" style="width: 100%; padding: 8px; box-sizing: border-box;" required>
            </div>
            <div style="margin-bottom: 15px;">
                <label style="display: block; margin-bottom: 5px; font-weight: bold;">Coordinator Email:</label>
                <input name="email" type="email" placeholder="Recipient Email" style="width: 100%; padding: 8px; box-sizing: border-box;" required>
            </div>
            <button type="submit" style="background-color: #0078d4; color: white; padding: 10px 20px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">Send HTML Approval Email</button>
        </form>
        <p style="margin-top: 20px;"><a href="/logs">View Email Logs</a> | <a href="/">Home</a></p>
    </div>
    '''


@email_bp.route("/logs")
def view_logs():
    logs = Retrieve_Database.get_all_email_logs()

    rows_html = ""
    for log in logs:
        status_color = "#6c757d"
        if log.action_status == "Approved":
            status_color = "#28a745"
        elif log.action_status == "Rejected":
            status_color = "#dc3545"

        reason_display = f"Reason: {log.rejection_reason}" if log.rejection_reason else "-"

        rows_html += f"""
        <tr>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{log.id}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{log.recipient}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{log.subject}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; color: {status_color}; font-weight: bold;">{log.action_status}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd; font-size: 13px; color: #555;">{reason_display}</td>
            <td style="padding: 10px; border-bottom: 1px solid #ddd;">{log.sent_at}</td>
        </tr>
        """

    return f"""
    <div style="font-family: Arial; max-width: 950px; margin: 40px auto;">
        <h2>Email Sending & Approval History (Logs)</h2>
        <p><a href="/test-create">Send New Email</a> | <a href="/">Home</a></p>
        <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
            <thead>
                <tr style="background-color: #f2f2f2; text-align: left;">
                    <th style="padding: 10px; border-bottom: 2px solid #ddd;">ID</th>
                    <th style="padding: 10px; border-bottom: 2px solid #ddd;">Recipient</th>
                    <th style="padding: 10px; border-bottom: 2px solid #ddd;">Subject</th>
                    <th style="padding: 10px; border-bottom: 2px solid #ddd;">Action Status</th>
                    <th style="padding: 10px; border-bottom: 2px solid #ddd;">Details / Reason</th>
                    <th style="padding: 10px; border-bottom: 2px solid #ddd;">Sent Time</th>
                </tr>
            </thead>
            <tbody>
                {rows_html if rows_html else '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #777;">No email logs found yet.</td></tr>'}
            </tbody>
        </table>
    </div>
    """


@email_bp.route("/approve/<string:token>", methods=["GET"])
def approve_outline(token):
    record = Retrieve_Database.get_approval(token)
    if not record:
        return "<h3>❌ Invalid or expired token.</h3>", 404

    Retrieve_Database.update_approval_status(token, "Approved")
    Retrieve_Database.update_email_log_status(token, "Approved")

    return f"""
    <div style="text-align: center; margin-top: 50px; font-family: Arial;">
        <h1 style="color: #28a745;">✅ Outline Approved Successfully!</h1>
        <p>Unit Code: <b>{record.unit_code}</b> has been approved.</p>
        <p><a href="/logs">View Updated System Logs</a></p>
    </div>
    """


@email_bp.route("/reject/<string:token>", methods=["GET", "POST"])
def reject_outline(token):
    record = Retrieve_Database.get_approval(token)
    if not record:
        return "<h3>❌ Invalid or expired token.</h3>", 404

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()

        Retrieve_Database.update_approval_status(token, "Rejected", reason)
        Retrieve_Database.update_email_log_status(token, "Rejected", reason)

        return f"""
        <div style="text-align: center; margin-top: 50px; font-family: Arial;">
            <h1 style="color: #dc3545;">❌ Outline Rejected</h1>
            <p>Unit Code: <b>{record.unit_code}</b> has been rejected.</p>
            <p style="background: #fff3f3; display: inline-block; padding: 10px 20px; border: 1px solid #ffcdd2; border-radius: 4px;">
                <b>Rejection Reason:</b> {reason}
            </p>
            <p style="margin-top: 20px;"><a href="/logs">View Updated System Logs</a></p>
        </div>
        """

    return f"""
    <div style="max-width: 500px; margin: 50px auto; font-family: Arial; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
        <h2 style="color: #dc3545;">Reject Unit Outline</h2>
        <p>Unit Code: <b>{record.unit_code}</b></p>
        <form method="POST">
            <label style="display: block; margin-bottom: 8px; font-weight: bold;">Please provide the reason for rejection:</label>
            <textarea name="reason" rows="4" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;" required placeholder="Enter reasons here..."></textarea>
            <br><br>
            <button type="submit" style="background-color: #dc3545; color: white; padding: 10px 20px; border: none; border-radius: 4px; font-weight: bold; cursor: pointer;">Submit Rejection</button>
        </form>
    </div>
    """
