import hmac
import re
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request, session

from flask_login import current_user, login_user, login_required, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select, func, text

from app.decorators import admin_required
from app.extensions import csrf, db
from app.models import Comparison, Document, User, Workspace, WorkspaceMembership, WorkspaceRequest
from app.services.auth_security import consume_auth_limits
from app.services.email_service import (
    email_is_configured, send_password_reset_email, send_verification_email,
)
from app.services.workspace_service import ensure_personal_workspace, get_active_workspace, membership_for, is_workspace_manager
from app.services.workflow_service import run_comparison, save_uploaded_document

bp = Blueprint("api", __name__, url_prefix="/api")


def _date(value):
    return value.isoformat() if value else None


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


def _comparison_payload(comparison, include_results=False):
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
            passages = []
            for passage in result.passages:
                passages.append({
                    "id": passage.passage_id,
                    "submitted_start": passage.submitted_start,
                    "submitted_end": passage.submitted_end,
                    "reference_start": passage.reference_start,
                    "reference_end": passage.reference_end,
                    "matched_text": passage.matched_text,
                    "reference_text": (reference.extracted_text or "")[passage.reference_start:passage.reference_end],
                })
            payload["results"].append({
                "id": result.result_id,
                "reference_document": _document_payload(reference),
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
    comparison_query = Comparison.query.filter_by(
        user_id=current_user.user_id,
        workspace_id=workspace.workspace_id,
    )
    reference_query = Document.query.filter(
        Document.document_type == "reference",
        Document.processing_status == "processed",
        (
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
        ),
    )
    return jsonify({
        "stats": {
            "document_count": document_query.count(),
            "comparison_count": comparison_query.count(),
            "reference_count": reference_query.count(),
        },
        "recent_documents": [_document_payload(item) for item in document_query.order_by(Document.uploaded_at.desc()).limit(6).all()],
        "recent_comparisons": [_comparison_payload(item) for item in comparison_query.order_by(Comparison.started_at.desc()).limit(6).all()],
        "workspace": _workspace_payload(workspace),
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
    if comparison.user_id != current_user.user_id:
        return _error("You do not have permission to view this report.", 403)
    if comparison.workspace_id and not membership_for(current_user, comparison.workspace_id):
        return _error("This report belongs to a workspace you can no longer access.", 403)
    return jsonify({"comparison": _comparison_payload(comparison, include_results=True)})


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


@bp.post("/workspace/references")
@login_required
def upload_workspace_reference():
    workspace = get_active_workspace(current_user)
    membership = membership_for(current_user, workspace.workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only the owner or an authorised workspace administrator can add reference documents.", 403)
    scope = "private" if workspace.workspace_type == "personal" else "workspace"
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "reference",
            workspace_id=workspace.workspace_id,
            visibility_scope=scope,
        )
        return jsonify({
            "message": f"Reference document '{document.title}' added to {workspace.name}.",
            "document": _document_payload(document),
        }), 201
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception:
        current_app.logger.exception("Workspace reference upload failed.")
        return _error("The reference document could not be saved.", 500)


@bp.get("/admin/references")
@admin_required
def references():
    records = Document.query.filter_by(document_type="reference", visibility_scope="platform").order_by(Document.uploaded_at.desc()).all()
    return jsonify({"documents": [_document_payload(item) for item in records]})


@bp.post("/admin/references")
@admin_required
def upload_reference():
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "reference",
        )
        return jsonify({
            "message": f"Reference document '{document.title}' added to the repository.",
            "document": _document_payload(document),
        }), 201
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception:
        from flask import current_app
        current_app.logger.exception("Reference document upload failed.")
        return _error("The reference document could not be saved.", 500)




def _workspace_payload(workspace, membership=None):
    return {
        "id": workspace.workspace_id,
        "name": workspace.name,
        "type": workspace.workspace_type,
        "status": workspace.status,
        "role": membership.role if membership else None,
        "created_at": _date(workspace.created_at),
    }


@bp.get("/workspaces")
@login_required
def workspaces():
    active = get_active_workspace(current_user)
    memberships = (
        WorkspaceMembership.query.join(Workspace)
        .filter(
            WorkspaceMembership.user_id == current_user.user_id,
            WorkspaceMembership.status == "active",
            Workspace.status == "active",
        ).order_by(Workspace.created_at.asc()).all()
    )
    pending = WorkspaceRequest.query.filter_by(user_id=current_user.user_id, status="pending").order_by(WorkspaceRequest.created_at.desc()).first()
    active_membership = membership_for(current_user, active.workspace_id)
    members = []
    if is_workspace_manager(active_membership):
        members = [{
            "id": item.user.user_id,
            "full_name": item.user.full_name,
            "email": item.user.email,
            "role": item.role,
        } for item in WorkspaceMembership.query.filter_by(workspace_id=active.workspace_id, status="active").all()]
    return jsonify({
        "active_workspace_id": active.workspace_id,
        "workspaces": [_workspace_payload(item.workspace, item) for item in memberships],
        "pending_request": ({
            "id": pending.request_id,
            "organization_name": pending.organization_name,
            "status": pending.status,
            "created_at": _date(pending.created_at),
        } if pending else None),
        "can_manage_members": is_workspace_manager(active_membership),
        "members": members,
    })


@bp.post("/workspaces/current")
@login_required
def switch_workspace():
    data = request.get_json(silent=True) or {}
    try:
        workspace_id = int(data.get("workspace_id"))
    except (TypeError, ValueError):
        return _error("Select a valid workspace.")
    membership = membership_for(current_user, workspace_id)
    if not membership:
        return _error("You are not an active member of that workspace.", 403)
    session["active_workspace_id"] = workspace_id
    return jsonify({"message": "Workspace changed successfully.", "workspace": _workspace_payload(membership.workspace, membership)})


@bp.post("/workspaces/requests")
@login_required
def request_organization_workspace():
    data = request.get_json(silent=True) or {}
    name = str(data.get("organization_name", "")).strip()
    kind = str(data.get("organization_type", "other")).strip().lower()
    website = str(data.get("website", "")).strip()
    reason = str(data.get("reason", "")).strip()
    allowed_types = {"university", "college", "school", "research_group", "company", "other"}
    if not name or len(name) > 180:
        return _error("Enter an organisation name (up to 180 characters).")
    if kind not in allowed_types:
        return _error("Select a valid organisation type.")
    if website and (len(website) > 255 or not re.match(r"^https?://", website, re.I)):
        return _error("Enter a website beginning with http:// or https://.")
    if len(reason) < 20 or len(reason) > 2000:
        return _error("Explain how you intend to use the workspace (20–2,000 characters).")
    if WorkspaceRequest.query.filter_by(user_id=current_user.user_id, status="pending").first():
        return _error("You already have an organisational workspace request awaiting review.", 409)
    record = WorkspaceRequest(
        user_id=current_user.user_id,
        organization_name=name,
        organization_type=kind,
        website=website or None,
        reason=reason,
        status="pending",
    )
    db.session.add(record)
    db.session.commit()
    return jsonify({"message": "Your organisational workspace request has been submitted for review."}), 201


@bp.get("/workspaces/<int:workspace_id>/members")
@login_required
def workspace_members(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can manage members.", 403)
    if membership.workspace.workspace_type != "organization":
        return _error("Personal workspaces cannot have additional members.", 400)
    records = WorkspaceMembership.query.filter_by(workspace_id=workspace_id, status="active").all()
    return jsonify({"members": [{"id": item.user.user_id, "full_name": item.user.full_name, "email": item.user.email, "role": item.role} for item in records]})


@bp.post("/workspaces/<int:workspace_id>/members")
@login_required
def add_workspace_member(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can manage members.", 403)
    if membership.workspace.workspace_type != "organization":
        return _error("Personal workspaces cannot have additional members.", 400)
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "member")).strip().lower()
    if role not in {"admin", "lecturer", "student", "member"}:
        return _error("Select a valid workspace role.")
    target = User.query.filter_by(email=email, is_active=True).first()
    if not target:
        return _error("No active AcaSift account was found for that email address.", 404)
    existing = WorkspaceMembership.query.filter_by(workspace_id=workspace_id, user_id=target.user_id).first()
    if existing and existing.status == "active":
        return _error("This user is already a member of the workspace.", 409)
    if existing:
        existing.role = role
        existing.status = "active"
    else:
        db.session.add(WorkspaceMembership(workspace_id=workspace_id, user_id=target.user_id, role=role, status="active"))
    db.session.commit()
    return jsonify({"message": f"{target.full_name} was added to the workspace."}), 201


@bp.get("/admin/workspace-requests")
@admin_required
def admin_workspace_requests():
    records = WorkspaceRequest.query.order_by(WorkspaceRequest.created_at.desc()).all()
    return jsonify({"requests": [{
        "id": item.request_id,
        "requester": item.requester.full_name,
        "requester_email": item.requester.email,
        "organization_name": item.organization_name,
        "organization_type": item.organization_type,
        "website": item.website,
        "reason": item.reason,
        "status": item.status,
        "created_at": _date(item.created_at),
        "review_notes": item.review_notes,
    } for item in records]})


@bp.post("/admin/workspace-requests/<int:request_id>/decision")
@admin_required
def decide_workspace_request(request_id):
    record = db.get_or_404(WorkspaceRequest, request_id)
    if record.status != "pending":
        return _error("This request has already been reviewed.", 409)
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).lower()
    notes = str(data.get("review_notes", "")).strip()
    if decision not in {"approve", "reject"}:
        return _error("Choose approve or reject.")
    if len(notes) > 2000:
        return _error("Review notes are too long.")
    if decision == "approve":
        workspace = Workspace(
            name=record.organization_name,
            workspace_type="organization",
            status="active",
            owner_user_id=record.user_id,
        )
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMembership(workspace_id=workspace.workspace_id, user_id=record.user_id, role="owner", status="active"))
        record.status = "approved"
    else:
        record.status = "rejected"
    record.reviewed_by_user_id = current_user.user_id
    record.review_notes = notes or None
    record.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": f"Workspace request {record.status} successfully."})


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
