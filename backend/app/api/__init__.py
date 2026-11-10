import hashlib
import hmac
import io
import re
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from PIL import Image, ImageOps, UnidentifiedImageError
from flask import Blueprint, current_app, jsonify, request, send_file, session
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func, select, text
from werkzeug.security import check_password_hash, generate_password_hash

from app.decorators import admin_required
from app.extensions import csrf, db
from app.models import Comparison, Document, User, Workspace
from app.services.auth_security import consume_auth_limits
from app.services.email_service import (
    email_is_configured,
    send_email_change_verification,
    send_password_reset_email,
    send_verification_email,
)
from app.services.workspace_service import ensure_personal_workspace, get_active_workspace, membership_for, is_workspace_manager
from app.services.workflow_service import run_comparison, save_uploaded_document
from app.submission_models import (
    DocumentSubmission,
    SubmissionRequest,
    SubmissionRequestParticipant,
)
from app.reference_models import ReferenceEntry
from app.services.reference_service import (
    GLOBAL_RIGHTS_BASES,
    archive_reference_entry,
    list_reference_entries,
    reference_entry_payload,
    register_reference_entry,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def _date(value):
    return value.isoformat() if value else None


def _profile_image_url(user):
    updated_at = user.profile_image_updated_at
    if not updated_at:
        return None
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return f"/api/users/{user.user_id}/profile-picture?v={int(updated_at.timestamp() * 1_000_000)}"


def _user_payload(user):
    return {
        "id": user.user_id,
        "full_name": user.full_name,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "other_names": user.other_names,
        "email": user.email,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "email_verified": bool(user.email_verified_at),
        "profile_image_url": _profile_image_url(user),
        "created_at": _date(user.created_at),
    }


def _validated_name_parts(data):
    first_name = str(data.get("first_name", "")).strip()
    last_name = str(data.get("last_name", "")).strip()
    other_names = str(data.get("other_names", "")).strip()
    if not first_name or not last_name:
        return None, _error("First name and last name are required.")
    if len(first_name) > 80 or len(last_name) > 80 or len(other_names) > 80:
        return None, _error("Each name field must contain no more than 80 characters.")
    display_name = " ".join(part for part in (first_name, other_names, last_name) if part)
    if len(display_name) > 255:
        return None, _error("The combined name is too long.")
    return {
        "first_name": first_name,
        "last_name": last_name,
        "other_names": other_names or None,
        "full_name": display_name,
    }, None


def _document_payload(document):
    return {
        "id": document.document_id,
        "user_id": document.user_id,
        "uploader": document.uploader.full_name if document.uploader else None,
        "title": document.title,
        "original_filename": document.original_filename,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "workspace_id": document.workspace_id,
        "visibility_scope": document.visibility_scope,
        "processing_status": document.processing_status,
        "uploaded_at": _date(document.uploaded_at),
    }


def _comparison_payload(comparison, include_results=False, hide_peer_source_details=False):
    payload = {
        "id": comparison.comparison_id,
        "status": comparison.status,
        "started_at": _date(comparison.started_at),
        "completed_at": _date(comparison.completed_at),
        "submitted_document": _document_payload(comparison.submitted_document),
    }
    if include_results:
        results = sorted(
            comparison.results,
            key=lambda item: (float(item.cosine_similarity), float(item.matched_ngram_coverage)),
            reverse=True,
        )
        payload["results"] = []
        for result in results:
            reference = result.reference_document
            is_request_peer = reference.document_type == "submission"
            passages = []
            for passage in result.passages:
                passages.append({
                    "id": passage.passage_id,
                    "submitted_start": passage.submitted_start,
                    "submitted_end": passage.submitted_end,
                    "reference_start": passage.reference_start,
                    "reference_end": passage.reference_end,
                    "matched_text": passage.matched_text,
                    "reference_text": (
                        "The matching excerpt is hidden to protect another participant's document."
                        if hide_peer_source_details and is_request_peer
                        else (reference.extracted_text or "")[passage.reference_start:passage.reference_end]
                    ),
                })
            reference_payload = _document_payload(reference)
            if hide_peer_source_details and is_request_peer:
                reference_payload = {
                    **reference_payload,
                    "title": "Another submission in this request",
                    "original_filename": "Protected submission",
                    "uploader": None,
                    "user_id": None,
                }
            source_scope = result.source_scope or (
                "request" if is_request_peer else
                "workspace" if reference.visibility_scope == "workspace" else
                "personal" if reference.visibility_scope == "private" else
                "global"
            )
            payload["results"].append({
                "id": result.result_id,
                "source_scope": source_scope,
                "reference_document": reference_payload,
                "cosine_similarity": float(result.cosine_similarity),
                "matched_ngram_coverage": float(result.matched_ngram_coverage),
                "matched_ngram_count": result.matched_ngram_count,
                "total_query_ngrams": result.total_query_ngrams,
                "coverage_method": result.coverage_method,
                "passages": passages,
            })
    return payload


def _error(message, status=400):
    return jsonify({"error": message}), status


def _token_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _token_expired(value):
    if value is None:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value < datetime.now(timezone.utc)


def _rate_limited(action, identity=None, ip_limit=30, identity_limit=None, window_seconds=900):
    result = consume_auth_limits(
        action, identity=identity, ip_limit=ip_limit,
        identity_limit=identity_limit, window_seconds=window_seconds,
    )
    if result is None:
        return None
    payload, status, retry_after = result
    response = jsonify(payload)
    response.status_code = status
    response.headers["Retry-After"] = str(retry_after)
    response.headers["Cache-Control"] = "no-store"
    return response


def _valid_email(value):
    return len(value) <= 150 and bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def _valid_password(value):
    return 10 <= len(value) <= 256


@bp.get("/csrf")
def csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


@bp.get("/auth/me")
def me():
    if not current_user.is_authenticated:
        return _error("Authentication required.", 401)
    return jsonify({"user": _user_payload(current_user)})


@bp.post("/auth/login")
def login():
    if current_user.is_authenticated:
        return jsonify({"user": _user_payload(current_user)})

    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    limited = _rate_limited("login", email or None, ip_limit=30, identity_limit=8, window_seconds=900)
    if limited:
        return limited

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return _error("Invalid email address or password.", 401)
    if not user.email_verified_at:
        # Active accounts created before email verification was introduced are
        # trusted legacy accounts. New public registrations are inactive until verified.
        if user.is_active:
            user.email_verified_at = user.created_at or datetime.now(timezone.utc)
            db.session.commit()
        else:
            return _error("Please verify your email address before signing in. You can request a new verification email.", 403)
    if not user.is_active:
        return _error("This account is currently inactive. Contact AcaSift support.", 403)

    login_user(user, remember=False, fresh=True)
    personal = ensure_personal_workspace(user)
    session["active_workspace_id"] = personal.workspace_id
    db.session.commit()
    response = jsonify({"user": _user_payload(user)})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/register")
def register_account():
    if current_user.is_authenticated:
        return _error("You are already signed in. Sign out before creating another account.", 409)
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    limited = _rate_limited("register", email or None, ip_limit=10, identity_limit=3, window_seconds=3600)
    if limited:
        return limited

    if not email_is_configured():
        return _error("Public registration is temporarily unavailable because email delivery has not been configured. Please try again later.", 503)

    name_parts, name_error = _validated_name_parts(data)
    if name_error:
        return name_error
    password = str(data.get("password", ""))
    confirm_password = str(data.get("confirm_password", ""))
    if not _valid_email(email):
        return _error("Enter a valid email address.")
    if not _valid_password(password):
        return _error("Use a password containing between 10 and 256 characters.")
    if password != confirm_password:
        return _error("The password and confirmation do not match.")
    if User.query.filter_by(email=email).first():
        return _error("An account with that email address already exists. Try signing in or resetting your password.", 409)

    raw_token = secrets.token_urlsafe(32)
    user = User(
        **name_parts,
        email=email,
        password_hash=generate_password_hash(password),
        role="user",
        is_active=False,
        email_verification_token_hash=_token_hash(raw_token),
        email_verification_expires_at=datetime.now(timezone.utc) + timedelta(hours=current_app.config["EMAIL_VERIFICATION_HOURS"]),
    )
    try:
        db.session.add(user)
        db.session.flush()
        ensure_personal_workspace(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Public account registration failed.")
        return _error("We could not complete registration. Please try again later.", 500)

    # Commit the pending account before sending. If Nylas delivery fails, the
    # account remains recoverable through the resend-verification workflow.
    try:
        send_verification_email(user, raw_token)
    except Exception as exc:
        current_app.logger.warning("Registration email delivery was not completed: %s", type(exc).__name__)
        return _error("Your account was created, but the verification email could not be delivered. Use the resend-verification page to try again.", 503)

    response = jsonify({
        "message": "Your account has been created. Check your email for a verification link before signing in.",
        "email": email,
    })
    response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/verify-email")
@csrf.exempt
def verify_email():
    """Verify a one-time email bearer token without requiring a prior browser session.

    The 256-bit, single-use token is the proof of mailbox control. A browser-session
    CSRF token is intentionally not required because email links are opened in a
    fresh browser context and may not share the session that initiated registration.
    The endpoint remains POST-only, rate-limited, expiry-checked and single-use.
    """
    data = request.get_json(silent=True) or {}
    raw_token = str(data.get("token", ""))
    limited = _rate_limited("verify_email", None, ip_limit=20, window_seconds=900)
    if limited:
        return limited
    if not raw_token or len(raw_token) > 512:
        return _error("This verification link is invalid or has expired.", 400)
    user = User.query.filter_by(email_verification_token_hash=_token_hash(raw_token)).first()
    if not user or _token_expired(user.email_verification_expires_at):
        return _error("This verification link is invalid or has expired. Request a new verification email.", 400)

    user.email_verified_at = datetime.now(timezone.utc)
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    user.is_active = True
    personal = ensure_personal_workspace(user)
    db.session.commit()
    login_user(user, remember=False, fresh=True)
    session["active_workspace_id"] = personal.workspace_id
    response = jsonify({"message": "Your email address has been verified.", "user": _user_payload(user)})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/resend-verification")
def resend_verification():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    limited = _rate_limited("resend_verification", email or None, ip_limit=5, identity_limit=3, window_seconds=3600)
    if limited:
        return limited
    generic = {"message": "If an unverified account exists for that address, a verification email will be sent."}
    if not email_is_configured():
        return _error("Email delivery is temporarily unavailable. Please contact AcaSift support.", 503)
    if not _valid_email(email):
        return jsonify(generic)
    user = User.query.filter_by(email=email).first()
    if not user or user.email_verified_at or user.is_active:
        return jsonify(generic)

    raw_token = secrets.token_urlsafe(32)
    user.email_verification_token_hash = _token_hash(raw_token)
    user.email_verification_expires_at = datetime.now(timezone.utc) + timedelta(hours=current_app.config["EMAIL_VERIFICATION_HOURS"])
    db.session.commit()
    try:
        send_verification_email(user, raw_token)
    except Exception:
        current_app.logger.warning("Verification resend could not be delivered.")
    return jsonify(generic)


@bp.post("/auth/password-reset/request")
def request_password_reset():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    limited = _rate_limited("password_reset_request", email or None, ip_limit=5, identity_limit=3, window_seconds=3600)
    if limited:
        return limited
    generic = {"message": "If an active verified account exists for that address, password reset instructions will be sent."}
    if not email_is_configured():
        return _error("Email delivery is temporarily unavailable. Please contact AcaSift support.", 503)
    if not _valid_email(email):
        return jsonify(generic)
    user = User.query.filter_by(email=email).first()
    if not user or not user.is_active or not user.email_verified_at:
        return jsonify(generic)

    raw_token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = _token_hash(raw_token)
    user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=current_app.config["PASSWORD_RESET_HOURS"])
    db.session.commit()
    try:
        send_password_reset_email(user, raw_token)
    except Exception:
        current_app.logger.warning("Password reset email could not be delivered.")
    return jsonify(generic)


@bp.post("/auth/password-reset/confirm")
@csrf.exempt
def confirm_password_reset():
    """Confirm a password reset using its one-time email bearer token.

    The reset token is high-entropy, short-lived and single-use, so a browser
    session CSRF token is not required for this email-link flow.
    """
    data = request.get_json(silent=True) or {}
    raw_token = str(data.get("token", ""))
    limited = _rate_limited("password_reset_confirm", None, ip_limit=10, window_seconds=900)
    if limited:
        return limited
    new_password = str(data.get("new_password", ""))
    confirm_password = str(data.get("confirm_password", ""))
    if not raw_token or len(raw_token) > 512:
        return _error("This password reset link is invalid or has expired.", 400)
    if not _valid_password(new_password):
        return _error("Use a password containing between 10 and 256 characters.")
    if new_password != confirm_password:
        return _error("The password and confirmation do not match.")
    user = User.query.filter_by(password_reset_token_hash=_token_hash(raw_token)).first()
    if not user or _token_expired(user.password_reset_expires_at) or not user.is_active:
        return _error("This password reset link is invalid or has expired. Request a new one.", 400)

    user.password_hash = generate_password_hash(new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.pending_email = None
    user.email_change_token_hash = None
    user.email_change_expires_at = None
    user.auth_version = int(user.auth_version or 0) + 1
    db.session.commit()
    response = jsonify({"message": "Your password has been reset. Sign in using your new password."})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "You have been signed out."})


@bp.get("/account")
@login_required
def account_overview():
    documents = Document.query.filter_by(user_id=current_user.user_id).order_by(
        Document.uploaded_at.desc()
    ).limit(5).all()
    comparisons = Comparison.query.filter_by(user_id=current_user.user_id).order_by(
        Comparison.started_at.desc()
    ).limit(5).all()
    return jsonify({
        "user": _user_payload(current_user),
        "pending_email": (
            current_user.pending_email
            if current_user.email_change_token_hash and not _token_expired(current_user.email_change_expires_at)
            else None
        ),
        "email_change_pending": bool(
            current_user.pending_email
            and current_user.email_change_token_hash
            and not _token_expired(current_user.email_change_expires_at)
        ),
        "activity": {
            "document_count": Document.query.filter_by(user_id=current_user.user_id).count(),
            "comparison_count": Comparison.query.filter_by(user_id=current_user.user_id).count(),
            "recent_documents": [_document_payload(item) for item in documents],
            "recent_comparisons": [_comparison_payload(item) for item in comparisons],
        },
    })


@bp.post("/account/profile")
@login_required
def update_account_profile():
    data = request.get_json(silent=True) or {}
    name_parts, error = _validated_name_parts(data)
    if error:
        return error
    current_user.first_name = name_parts["first_name"]
    current_user.last_name = name_parts["last_name"]
    current_user.other_names = name_parts["other_names"]
    current_user.full_name = name_parts["full_name"]
    db.session.commit()
    return jsonify({"message": "Personal information updated successfully.", "user": _user_payload(current_user)})


@bp.post("/account/profile-picture")
@login_required
def upload_account_profile_picture():
    image_file = request.files.get("image")
    if not image_file or not image_file.filename:
        return _error("Choose a profile picture to upload.")

    raw_image = image_file.read(5 * 1024 * 1024 + 1)
    if not raw_image:
        return _error("The selected image is empty.")
    if len(raw_image) > 5 * 1024 * 1024:
        return _error("Profile pictures must be 5 MB or smaller.", 413)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(io.BytesIO(raw_image))
            if source.format not in {"JPEG", "PNG", "WEBP"}:
                return _error("Use a JPEG, PNG or WebP image.")
            if getattr(source, "n_frames", 1) != 1:
                return _error("Animated images are not supported. Choose a still image.")
            if source.width * source.height > 40_000_000:
                return _error("This image is too large. Choose an image with fewer pixels.")
            source.verify()

            source = Image.open(io.BytesIO(raw_image))
            source = ImageOps.exif_transpose(source)
            source.thumbnail((512, 512), Image.Resampling.LANCZOS)
            has_alpha = source.mode in {"RGBA", "LA"} or (
                source.mode == "P" and "transparency" in source.info
            )
            processed = source.convert("RGBA" if has_alpha else "RGB")
            output = io.BytesIO()
            processed.save(output, format="WEBP", quality=84, method=6)
            image_data = output.getvalue()
            if not image_data or len(image_data) > 600 * 1024:
                return _error("This image could not be reduced to a suitable profile picture.")
    except (
        UnidentifiedImageError,
        OSError,
        EOFError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        return _error("The selected file is not a valid supported image.")

    current_user.profile_image_data = image_data
    current_user.profile_image_mime = "image/webp"
    current_user.profile_image_updated_at = datetime.now(timezone.utc)
    db.session.commit()
    response = jsonify({
        "message": "Your profile picture has been updated.",
        "user": _user_payload(current_user),
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.delete("/account/profile-picture")
@login_required
def remove_account_profile_picture():
    current_user.profile_image_data = None
    current_user.profile_image_mime = None
    current_user.profile_image_updated_at = None
    db.session.commit()
    response = jsonify({"message": "Your profile picture has been removed."})
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/users/<int:user_id>/profile-picture")
@login_required
def get_user_profile_picture(user_id):
    user = db.session.get(User, user_id)
    if not user or not user.profile_image_data:
        return _error("Profile picture not found.", 404)

    if user.user_id != current_user.user_id and not current_user.is_admin:
        active_workspace = get_active_workspace(current_user)
        viewer_membership = membership_for(current_user, active_workspace.workspace_id)
        target_membership = membership_for(user, active_workspace.workspace_id)
        if not viewer_membership or not target_membership:
            return _error("Profile picture not found.", 404)

    response = send_file(
        io.BytesIO(user.profile_image_data),
        mimetype=user.profile_image_mime or "image/webp",
        download_name="profile-picture.webp",
        conditional=False,
        max_age=86400,
    )
    response.headers["Cache-Control"] = "private, max-age=86400"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Vary"] = "Cookie"
    return response


@bp.post("/account/email-change")
@login_required
def request_account_email_change():
    limited = _rate_limited(
        "email_change_request",
        str(current_user.user_id),
        ip_limit=8,
        identity_limit=4,
        window_seconds=3600,
    )
    if limited:
        return limited

    data = request.get_json(silent=True) or {}
    new_email = str(data.get("new_email", "")).strip().lower()
    current_password = str(data.get("current_password", ""))
    if not current_password or not current_user.check_password(current_password):
        return _error("Your current password is incorrect.", 400)
    if not _valid_email(new_email):
        return _error("Enter a valid email address.")
    if new_email == current_user.email.lower():
        return _error("This is already your current email address.")
    if not email_is_configured():
        return _error("Email verification is temporarily unavailable. Please try again later.", 503)

    existing = User.query.filter(func.lower(User.email) == new_email).first()
    pending = User.query.filter(
        func.lower(User.pending_email) == new_email,
        User.email_change_expires_at > datetime.now(timezone.utc),
        User.user_id != current_user.user_id,
    ).first()
    if existing or pending:
        return _error("That email address is already associated with another account or pending request.", 409)

    raw_token = secrets.token_urlsafe(32)
    current_user.pending_email = new_email
    current_user.email_change_token_hash = _token_hash(raw_token)
    current_user.email_change_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=current_app.config["EMAIL_VERIFICATION_HOURS"]
    )
    db.session.commit()

    try:
        send_email_change_verification(current_user, new_email, raw_token)
    except Exception as exc:
        current_app.logger.warning(
            "Email change verification delivery was not completed: %s",
            type(exc).__name__,
        )
        current_user.pending_email = None
        current_user.email_change_token_hash = None
        current_user.email_change_expires_at = None
        db.session.commit()
        return _error(
            "Your current email address has not changed. We could not send the confirmation message; submit the request again to retry.",
            503,
        )

    response = jsonify({
        "message": "A confirmation link has been sent to your new email address. Your current email remains active until you confirm it.",
        "pending_email": new_email,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/auth/confirm-email-change")
@csrf.exempt
def confirm_account_email_change():
    data = request.get_json(silent=True) or {}
    raw_token = str(data.get("token", ""))
    limited = _rate_limited("confirm_email_change", None, ip_limit=20, window_seconds=900)
    if limited:
        return limited
    if not raw_token or len(raw_token) > 512:
        return _error("This email confirmation link is invalid or has expired. Request another email change.", 400)

    user = User.query.filter_by(email_change_token_hash=_token_hash(raw_token)).first()
    if (
        not user
        or not user.is_active
        or not user.pending_email
        or _token_expired(user.email_change_expires_at)
    ):
        return _error("This email confirmation link is invalid or has expired. Request another email change.", 400)

    new_email = user.pending_email.strip().lower()
    existing = User.query.filter(
        func.lower(User.email) == new_email,
        User.user_id != user.user_id,
    ).first()
    if existing:
        user.pending_email = None
        user.email_change_token_hash = None
        user.email_change_expires_at = None
        db.session.commit()
        return _error("That email address is no longer available. Request the change using another address.", 409)

    user.email = new_email
    user.email_verified_at = datetime.now(timezone.utc)
    user.pending_email = None
    user.email_change_token_hash = None
    user.email_change_expires_at = None
    db.session.commit()

    response = jsonify({
        "message": "Your email address has been changed and verified successfully.",
        "email": user.email,
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/account/password")
@login_required
def change_account_password():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    confirm_password = str(data.get("confirm_password", ""))
    if not current_password or not check_password_hash(current_user.password_hash, current_password):
        return _error("Your current password is incorrect.", 400)
    if len(new_password) < 10 or len(new_password) > 256:
        return _error("Your new password must contain between 10 and 256 characters.")
    if new_password != confirm_password:
        return _error("The new password and confirmation do not match.")
    if check_password_hash(current_user.password_hash, new_password):
        return _error("Choose a password different from your current password.")
    current_user.password_hash = generate_password_hash(new_password)
    current_user.password_reset_token_hash = None
    current_user.password_reset_expires_at = None
    current_user.pending_email = None
    current_user.email_change_token_hash = None
    current_user.email_change_expires_at = None
    current_user.auth_version = int(current_user.auth_version or 0) + 1
    db.session.commit()
    login_user(current_user, remember=False, fresh=True)
    return jsonify({"message": "Your password has been changed successfully."})


@bp.get("/dashboard")
@login_required
def dashboard():
    workspace = get_active_workspace(current_user)
    document_query = Document.query.filter_by(
        user_id=current_user.user_id,
        workspace_id=workspace.workspace_id,
        document_type="submission",
    )
    comparison_query = Comparison.query.filter(
        Comparison.user_id == current_user.user_id,
        Comparison.workspace_id == workspace.workspace_id,
    )
    reference_query = ReferenceEntry.query.filter(
        ReferenceEntry.status == "active",
        ReferenceEntry.document.has(Document.processing_status == "processed"),
        (
            (ReferenceEntry.scope == "global")
            & (ReferenceEntry.rights_verified.is_(True))
        )
        | (
            (ReferenceEntry.scope == "personal")
            & (ReferenceEntry.owner_user_id == current_user.user_id)
            & (workspace.workspace_type == "personal")
        )
        | (
            (ReferenceEntry.scope == "workspace")
            & (ReferenceEntry.workspace_id == workspace.workspace_id)
            & (ReferenceEntry.rights_verified.is_(True))
            & (workspace.workspace_type == "shared")
        ),
    )
    request_records = (
        SubmissionRequest.query.join(SubmissionRequestParticipant)
        .join(SubmissionRequest.workspace)
        .filter(
            SubmissionRequestParticipant.user_id == current_user.user_id,
            SubmissionRequestParticipant.status == "active",
            Workspace.status == "active",
            SubmissionRequest.status.in_(("draft", "open", "closed", "archived")),
        )
        .order_by(SubmissionRequest.updated_at.desc())
        .limit(50)
        .all()
    )
    submission_summaries = db.session.query(
        DocumentSubmission.request_id,
        func.count(DocumentSubmission.submission_id),
        func.max(DocumentSubmission.submitted_at),
    ).filter_by(contributor_user_id=current_user.user_id).group_by(
        DocumentSubmission.request_id
    ).all()
    summary_by_request = {
        request_id: {"count": count, "last_submitted_at": last_submitted_at}
        for request_id, count, last_submitted_at in submission_summaries
    }
    my_submission_requests = []
    for item in request_records:
        summary = summary_by_request.get(item.request_id, {})
        my_submission_requests.append({
            "id": item.request_id,
            "title": item.title,
            "workspace_name": item.workspace.name if item.workspace else None,
            "status": item.status,
            "due_at": _date(item.due_at),
            "submission_count": summary.get("count", 0),
            "last_submitted_at": _date(summary.get("last_submitted_at")),
        })

    return jsonify({
        "stats": {
            "document_count": document_query.count(),
            "comparison_count": comparison_query.count(),
            "reference_count": reference_query.with_entities(ReferenceEntry.document_id).distinct().count(),
        },
        "recent_documents": [_document_payload(item) for item in document_query.order_by(Document.uploaded_at.desc()).limit(6).all()],
        "recent_comparisons": [_comparison_payload(item) for item in comparison_query.order_by(Comparison.started_at.desc()).limit(6).all()],
        "my_submission_requests": my_submission_requests,
    })


@bp.get("/documents")
@login_required
def documents():
    workspace = get_active_workspace(current_user)
    query = Document.query.filter(
        (
            (Document.document_type == "submission")
            & (Document.user_id == current_user.user_id)
            & (Document.workspace_id == workspace.workspace_id)
        )
        | (
            (Document.document_type == "reference")
            & (
                (Document.visibility_scope == "platform")
                | (
                    (Document.workspace_id == workspace.workspace_id)
                    & (Document.visibility_scope == "workspace")
                )
                | (
                    (Document.workspace_id == workspace.workspace_id)
                    & (Document.user_id == current_user.user_id)
                    & (Document.visibility_scope == "private")
                )
            )
        )
    )
    records = query.order_by(Document.uploaded_at.desc()).all()
    return jsonify({"documents": [_document_payload(item) for item in records]})


@bp.post("/documents")
@login_required
def upload_submission():
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "submission",
        )
        comparison = run_comparison(document)
        return jsonify({
            "message": "Document uploaded and similarity analysis completed.",
            "comparison_id": comparison.comparison_id,
            "comparison": _comparison_payload(comparison),
        }), 201
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception:
        from flask import current_app
        current_app.logger.exception("Submission upload or comparison failed.")
        return _error("The document was stored, but similarity analysis could not be completed. Check the application log.", 500)


@bp.get("/comparisons/<int:comparison_id>")
@login_required
def comparison_detail(comparison_id):
    comparison = db.get_or_404(Comparison, comparison_id)
    from app.submission_models import DocumentSubmission, SubmissionRequestReviewer

    generic_submission = DocumentSubmission.query.filter_by(comparison_id=comparison_id).first()
    hide_peer_source_details = False
    if generic_submission:
        submission_request = generic_submission.request
        if not submission_request.workspace or submission_request.workspace.status != "active":
            return _error("This report is no longer available.", 404)
        membership = membership_for(current_user, submission_request.workspace_id)
        is_manager = is_workspace_manager(membership)
        is_reviewer = bool(membership and SubmissionRequestReviewer.query.filter_by(
            request_id=submission_request.request_id,
            user_id=current_user.user_id,
        ).first())
        active_participation = SubmissionRequestParticipant.query.filter_by(
            request_id=submission_request.request_id,
            user_id=current_user.user_id,
            status="active",
        ).first()
        is_contributor = (
            generic_submission.contributor_user_id == current_user.user_id
            and active_participation is not None
        )
        if not (is_contributor or is_manager or is_reviewer):
            return _error("You do not have permission to view this report.", 403)
        hide_peer_source_details = is_contributor and not (is_manager or is_reviewer)
    else:
        if comparison.user_id != current_user.user_id:
            return _error("You do not have permission to view this report.", 403)
        if comparison.workspace_id and not membership_for(current_user, comparison.workspace_id):
            return _error("This report belongs to a workspace you can no longer access.", 403)

    return jsonify({"comparison": _comparison_payload(
        comparison,
        include_results=True,
        hide_peer_source_details=hide_peer_source_details,
    )})


@bp.get("/admin/users")
@admin_required
def users():
    records = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [{
        **_user_payload(user),
        "is_active": user.is_active,
        "email_verified": bool(user.email_verified_at),
        "created_at": _date(user.created_at),
    } for user in records]})


@bp.post("/admin/users")
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    name_parts, name_error = _validated_name_parts(data)
    if name_error:
        return name_error
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "user"))

    if not email or not password:
        return _error("Email address and password are required.")
    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return _error("Enter a valid email address.")
    if len(password) < 10 or len(password) > 256:
        return _error("The password must contain between 10 and 256 characters.")
    if role not in {"user", "admin"}:
        return _error("The selected account role is invalid.")
    if User.query.filter_by(email=email).first():
        return _error("An account with that email already exists.", 409)

    user = User(
        **name_parts,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    db.session.add(user)
    db.session.flush()
    ensure_personal_workspace(user)
    db.session.commit()
    return jsonify({"message": "User account created successfully.", "user": _user_payload(user)}), 201


def _valid_reference_url(value, field_name):
    value = str(value or "").strip()
    if not value:
        return None, None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None, _error(f"Enter a valid HTTP or HTTPS {field_name}.")
    if len(value) > 1000:
        return None, _error(f"The {field_name} is too long.")
    return value, None


def _reference_entry_response(entry):
    return reference_entry_payload(entry)


@bp.get("/reference-library")
@login_required
def reference_library():
    workspace = get_active_workspace(current_user)
    if workspace.workspace_type == "personal":
        entries = list_reference_entries(
            scope="personal",
            owner_user_id=current_user.user_id,
        )
        scope = "personal"
        can_manage = True
    else:
        membership = membership_for(current_user, workspace.workspace_id)
        entries = list_reference_entries(
            scope="workspace",
            workspace_id=workspace.workspace_id,
        )
        scope = "workspace"
        can_manage = is_workspace_manager(membership)
    return jsonify({
        "scope": scope,
        "workspace": {"id": workspace.workspace_id, "name": workspace.name, "type": workspace.workspace_type},
        "can_manage": can_manage,
        "entries": [_reference_entry_response(entry) for entry in entries],
    })


@bp.post("/reference-library")
@login_required
def upload_reference_library_document():
    workspace = get_active_workspace(current_user)
    if workspace.workspace_type == "shared":
        membership = membership_for(current_user, workspace.workspace_id)
        if not is_workspace_manager(membership):
            return _error("Only workspace owners and administrators can manage shared references.", 403)
        if str(request.form.get("permission_confirmed", "")).lower() not in {"1", "true", "yes", "on"}:
            return _error("Confirm that you have permission to use this document within the workspace.")
        scope = "workspace"
        visibility_scope = "workspace"
        rights_basis = "workspace_permission"
        rights_verified = True
        owner_user_id = None
        workspace_id = workspace.workspace_id
    else:
        scope = "personal"
        visibility_scope = "private"
        rights_basis = "personal_use_only"
        rights_verified = False
        owner_user_id = current_user.user_id
        workspace_id = None

    source_url, url_error = _valid_reference_url(request.form.get("source_url"), "source URL")
    if url_error:
        return url_error
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "reference",
            workspace_id=workspace.workspace_id if scope == "personal" else workspace_id,
            visibility_scope=visibility_scope,
            commit=False,
        )
        entry = register_reference_entry(
            document,
            scope,
            current_user.user_id,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
            status="active",
            provenance_type="user_upload",
            source_title=document.title,
            source_url=source_url,
            rights_basis=rights_basis,
            rights_verified=rights_verified,
            verified_by_user_id=current_user.user_id if rights_verified else None,
            verified_at=datetime.now(timezone.utc) if rights_verified else None,
        )
        db.session.commit()
        return jsonify({
            "message": f"Reference document '{document.title}' added to your {scope} reference library.",
            "entry": _reference_entry_response(entry),
        }), 201
    except ValueError as exc:
        db.session.rollback()
        return _error(str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Reference library upload failed.")
        return _error("The reference document could not be saved.", 500)


@bp.delete("/reference-library/<int:entry_id>")
@login_required
def archive_reference_library_entry(entry_id):
    entry = db.session.get(ReferenceEntry, entry_id)
    if not entry or entry.scope not in {"personal", "workspace"}:
        return _error("Reference document not found.", 404)
    if entry.scope == "personal":
        if entry.owner_user_id != current_user.user_id:
            return _error("You do not have permission to remove this reference.", 403)
    else:
        membership = membership_for(current_user, entry.workspace_id)
        if not is_workspace_manager(membership):
            return _error("Only workspace owners and administrators can manage shared references.", 403)
    archive_reference_entry(entry)
    db.session.commit()
    return jsonify({"message": "The reference was removed from this collection."})


@bp.post("/reference-library/<int:entry_id>/verify")
@login_required
def verify_workspace_reference_entry(entry_id):
    entry = db.session.get(ReferenceEntry, entry_id)
    if not entry or entry.scope != "workspace" or entry.status != "review_required":
        return _error("Reference document not found or no longer requires review.", 404)
    membership = membership_for(current_user, entry.workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can verify shared references.", 403)
    if str(request.form.get("permission_confirmed", "")).lower() not in {"1", "true", "yes", "on"}:
        return _error("Confirm that the workspace has permission to use this document.")
    entry.status = "active"
    entry.rights_basis = "workspace_permission"
    entry.rights_verified = True
    entry.verified_by_user_id = current_user.user_id
    entry.verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Workspace reference permission recorded."})


@bp.post("/workspace/references")
@login_required
def upload_workspace_reference():
    """Backward-compatible endpoint; new clients use /reference-library."""
    workspace = get_active_workspace(current_user)
    if workspace.workspace_type != "shared":
        return _error("Shared reference collections are not available in a personal workspace.", 403)
    membership = membership_for(current_user, workspace.workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can manage shared references.", 403)
    if str(request.form.get("permission_confirmed", "")).lower() not in {"1", "true", "yes", "on"}:
        return _error("Confirm that you have permission to use this document within the workspace.")
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "reference",
            workspace_id=workspace.workspace_id,
            visibility_scope="workspace",
            commit=False,
        )
        entry = register_reference_entry(
            document,
            "workspace",
            current_user.user_id,
            workspace_id=workspace.workspace_id,
            status="active",
            provenance_type="user_upload",
            rights_basis="workspace_permission",
            rights_verified=True,
            verified_by_user_id=current_user.user_id,
            verified_at=datetime.now(timezone.utc),
        )
        db.session.commit()
        return jsonify({"message": f"Reference document '{document.title}' added to {workspace.name}.", "document": _document_payload(document), "entry": _reference_entry_response(entry)}), 201
    except ValueError as exc:
        db.session.rollback()
        return _error(str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Workspace reference upload failed.")
        return _error("The reference document could not be saved.", 500)


@bp.get("/admin/references")
@admin_required
def references():
    entries = list_reference_entries(scope="global", include_inactive=True)
    payload = [_reference_entry_response(entry) for entry in entries]
    return jsonify({"entries": payload, "documents": [_document_payload(entry.document) for entry in entries]})


@bp.post("/admin/references")
@admin_required
def upload_reference():
    rights_basis = str(request.form.get("rights_basis", "")).strip()
    if rights_basis not in GLOBAL_RIGHTS_BASES:
        return _error("Select a valid permission basis for this global reference.")
    if str(request.form.get("rights_confirmed", "")).lower() not in {"1", "true", "yes", "on"}:
        return _error("Confirm that AcaSift has the necessary rights to use this document globally.")

    license_name = str(request.form.get("license_name", "")).strip() or None
    license_url, url_error = _valid_reference_url(request.form.get("license_url"), "licence URL")
    if url_error:
        return url_error
    source_url, url_error = _valid_reference_url(request.form.get("source_url"), "source URL")
    if url_error:
        return url_error
    if rights_basis == "open_license" and (not license_name or not license_url):
        return _error("Provide the open licence name and its official licence URL.")
    rights_notes = str(request.form.get("rights_notes", "")).strip()[:2000] or None
    if rights_basis in {"author_permission", "publisher_agreement", "other_authorization"} and not (source_url or rights_notes):
        return _error("Provide a source URL or permission note supporting global use.")

    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "reference",
            commit=False,
        )
        entry = register_reference_entry(
            document,
            "global",
            current_user.user_id,
            status="active",
            provenance_type="administrator_curated",
            source_title=document.title,
            source_url=source_url,
            doi=str(request.form.get("doi", "")).strip()[:255] or None,
            rights_basis=rights_basis,
            license_name=license_name,
            license_url=license_url,
            rights_notes=rights_notes,
            rights_verified=True,
            verified_by_user_id=current_user.user_id,
            verified_at=datetime.now(timezone.utc),
        )
        db.session.commit()
        return jsonify({
            "message": f"Reference document '{document.title}' added to the global collection.",
            "entry": _reference_entry_response(entry),
            "document": _document_payload(document),
        }), 201
    except ValueError as exc:
        db.session.rollback()
        return _error(str(exc), 400)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Global reference upload failed.")
        return _error("The reference document could not be saved.", 500)


@bp.post("/admin/references/<int:entry_id>/verify")
@admin_required
def verify_global_reference_entry(entry_id):
    entry = db.session.get(ReferenceEntry, entry_id)
    if not entry or entry.scope != "global" or entry.status != "review_required":
        return _error("Reference document not found or no longer requires review.", 404)
    rights_basis = str(request.form.get("rights_basis", "")).strip()
    if rights_basis not in GLOBAL_RIGHTS_BASES:
        return _error("Select a valid permission basis for this global reference.")
    if str(request.form.get("rights_confirmed", "")).lower() not in {"1", "true", "yes", "on"}:
        return _error("Confirm that AcaSift has the necessary rights to use this document globally.")
    license_name = str(request.form.get("license_name", "")).strip() or None
    license_url, url_error = _valid_reference_url(request.form.get("license_url"), "licence URL")
    if url_error:
        return url_error
    source_url, url_error = _valid_reference_url(request.form.get("source_url"), "source URL")
    if url_error:
        return url_error
    if rights_basis == "open_license" and (not license_name or not license_url):
        return _error("Provide the open licence name and its official licence URL.")
    rights_notes = str(request.form.get("rights_notes", "")).strip()[:2000] or None
    if rights_basis in {"author_permission", "publisher_agreement", "other_authorization"} and not (source_url or rights_notes):
        return _error("Provide a source URL or permission note supporting global use.")
    entry.status = "active"
    entry.rights_basis = rights_basis
    entry.license_name = license_name
    entry.license_url = license_url
    entry.source_url = source_url
    entry.rights_notes = rights_notes
    entry.rights_verified = True
    entry.verified_by_user_id = current_user.user_id
    entry.verified_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Global reference rights verified. The document is now eligible for comparisons."})


@bp.delete("/admin/references/<int:entry_id>")
@admin_required
def archive_global_reference_entry(entry_id):
    entry = db.session.get(ReferenceEntry, entry_id)
    if not entry or entry.scope != "global":
        return _error("Global reference not found.", 404)
    archive_reference_entry(entry)
    db.session.commit()
    return jsonify({"message": "The global reference has been removed from future comparisons."})


@bp.get("/bootstrap/status")
def bootstrap_status():
    """Expose only whether one-time first-admin setup can currently be used."""
    token = str(current_app.config.get("ADMIN_BOOTSTRAP_TOKEN") or "")
    token_is_configured = len(token) >= 32
    admin_exists = db.session.execute(
        select(User.user_id).where(User.role == "admin").limit(1)
    ).first() is not None

    response = jsonify({"available": token_is_configured and not admin_exists})
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@bp.post("/bootstrap/first-admin")
def bootstrap_first_admin():
    """Create exactly one initial administrator when a high-entropy token is configured."""
    configured_token = str(current_app.config.get("ADMIN_BOOTSTRAP_TOKEN") or "")
    if len(configured_token) < 32:
        return _error("Initial administrator setup is disabled. Configure a strong setup token first.", 410)

    data = request.get_json(silent=True) or {}
    supplied_token = str(data.get("setup_token", ""))
    if len(supplied_token) > 512 or not hmac.compare_digest(supplied_token.encode('utf-8'), configured_token.encode('utf-8')):
        return _error("The setup token is invalid.", 403)

    name_parts, name_error = _validated_name_parts(data)
    if name_error:
        return name_error
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return _error("Enter a valid email address.")
    if len(password) < 10 or len(password) > 256:
        return _error("Your password must contain between 10 and 256 characters.")

    created_user = None
    outcome = None

    try:
        # PostgreSQL advisory transaction lock serialises simultaneous bootstrap
        # attempts across Render workers. The administrator count is checked only
        # after acquiring the lock, so two requests cannot both create an admin.
        with db.session.begin():
            if db.engine.dialect.name == "postgresql":
                db.session.execute(text("SELECT pg_advisory_xact_lock(731245908113)"))

            existing_admin = db.session.execute(
                select(User.user_id).where(User.role == "admin").limit(1)
            ).first()

            if existing_admin:
                outcome = "completed"
            else:
                existing_email = db.session.execute(
                    select(User.user_id).where(func.lower(User.email) == email).limit(1)
                ).first()

                if existing_email:
                    outcome = "email_exists"
                else:
                    created_user = User(
                        **name_parts,
                        email=email,
                        password_hash=generate_password_hash(password),
                        role="admin",
                        is_active=True,
                        email_verified_at=datetime.now(timezone.utc),
                    )
                    db.session.add(created_user)
                    db.session.flush()
                    ensure_personal_workspace(created_user)

    except Exception:
        db.session.rollback()
        current_app.logger.exception("First administrator bootstrap failed.")
        return _error("The administrator account could not be created. Please try again.", 500)

    if outcome == "completed":
        return _error("Initial administrator setup has already been completed.", 409)
    if outcome == "email_exists":
        return _error("An account with that email already exists. Use a different email address.", 409)

    # Sign in only after the database transaction commits successfully.
    login_user(created_user, remember=False, fresh=True)
    personal = ensure_personal_workspace(created_user)
    session["active_workspace_id"] = personal.workspace_id
    db.session.commit()
    response = jsonify({
        "message": "Your AcaSift administrator account has been created.",
        "user": _user_payload(created_user),
    })
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response, 201
