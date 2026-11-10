import html
import json
import re
import uuid
from datetime import datetime, timezone
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


def _branded_email(
    *,
    recipient_name,
    eyebrow,
    heading,
    intro,
    action_label,
    action_url,
    expiry_note,
    security_note,
    preheader,
):
    """Build a table-based, inline-styled HTML email that works across major clients."""
    public_url = current_app.config["PUBLIC_APP_URL"].rstrip("/")
    logo_url = html.escape(f"{public_url}/static/img/acasift-mark.png", quote=True)
    safe_name = html.escape(recipient_name or "there")
    safe_eyebrow = html.escape(eyebrow)
    safe_heading = html.escape(heading)
    safe_intro = html.escape(intro)
    safe_action_label = html.escape(action_label)
    safe_action_url = html.escape(action_url, quote=True)
    safe_expiry = html.escape(expiry_note)
    safe_security = html.escape(security_note)
    safe_preheader = html.escape(preheader)

    year = datetime.now(timezone.utc).year

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="light">
  <meta name="supported-color-schemes" content="light">
  <title>{safe_heading} | AcaSift</title>
</head>
<body style="margin:0;padding:0;background-color:#F5F7FB;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:#14243D;">
  <div style="display:none;font-size:1px;color:#F5F7FB;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{safe_preheader}</div>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;background-color:#F5F7FB;">
    <tr>
      <td align="center" style="padding:36px 14px 42px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="width:100%;max-width:600px;border-collapse:separate;border-spacing:0;">
          <tr>
            <td style="background-color:#14243D;padding:25px 32px;border-radius:16px 16px 0 0;border-bottom:4px solid #18A999;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td valign="middle" style="padding-right:13px;">
                    <img src="{logo_url}" width="48" height="48" alt="AcaSift logo" style="display:block;width:48px;height:48px;border:0;outline:none;text-decoration:none;border-radius:12px;">
                  </td>
                  <td valign="middle">
                    <div style="font-size:23px;line-height:27px;font-weight:750;letter-spacing:-0.5px;color:#FFFFFF;">AcaSift</div>
                    <div style="font-size:10px;line-height:16px;letter-spacing:1.35px;text-transform:uppercase;color:#C9D6E6;">Find the overlap. Follow the source.</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#FFFFFF;padding:39px 42px 34px;border-left:1px solid #E6EBF2;border-right:1px solid #E6EBF2;">
              <div style="display:inline-block;padding:6px 10px;background-color:#EAF7F5;border-radius:30px;color:#147F75;font-size:10px;line-height:14px;font-weight:700;letter-spacing:1.1px;text-transform:uppercase;">{safe_eyebrow}</div>
              <h1 style="margin:19px 0 13px;color:#14243D;font-size:28px;line-height:1.22;font-weight:750;letter-spacing:-0.7px;">{safe_heading}</h1>
              <p style="margin:0 0 22px;color:#526176;font-size:15px;line-height:1.75;">Hello {safe_name},<br>{safe_intro}</p>
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:27px 0 23px;">
                <tr>
                  <td align="center" bgcolor="#18A999" style="border-radius:9px;">
                    <a href="{safe_action_url}" target="_blank" style="display:inline-block;padding:15px 25px;border:1px solid #18A999;border-radius:9px;color:#FFFFFF;text-decoration:none;font-size:14px;line-height:18px;font-weight:700;">{safe_action_label} &nbsp; &#8594;</a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 8px;color:#68778B;font-size:12px;line-height:1.7;">If the button does not work, copy and paste this link into your browser:</p>
              <p style="margin:0 0 24px;padding:12px 14px;background-color:#F5F7FB;border:1px solid #E6EBF2;border-radius:8px;overflow-wrap:anywhere;word-break:break-word;">
                <a href="{safe_action_url}" target="_blank" style="color:#147F75;font-size:12px;line-height:1.65;text-decoration:underline;overflow-wrap:anywhere;word-break:break-word;">{safe_action_url}</a>
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-top:1px solid #E9EDF3;">
                <tr>
                  <td style="padding:19px 0 0;color:#68778B;font-size:12px;line-height:1.7;">
                    <strong style="color:#14243D;">Link expiry:</strong> {safe_expiry}<br>
                    <strong style="color:#14243D;">Security:</strong> {safe_security}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="background-color:#F9FAFC;padding:22px 32px;border:1px solid #E6EBF2;border-top:0;border-radius:0 0 16px 16px;text-align:center;">
              <div style="color:#14243D;font-size:13px;line-height:20px;font-weight:700;">AcaSift</div>
              <div style="margin-top:3px;color:#7A8798;font-size:11px;line-height:18px;">Academic similarity analysis</div>
              <div style="margin-top:12px;color:#9AA5B3;font-size:10px;line-height:17px;">This is an automated account-security message. Please do not reply to this email.<br>&copy; {year} AcaSift. All rights reserved.</div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_verification_email(user, raw_token):
    expires = current_app.config["EMAIL_VERIFICATION_HOURS"]
    link = (
        f"{current_app.config['PUBLIC_APP_URL']}/verify-email"
        f"?token={quote(raw_token, safe='')}"
    )
    recipient = user.first_name or user.full_name
    html_body = _branded_email(
        recipient_name=recipient,
        eyebrow="ACCOUNT VERIFICATION",
        heading="Confirm your email address",
        intro="Welcome to AcaSift. Confirm that this email address belongs to you to activate your individual workspace and start using AcaSift.",
        action_label="Verify my email address",
        action_url=link,
        expiry_note=f"This one-time verification link expires in {expires} hours.",
        security_note="If you did not create an AcaSift account, you can safely ignore this message. Your account will remain inactive.",
        preheader="One quick step remains before your AcaSift workspace is ready.",
    )
    _send(
        user.email,
        recipient,
        "Confirm your email address | AcaSift",
        html_body,
        "verification",
    )


def send_email_change_verification(user, new_email, raw_token):
    expires = current_app.config["EMAIL_VERIFICATION_HOURS"]
    link = (
        f"{current_app.config['PUBLIC_APP_URL']}/confirm-email-change"
        f"?token={quote(raw_token, safe='')}"
    )
    recipient = user.first_name or user.full_name
    html_body = _branded_email(
        recipient_name=recipient,
        eyebrow="EMAIL ADDRESS CHANGE",
        heading="Confirm your new email address",
        intro="A request was made to change the email address on your AcaSift account. Confirm that you control this new address to complete the change.",
        action_label="Confirm new email address",
        action_url=link,
        expiry_note=f"This one-time confirmation link expires in {expires} hours.",
        security_note="Your existing email address remains active until confirmation. If you did not request this change, ignore this message and your account will keep its current email address.",
        preheader="Confirm the new email address for your AcaSift account.",
    )
    _send(
        new_email,
        recipient,
        "Confirm your new email address | AcaSift",
        html_body,
        "verification",
    )


def send_password_reset_email(user, raw_token):
    expires = current_app.config["PASSWORD_RESET_HOURS"]
    link = (
        f"{current_app.config['PUBLIC_APP_URL']}/reset-password"
        f"?token={quote(raw_token, safe='')}"
    )
    recipient = user.first_name or user.full_name
    html_body = _branded_email(
        recipient_name=recipient,
        eyebrow="ACCOUNT SECURITY",
        heading="Choose a new password",
        intro="We received a request to reset the password for your AcaSift account. Use the secure button below to choose a new password.",
        action_label="Reset my password",
        action_url=link,
        expiry_note=f"This one-time password-reset link expires in {expires} hour(s).",
        security_note="If you did not request a password reset, ignore this message. Your current password will remain unchanged. AcaSift will never ask you to send your password by email.",
        preheader="A password reset was requested for your AcaSift account.",
    )
    _send(
        user.email,
        recipient,
        "Reset your password | AcaSift",
        html_body,
        "password_reset",
    )
