# email_service.py
from flask_mail import Message
from flask import current_app
from shared.retrieve_database import Retrieve_Database


def send_email(mail, recipient, subject, html_body, token=None):
    try:
        s_subject = str(subject).encode('ascii', 'ignore').decode('ascii')
        s_sender = str(current_app.config['MAIL_USERNAME'])

        msg = Message(
            subject=s_subject,
            recipients=[recipient],
            sender=s_sender
        )

        msg.html = html_body
        msg.body = "Please view this email in an HTML-compatible client to see the action buttons."

        mail.send(msg)

        # Log through the shared data layer — this module doesn't own a
        # database, it just records that an email went out.
        Retrieve_Database.log_email_sent(recipient=recipient, subject=s_subject, status="Sent", token=token)

        print(f"Success: HTML Email Sent to {recipient}")
        return True
    except Exception as e:
        print(f"Error occurred: {repr(e)}")
        return False


def _format_change_items(change_summary):
    """Turns [{section, details, reason}, ...] into safe <li> HTML lines."""
    lines = []
    for item in change_summary:
        section = item.get("section", "")
        details = item.get("details", "")
        reason = item.get("reason")
        line = f"<li><strong>{section}:</strong> {details}"
        if reason:
            line += f" — <em>{reason}</em>"
        line += "</li>"
        lines.append(line)
    return "".join(lines)


def send_approval_email(mail, recipient, unit_code, token, change_summary=None):
    base_url = "http://127.0.0.1:5000"
    approve_link = f"{base_url}/approve/{token}"
    reject_link = f"{base_url}/reject/{token}"

    # Optional — populated when this came from the frontend's "Request a
    # Change" form, so the approver sees what's actually being asked for
    # instead of just a bare unit code.
    changes_block = ""
    if change_summary:
        changes_block = f"""
        <div style="background: #ffffff; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #0078d4;">
            <p style="margin:0 0 8px 0; font-size: 15px; font-weight: bold; color: #333;">Requested changes:</p>
            <ul style="margin:0; padding-left: 20px; color: #555; font-size: 14px;">{_format_change_items(change_summary)}</ul>
        </div>
        """

    html_content = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px; border: 1px solid #e0e0e0; border-radius: 8px; background-color: #f9f9f9;">
        <h2 style="color: #333; border-bottom: 2px solid #0078d4; padding-bottom: 10px;">SPI Unit Outline Approval</h2>
        <p style="font-size: 16px; color: #555;">Hello,</p>
        <p style="font-size: 16px; color: #555;">A new unit outline requires your review and action:</p>

        <div style="background: #ffffff; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #0078d4;">
            <p style="margin: 0; font-size: 16px; font-weight: bold; color: #333;">Unit Code: {unit_code}</p>
        </div>

        {changes_block}

        <p style="font-size: 16px; color: #555;">Please click one of the buttons below to proceed:</p>

        <div style="margin: 30px 0;">
            <a href="{approve_link}" style="background-color: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block; margin-right: 15px;">Approve Outline</a>
            <a href="{reject_link}" style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; font-weight: bold; display: inline-block;">Reject Outline</a>
        </div>

        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
        <p style="font-size: 12px; color: #999;">This is an automated message from the SPI Secure Email System.</p>
    </div>
    """

    send_email(mail, recipient, f"Action Required: Approval for Unit {unit_code}", html_content, token=token)
