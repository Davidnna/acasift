import html
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from flask import current_app


class EmailConfigurationError(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


def email_is_configured():
    return bool(current_app.config.get("MAIL_SERVER") and current_app.config.get("MAIL_DEFAULT_SENDER"))


def _send(to_email, subject, text_body, html_body):
    if not email_is_configured():
        raise EmailConfigurationError("Email delivery is not configured.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    server_name = current_app.config["MAIL_SERVER"]
    port = current_app.config["MAIL_PORT"]
    smtp = None
    try:
        if current_app.config["MAIL_USE_SSL"]:
            smtp = smtplib.SMTP_SSL(server_name, port, timeout=20)
        else:
            smtp = smtplib.SMTP(server_name, port, timeout=20)
            if current_app.config["MAIL_USE_TLS"]:
                smtp.starttls()
        username = current_app.config.get("MAIL_USERNAME")
        if username:
            smtp.login(username, current_app.config.get("MAIL_PASSWORD", ""))
        smtp.send_message(message)
    except (smtplib.SMTPException, OSError) as exc:
        raise EmailDeliveryError("The email provider could not deliver the message.") from exc
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except Exception:
                pass


def send_verification_email(user, raw_token):
    expires = current_app.config["EMAIL_VERIFICATION_HOURS"]
    link = f"{current_app.config['PUBLIC_APP_URL']}/verify-email?{urlencode({'token': raw_token})}"
    name = html.escape(user.first_name or user.full_name)
    safe_link = html.escape(link, quote=True)
    text_body = (
        f"Hello {user.first_name or user.full_name},\n\n"
        "Verify your email address to activate your AcaSift account:\n\n"
        f"{link}\n\nThis link expires in {expires} hours. If you did not create this account, ignore this message.\n\nAcaSift"
    )
    html_body = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#14243d;line-height:1.6">'
        '<h2>Verify your AcaSift email address</h2>'
        f'<p>Hello {name},</p><p>Confirm that you own this email address to activate your AcaSift account.</p>'
        f'<p><a href="{safe_link}" style="display:inline-block;padding:12px 18px;background:#18a999;color:#fff;text-decoration:none;border-radius:8px">Verify email address</a></p>'
        f'<p>This link expires in {expires} hours. If you did not create this account, ignore this message.</p>'
        '<p>AcaSift</p></body></html>'
    )
    _send(user.email, "Verify your AcaSift email address", text_body, html_body)


def send_password_reset_email(user, raw_token):
    expires = current_app.config["PASSWORD_RESET_HOURS"]
    link = f"{current_app.config['PUBLIC_APP_URL']}/reset-password?{urlencode({'token': raw_token})}"
    name = html.escape(user.first_name or user.full_name)
    safe_link = html.escape(link, quote=True)
    text_body = (
        f"Hello {user.first_name or user.full_name},\n\n"
        "A request was made to reset your AcaSift password. Use this one-time link:\n\n"
        f"{link}\n\nThis link expires in {expires} hour(s). If you did not request a reset, ignore this message."
    )
    html_body = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#14243d;line-height:1.6">'
        '<h2>Reset your AcaSift password</h2>'
        f'<p>Hello {name},</p><p>Use the button below to choose a new password.</p>'
        f'<p><a href="{safe_link}" style="display:inline-block;padding:12px 18px;background:#18a999;color:#fff;text-decoration:none;border-radius:8px">Reset password</a></p>'
        f'<p>This link expires in {expires} hour(s). If you did not request this reset, ignore this message.</p>'
        '<p>AcaSift</p></body></html>'
    )
    _send(user.email, "Reset your AcaSift password", text_body, html_body)
