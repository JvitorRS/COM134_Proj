# email_service.py
import os
from html import escape

from flask_mail import Message
from flask import current_app
from shared.retrieve_database import Retrieve_Database


class EmailSendError(Exception):
    """
    Raised when an approval email could not be sent.

    This exists because the old version of send_email() caught every
    exception, printed it to the terminal, and returned False — and
    send_approval_email() then ignored that return value entirely. The
    result was that a failed send looked identical to a successful one
    from the caller's point of view, and the only trace was a line in a
    terminal nobody was watching. A change request would be created,
    the user would be told it was submitted, and no email would ever
    arrive. Failing loudly is the whole point of this class.
    """


def send_email(mail, recipient, subject, html_body, token=None):
    """
    Send one HTML email and record it in the email log.

    Raises EmailSendError if the send fails, with the underlying reason
    in the message. Callers are expected to let that propagate so the
    user finds out.
    """
    s_subject = str(subject).encode('ascii', 'ignore').decode('ascii')
    s_sender = str(current_app.config.get('MAIL_USERNAME') or "")

    # Checked before trying to connect, so a missing password produces
    # "the mail account isn't configured" instead of an SMTP
    # authentication error that reads like a wrong password.
    if not s_sender or not current_app.config.get('MAIL_PASSWORD'):
        raise EmailSendError(
            "The mail account is not configured — set MAIL_USERNAME and MAIL_PASSWORD "
            "in your .env file. For Gmail, MAIL_PASSWORD must be a 16-character App "
            "Password, not your normal account password."
        )

    msg = Message(subject=s_subject, recipients=[recipient], sender=s_sender)
    msg.html = html_body
    msg.body = "Please view this email in an HTML-compatible client to see the action buttons."

    try:
        mail.send(msg)
    except Exception as err:
        # Record the failed attempt too, so /logs shows what was tried
        # and didn't arrive — not just the successes. Wrapped in its own
        # try/except because if the DATABASE is what's broken, that must
        # not replace the real mail error with a database one.
        try:
            Retrieve_Database.log_email_sent(
                recipient=recipient, subject=s_subject, status=f"Failed: {err}", token=token
            )
        except Exception:
            pass
        raise EmailSendError(f"Sending the email failed: {err}") from err

    # The email is genuinely gone at this point. If the log write fails
    # after that, that's a database problem, not a mail one — don't tell
    # the user their email wasn't sent when it was.
    try:
        Retrieve_Database.log_email_sent(
            recipient=recipient, subject=s_subject, status="Sent", token=token
        )
    except Exception as err:
        print(f"WARNING: email to {recipient} was sent, but logging it failed: {err!r}")

    print(f"Success: HTML Email Sent to {recipient}")
    return True


def _format_change_items(change_summary):
    """
    Turns [{section, details, reason}, ...] into <li> HTML lines.

    Every value is HTML-escaped. These strings come from a form the user
    typed into, so without escaping, a change description containing
    "<" or "&" would break the email's markup — and anything that looks
    like a tag would be interpreted as one by the mail client.
    """
    lines = []
    for item in change_summary:
        section = escape(str(item.get("section", "")))
        details = escape(str(item.get("details", "")))
        reason = item.get("reason")
        line = f"<li><strong>{section}:</strong> {details}"
        if reason:
            line += f" — <em>{escape(str(reason))}</em>"
        line += "</li>"
        lines.append(line)
    return "".join(lines)


def send_approval_email(mail, recipient, unit_code, token, change_summary=None):
    """
    Build and send the approval email. Raises EmailSendError on failure
    (see send_email) — the caller must not treat a failure as success.
    """
    # Was hardcoded to 127.0.0.1:5000, which meant the Approve/Reject
    # links in the email only worked for someone sitting at the same
    # machine that ran the server. Set APP_BASE_URL in .env once this
    # is hosted anywhere real; the default keeps local testing working.
    base_url = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
    approve_link = f"{base_url}/approve/{token}"
    reject_link = f"{base_url}/reject/{token}"
    unit_code = escape(str(unit_code))

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

    # No try/except here on purpose: if this fails, EmailSendError must
    # reach the route so the user is told the email didn't go out.
    return send_email(mail, recipient, f"Action Required: Approval for Unit {unit_code}", html_content, token=token)
