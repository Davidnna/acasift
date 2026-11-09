import html
import json
import re
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from flask import current_app


class EmailConfigurationError(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _sender_for(purpose):
    domain = str(current_app.config.get("NYLAS_SENDING_DOMAIN", "")).strip().lower()
    brand_name = str(current_app.config.get("NYLAS_FROM_NAME", "AcaSift")).strip() or "AcaSift"
    if purpose == "verification":
        address = current_app.config.get("NYLAS_FROM_EMAIL_VERIFICATION", "")
        display_name = f"{brand_name} Account Verification"
    elif purpose == "password_reset":
        address = current_app.config.get("NYLAS_FROM_EMAIL_PASSWORD_RESET", "")
        display_name = f"{brand_name} Security"
    elif purpose == "notification":
        address = current_app.config.get("NYLAS_FROM_EMAIL_NOTIFICATION", "")
        display_name = f"{brand_name} Notifications"
    else:
        raise EmailConfigurationError("An unsupported AcaSift email purpose was requested.")

    address = str(address).strip().lower()
    if not domain or not _EMAIL_RE.fullmatch(address):
        raise EmailConfigurationError("The Nylas sending domain or sender address is invalid.")
    if address.rsplit("@", 1)[1] != domain:
        raise EmailConfigurationError(
            "Every AcaSift sender address must use the configured Nylas sending domain."
        )
    return {"name": display_name, "email": address}


def email_is_configured():
    api_key = str(current_app.config.get("NYLAS_API_KEY", "")).strip()
    api_uri = str(current_app.config.get("NYLAS_API_URI", "")).strip()
    domain = str(current_app.config.get("NYLAS_SENDING_DOMAIN", "")).strip().lower()
    parsed = urlsplit(api_uri)
    if not api_key or not domain or parsed.scheme != "https" or not parsed.netloc:
        return False
    try:
        _sender_for("verification")
        _sender_for("password_reset")
    except EmailConfigurationError:
        return False
    return True


def _send(to_email, recipient_name, subject, html_body, purpose):
    if not email_is_configured():
        raise EmailConfigurationError(
            "Nylas email delivery is not configured. Check the NYLAS_* environment variables."
        )

    api_uri = current_app.config["NYLAS_API_URI"].rstrip("/")
    domain = quote(current_app.config["NYLAS_SENDING_DOMAIN"], safe="")
    endpoint = f"{api_uri}/v3/domains/{domain}/messages/send"
    sender = _sender_for(purpose)

    payload = {
        "to": [{
            "email": to_email,
            **({"name": recipient_name} if recipient_name else {}),
        }],
        "from": sender,
        "subject": subject,
        "body": html_body,
        "is_plaintext": False,
    }

    reply_to = str(current_app.config.get("NYLAS_REPLY_TO", "")).strip()
    if reply_to:
        if not _EMAIL_RE.fullmatch(reply_to):
            raise EmailConfigurationError("NYLAS_REPLY_TO must be a valid email address.")
        payload["reply_to"] = [{"email": reply_to, "name": "AcaSift Support"}]

    api_request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {current_app.config['NYLAS_API_KEY']}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )

    timeout = int(current_app.config.get("NYLAS_API_TIMEOUT", 20))
    try:
        with urlopen(api_request, timeout=timeout) as response:
            response_body = response.read()
            if response.status < 200 or response.status >= 300:
                raise EmailDeliveryError("Nylas did not accept the email.")
            result = json.loads(response_body.decode("utf-8")) if response_body else {}
            message_id = (result.get("data") or {}).get("message_id")
            current_app.logger.info(
                "Nylas accepted AcaSift %s email; message_id=%s",
                purpose,
                message_id or "not-returned",
            )
            return result
    except HTTPError as exc:
        provider_body = exc.read().decode("utf-8", errors="replace")[:1200]
        request_id = None
        try:
            provider_data = json.loads(provider_body)
            request_id = provider_data.get("request_id")
        except (TypeError, ValueError):
            pass
        current_app.logger.error(
            "Nylas rejected AcaSift %s email: status=%s request_id=%s response=%s",
            purpose, exc.code, request_id or "not-returned", provider_body,
        )
        raise EmailDeliveryError(
            f"Nylas rejected the email request (HTTP {exc.code}). Check the Render logs and Nylas domain status."
        ) from exc
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        current_app.logger.error(
            "Nylas request failed for AcaSift %s email: %s",
            purpose, type(exc).__name__,
        )
        raise EmailDeliveryError(
            "AcaSift could not reach Nylas. Check the Nylas API region, network availability and Render logs."
        ) from exc


def send_verification_email(user, raw_token):
    expires = current_app.config["EMAIL_VERIFICATION_HOURS"]
    link = (
        f"{current_app.config['PUBLIC_APP_URL']}/verify-email"
        f"?token={quote(raw_token, safe='')}"
    )
    recipient = user.first_name or user.full_name
    name = html.escape(recipient)
    safe_link = html.escape(link, quote=True)
    html_body = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#14243d;line-height:1.6">'
        '<h2>Verify your AcaSift email address</h2>'
        f'<p>Hello {name},</p>'
        '<p>Confirm that you own this email address to activate your AcaSift account.</p>'
        f'<p><a href="{safe_link}" style="display:inline-block;padding:12px 18px;background:#18a999;color:#fff;text-decoration:none;border-radius:8px">Verify email address</a></p>'
        f'<p>This link expires in {expires} hours. If you did not create this account, ignore this message.</p>'
        '<p>AcaSift</p></body></html>'
    )
    _send(user.email, recipient, "Verify your AcaSift email address", html_body, "verification")


def send_password_reset_email(user, raw_token):
    expires = current_app.config["PASSWORD_RESET_HOURS"]
    link = (
        f"{current_app.config['PUBLIC_APP_URL']}/reset-password"
        f"?token={quote(raw_token, safe='')}"
    )
    recipient = user.first_name or user.full_name
    name = html.escape(recipient)
    safe_link = html.escape(link, quote=True)
    html_body = (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#14243d;line-height:1.6">'
        '<h2>Reset your AcaSift password</h2>'
        f'<p>Hello {name},</p>'
        '<p>Use the button below to choose a new password.</p>'
        f'<p><a href="{safe_link}" style="display:inline-block;padding:12px 18px;background:#18a999;color:#fff;text-decoration:none;border-radius:8px">Reset password</a></p>'
        f'<p>This link expires in {expires} hour(s). If you did not request this reset, ignore this message.</p>'
        '<p>AcaSift</p></body></html>'
    )
    _send(user.email, recipient, "Reset your AcaSift password", html_body, "password_reset")
