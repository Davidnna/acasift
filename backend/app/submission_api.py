"""API for collaborative document submission and review requests."""

import hashlib
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Document, WorkspaceMembership
from app.services.auth_security import consume_auth_limits
from app.services.document_service import (
    calculate_sha256,
    extract_text,
    is_allowed_file,
    make_storage_filename,
)
from app.services.workspace_service import is_workspace_manager, membership_for
from app.services.submission_service import run_submission_request_comparison
from app.submission_models import (
    DocumentSubmission,
    SubmissionRequest,
    SubmissionRequestInvite,
    SubmissionRequestParticipant,
    SubmissionRequestReviewer,
    SubmissionReview,
)

bp = Blueprint("submission_api", __name__, url_prefix="/api")


def _now():
    return datetime.now(timezone.utc)


def _error(message, status=400):
    return jsonify({"error": message}), status


def _manager(membership):
    return bool(membership and membership.role in {"owner", "admin"})


def _participant(request_id, user_id):
    return SubmissionRequestParticipant.query.filter_by(
        request_id=request_id,
        user_id=user_id,
        status="active",
    ).first()


def _reviewer_access(submission_request, membership):
    if _manager(membership):
        return True
    if not membership:
        return False
    return SubmissionRequestReviewer.query.filter_by(
        request_id=submission_request.request_id,
        user_id=current_user.user_id,
    ).first() is not None


def _request_is_open_for_submission(item):
    if item.status != "open":
        return False
    now = _now()
    opens_at = item.opens_at
    if opens_at and opens_at.tzinfo is None:
        opens_at = opens_at.replace(tzinfo=timezone.utc)
    if opens_at and opens_at > now:
        return False
    due_at = item.due_at
    if due_at and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if due_at and due_at < now and not item.allow_late_submissions:
        return False
    return True


def _parse_datetime(value, field_name):
    if value in (None, ""):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Enter a valid {field_name} date and time.")
    if parsed.tzinfo is None:
        raise ValueError(f"The {field_name} date and time must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _invite_status(invite):
    if invite.revoked_at:
        return "revoked"
    expires_at = invite.expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= _now():
        return "expired"
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return "used_up"
    return "active"


def _invite_payload(invite):
    return {
        "id": invite.invite_id,
        "status": _invite_status(invite),
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "max_uses": invite.max_uses,
        "use_count": invite.use_count,
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
        "created_by": invite.creator.full_name if invite.creator else None,
    }


def _payload(item, include_counts=False):
    payload = {
        "id": item.request_id,
        "workspace_id": item.workspace_id,
        "workspace_name": item.workspace.name if item.workspace else None,
        "title": item.title,
        "description": item.description,
        "instructions": item.instructions,
        "opens_at": item.opens_at.isoformat() if item.opens_at else None,
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "status": item.status,
        "accepted_file_types": item.accepted_file_types or [],
        "max_file_size_mb": item.max_file_size_mb,
        "allow_late_submissions": bool(item.allow_late_submissions),
        "allow_resubmissions": item.allow_resubmissions,
        "allow_external_participants": item.allow_external_participants,
        "created_by": item.creator.full_name if item.creator else None,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
    if include_counts:
        payload["submission_count"] = DocumentSubmission.query.filter_by(
            request_id=item.request_id
        ).count()
        payload["participant_count"] = SubmissionRequestParticipant.query.filter_by(
            request_id=item.request_id,
            status="active",
        ).count()
        payload["reviewers"] = [{
            "id": reviewer.user_id,
            "full_name": reviewer.user.full_name,
            "email": reviewer.user.email,
        } for reviewer in item.reviewers]
        payload["invites"] = [
            _invite_payload(invite) for invite in sorted(
                item.invitation_links,
                key=lambda record: record.created_at,
                reverse=True,
            )
        ]
    return payload


def _submission_payload(row, include_contributor=False):
    latest_review = SubmissionReview.query.filter_by(
        submission_id=row.submission_id
    ).order_by(SubmissionReview.reviewed_at.desc()).first()
    review_decision = latest_review.decision if latest_review else None

    payload = {
        "id": row.submission_id,
        "document_id": row.document_id,
        "title": row.document.title,
        "filename": row.document.original_filename,
        "status": row.status if include_contributor else "submitted",
        "attempt_number": row.attempt_number,
        "is_late": bool(row.is_late),
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "review": ({
            "decision": review_decision,
            "feedback": latest_review.feedback,
            "reviewer": latest_review.reviewer.full_name if latest_review.reviewer else None,
            "reviewed_at": latest_review.reviewed_at.isoformat() if latest_review.reviewed_at else None,
        } if latest_review else None),
    }
    if include_contributor:
        payload["comparison_id"] = row.comparison_id
        payload["comparison_status"] = row.comparison.status if row.comparison else "not_started"
        payload["contributor"] = {
            "id": row.contributor.user_id,
            "full_name": row.contributor.full_name,
            "email": row.contributor.email,
        }
    return payload


def _get_request_access(item):
    if (
        not item.workspace
        or item.workspace.status != "active"
        or item.workspace.workspace_type != "shared"
    ):
        return {
            "membership": None,
            "participant": None,
            "reviewer": None,
            "can_manage": False,
            "can_review": False,
            "can_view": False,
            "can_submit": False,
            "can_join": False,
        }
    membership = membership_for(current_user, item.workspace_id)
    participant = _participant(item.request_id, current_user.user_id)
    reviewer = SubmissionRequestReviewer.query.filter_by(
        request_id=item.request_id,
        user_id=current_user.user_id,
    ).first() if membership else None
    if membership and membership.workspace.workspace_type != "shared":
        membership = None
    can_manage = _manager(membership)
    can_review = can_manage or bool(reviewer)
    is_open = _request_is_open_for_submission(item)
    can_view = bool(can_manage or reviewer or participant or (membership and item.status == "open"))
    can_submit = bool(is_open and participant)
    return {
        "membership": membership,
        "participant": participant,
        "reviewer": reviewer,
        "can_manage": can_manage,
        "can_review": can_review,
        "can_view": can_view,
        "can_submit": can_submit,
        "can_join": bool(membership and is_open and not participant),
    }


def _new_participant(item, user_id, participation_type):
    existing = SubmissionRequestParticipant.query.filter_by(
        request_id=item.request_id,
        user_id=user_id,
    ).first()
    if existing:
        existing.status = "active"
        if participation_type == "external":
            existing.participation_type = "external"
        return existing
    participant = SubmissionRequestParticipant(
        request_id=item.request_id,
        user_id=user_id,
        participation_type=participation_type,
        status="active",
    )
    db.session.add(participant)
    return participant


@bp.get("/submission-requests")
@login_required
def list_submission_requests():
    workspace_id = request.args.get("workspace_id", type=int)
    if not workspace_id:
        return _error("Select a shared workspace.")
    membership = membership_for(current_user, workspace_id)
    if not membership or membership.workspace.workspace_type != "shared":
        return _error("You do not have access to this shared workspace.", 403)

    query = SubmissionRequest.query.filter_by(workspace_id=workspace_id)
    if not _manager(membership):
        reviewer_ids = db.session.query(SubmissionRequestReviewer.request_id).filter_by(
            user_id=current_user.user_id
        )
        participant_ids = db.session.query(SubmissionRequestParticipant.request_id).filter_by(
            user_id=current_user.user_id,
            status="active",
        )
        query = query.filter(or_(
            SubmissionRequest.status == "open",
            SubmissionRequest.request_id.in_(reviewer_ids.union(participant_ids)),
        ))

    items = query.order_by(SubmissionRequest.created_at.desc()).all()
    return jsonify({
        "workspace": {
            "id": workspace_id,
            "name": membership.workspace.name,
        },
        "can_manage": _manager(membership),
        "submission_requests": [
            _payload(item, include_counts=_manager(membership)) for item in items
        ],
    })


@bp.post("/submission-requests")
@login_required
def create_submission_request():
    data = request.get_json(silent=True) or {}
    try:
        workspace_id = int(data.get("workspace_id"))
    except (TypeError, ValueError):
        return _error("Select a valid shared workspace.")

    membership = membership_for(current_user, workspace_id)
    if not _manager(membership) or membership.workspace.workspace_type != "shared":
        return _error("Only workspace owners and administrators can create submission requests.", 403)

    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    instructions = str(data.get("instructions", "")).strip()
    if not title or len(title) > 180:
        return _error("Enter a title containing no more than 180 characters.")
    if len(description) > 5000 or len(instructions) > 10000:
        return _error("The description or instructions are too long.")

    accepted_types = data.get("accepted_file_types", ["pdf", "docx", "txt"])
    allowed_types = {"pdf", "docx", "txt"}
    if not isinstance(accepted_types, list) or not accepted_types:
        return _error("Select at least one accepted document format.")
    accepted_types = sorted({str(value).lower().lstrip(".") for value in accepted_types})
    if not set(accepted_types).issubset(allowed_types):
        return _error("One or more document formats are not supported.")

    maximum_allowed_size = max(1, int(current_app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)))
    max_size = data.get("max_file_size_mb", min(15, maximum_allowed_size))
    if isinstance(max_size, bool) or not isinstance(max_size, int) or not 1 <= max_size <= maximum_allowed_size:
        return _error(f"The maximum file size must be a whole number between 1 and {maximum_allowed_size} MB.")

    try:
        opens_at = _parse_datetime(data.get("opens_at"), "opening")
        due_at = _parse_datetime(data.get("due_at"), "deadline")
    except ValueError as exc:
        return _error(str(exc))
    if opens_at and due_at and due_at <= opens_at:
        return _error("The deadline must be later than the opening date and time.")

    allow_resubmissions = data.get("allow_resubmissions", False)
    allow_late = data.get("allow_late_submissions", False)
    allow_external = data.get("allow_external_participants", True)
    if not all(isinstance(value, bool) for value in (allow_resubmissions, allow_late, allow_external)):
        return _error("Submission settings must use valid true or false values.")

    item = SubmissionRequest(
        workspace_id=workspace_id,
        title=title,
        description=description or None,
        instructions=instructions or None,
        opens_at=opens_at,
        due_at=due_at,
        status="draft",
        accepted_file_types=accepted_types,
        max_file_size_mb=max_size,
        allow_late_submissions=allow_late,
        allow_resubmissions=allow_resubmissions,
        allow_external_participants=allow_external,
        created_by_user_id=current_user.user_id,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({
        "message": "Submission request created.",
        "submission_request": _payload(item, include_counts=True),
    }), 201


@bp.get("/submission-requests/<int:request_id>")
@login_required
def submission_request_detail(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if (
        not item
        or not item.workspace
        or item.workspace.status != "active"
        or item.workspace.workspace_type != "shared"
    ):
        return _error("Submission request not found.", 404)

    access = _get_request_access(item)
    if not access["can_view"]:
        return _error("You do not have access to this submission request.", 403)

    can_review = access["can_review"]
    submissions_query = DocumentSubmission.query.filter_by(request_id=request_id)
    if not can_review:
        submissions_query = submissions_query.filter_by(contributor_user_id=current_user.user_id)
    submissions = submissions_query.order_by(DocumentSubmission.submitted_at.desc()).all()

    workspace_members = []
    if access["can_manage"]:
        workspace_members = [{
            "id": member.user_id,
            "full_name": member.user.full_name,
            "email": member.user.email,
        } for member in WorkspaceMembership.query.filter_by(
            workspace_id=item.workspace_id,
            status="active",
        ).order_by(WorkspaceMembership.created_at.asc()).all() if member.role == "member"]

    return jsonify({
        "submission_request": _payload(item, include_counts=access["can_manage"]),
        "submissions": [
            _submission_payload(row, include_contributor=can_review) for row in submissions
        ],
        "workspace_members": workspace_members,
        "permissions": {
            "can_manage": access["can_manage"],
            "can_review": can_review,
            "can_submit": access["can_submit"],
            "can_join": access["can_join"],
            "is_participant": bool(access["participant"]),
            "is_external_participant": bool(
                access["participant"] and access["participant"].participation_type == "external"
            ),
        },
    })


@bp.post("/submission-requests/<int:request_id>/update")
@login_required
def update_submission_request(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _manager(membership):
        return _error("Only workspace owners and administrators can update this request.", 403)

    data = request.get_json(silent=True) or {}
    title = str(data.get("title", item.title)).strip()
    description = str(data.get("description", item.description or "")).strip()
    instructions = str(data.get("instructions", item.instructions or "")).strip()
    if not title or len(title) > 180:
        return _error("Enter a title containing no more than 180 characters.")
    if len(description) > 5000 or len(instructions) > 10000:
        return _error("The description or instructions are too long.")

    try:
        opens_at = _parse_datetime(data.get("opens_at", item.opens_at.isoformat() if item.opens_at else None), "opening")
        due_at = _parse_datetime(data.get("due_at", item.due_at.isoformat() if item.due_at else None), "deadline")
    except ValueError as exc:
        return _error(str(exc))
    if opens_at and due_at and due_at <= opens_at:
        return _error("The deadline must be later than the opening date and time.")

    item.title = title
    item.description = description or None
    item.instructions = instructions or None
    item.opens_at = opens_at
    item.due_at = due_at
    db.session.commit()
    return jsonify({"message": "Submission request updated.", "submission_request": _payload(item, include_counts=True)})


@bp.post("/submission-requests/<int:request_id>/invites")
@login_required
def create_submission_request_invite(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _manager(membership):
        return _error("Only workspace owners and administrators can create submission links.", 403)
    if not item.allow_external_participants:
        return _error("External submissions are disabled for this request.", 403)

    data = request.get_json(silent=True) or {}
    expires_at = None
    try:
        expires_at = _parse_datetime(data.get("expires_at"), "link expiration")
    except ValueError as exc:
        return _error(str(exc))
    if expires_at and expires_at <= _now():
        return _error("The link expiration must be in the future.")

    max_uses = data.get("max_uses")
    if max_uses not in (None, ""):
        if isinstance(max_uses, bool) or not isinstance(max_uses, int) or not 1 <= max_uses <= 10000:
            return _error("The maximum number of uses must be between 1 and 10,000.")
    else:
        max_uses = None

    raw_token = secrets.token_urlsafe(32)
    invite = SubmissionRequestInvite(
        request_id=request_id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        created_by_user_id=current_user.user_id,
        expires_at=expires_at,
        max_uses=max_uses,
    )
    db.session.add(invite)
    db.session.commit()
    public_url = current_app.config["PUBLIC_APP_URL"].rstrip("/")
    join_url = f"{public_url}/join-submission-request?token={quote(raw_token, safe='')}"
    response = jsonify({
        "message": "Submission link created. Copy it now; the secret token cannot be recovered later.",
        "invite": _invite_payload(invite),
        "join_url": join_url,
    })
    response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/submission-requests/<int:request_id>/invites/<int:invite_id>/revoke")
@login_required
def revoke_submission_request_invite(request_id, invite_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _manager(membership):
        return _error("Only workspace owners and administrators can revoke submission links.", 403)
    invite = SubmissionRequestInvite.query.filter_by(
        invite_id=invite_id,
        request_id=request_id,
    ).first()
    if not invite:
        return _error("Submission link not found.", 404)
    if invite.revoked_at:
        return _error("This submission link has already been revoked.", 409)
    invite.revoked_at = _now()
    db.session.commit()
    return jsonify({"message": "Submission link revoked."})


@bp.get("/submission-request-invites/preview")
@login_required
def preview_submission_request_invite():
    if not current_user.email_verified_at:
        return _error("Verify your email address before accepting a submission link.", 403)
    raw_token = str(request.args.get("token", "")).strip()
    if len(raw_token) < 30 or len(raw_token) > 200:
        return _error("This submission link is invalid.", 404)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invite = SubmissionRequestInvite.query.filter_by(token_hash=token_hash).first()
    if not invite:
        return _error("This submission link is invalid or no longer exists.", 404)
    status = _invite_status(invite)
    if status != "active":
        return _error("This submission link is no longer active.", 410)
    item = invite.request
    if (
        not item
        or not item.workspace
        or item.workspace.status != "active"
        or item.workspace.workspace_type != "shared"
        or item.status != "open"
        or not item.allow_external_participants
    ):
        return _error("This submission request is not accepting external participants.", 410)
    existing = _participant(item.request_id, current_user.user_id)
    response = jsonify({
        "submission_request": _payload(item),
        "invited_by": invite.creator.full_name if invite.creator else "A workspace administrator",
        "already_joined": bool(existing),
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/submission-request-invites/accept")
@login_required
def accept_submission_request_invite():
    if not current_user.email_verified_at:
        return _error("Verify your email address before accepting a submission link.", 403)
    limited = consume_auth_limits(
        "submission_request_invite_accept",
        identity=current_user.user_id,
        ip_limit=40,
        identity_limit=20,
        window_seconds=900,
    )
    if limited:
        payload, status, retry_after = limited
        response = jsonify(payload)
        response.status_code = status
        response.headers["Retry-After"] = str(retry_after)
        response.headers["Cache-Control"] = "no-store"
        return response

    data = request.get_json(silent=True) or {}
    raw_token = str(data.get("token", "")).strip()
    if len(raw_token) < 30 or len(raw_token) > 200:
        return _error("This submission link is invalid.", 404)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invite = SubmissionRequestInvite.query.filter_by(token_hash=token_hash).with_for_update().first()
    if not invite:
        return _error("This submission link is invalid or no longer exists.", 404)

    existing = _participant(invite.request_id, current_user.user_id)
    if existing:
        return jsonify({
            "message": "You already have access to this submission request.",
            "request_id": invite.request_id,
        })
    if _invite_status(invite) != "active":
        return _error("This submission link is no longer active.", 410)
    item = invite.request
    if (
        not item
        or not item.workspace
        or item.workspace.status != "active"
        or item.workspace.workspace_type != "shared"
        or item.status != "open"
        or not item.allow_external_participants
    ):
        return _error("This submission request is not accepting external participants.", 410)

    participation_type = "member" if membership_for(current_user, item.workspace_id) else "external"
    _new_participant(item, current_user.user_id, participation_type)
    invite.use_count += 1
    db.session.commit()
    return jsonify({
        "message": "You now have access to this submission request.",
        "request_id": item.request_id,
    }), 201


@bp.post("/submission-requests/<int:request_id>/reviewers")
@login_required
def assign_submission_reviewer(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _manager(membership):
        return _error("Only workspace owners and administrators can assign reviewers.", 403)
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError):
        return _error("Select a valid workspace member.")
    target = WorkspaceMembership.query.filter_by(
        workspace_id=item.workspace_id,
        user_id=user_id,
        status="active",
    ).first()
    if not target:
        return _error("Reviewers must be active members of this workspace.", 400)
    if target.role in {"owner", "admin"}:
        return _error("Workspace administrators already have review access.", 400)
    existing = SubmissionRequestReviewer.query.filter_by(
        request_id=request_id,
        user_id=user_id,
    ).first()
    if existing:
        return jsonify({"message": "This member is already a reviewer."})
    db.session.add(SubmissionRequestReviewer(
        request_id=request_id,
        user_id=user_id,
        assigned_by_user_id=current_user.user_id,
    ))
    db.session.commit()
    return jsonify({"message": "Reviewer access granted."}), 201


@bp.delete("/submission-requests/<int:request_id>/reviewers/<int:user_id>")
@login_required
def remove_submission_reviewer(request_id, user_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _manager(membership):
        return _error("Only workspace owners and administrators can manage reviewers.", 403)
    reviewer = SubmissionRequestReviewer.query.filter_by(
        request_id=request_id,
        user_id=user_id,
    ).first()
    if not reviewer:
        return _error("Reviewer access record not found.", 404)
    db.session.delete(reviewer)
    db.session.commit()
    return jsonify({"message": "Reviewer access removed."})


@bp.post("/submission-requests/<int:request_id>/participate")
@login_required
def join_submission_request(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not membership or membership.workspace.workspace_type != "shared":
        return _error("Only members of this shared workspace can join directly.", 403)
    if not _request_is_open_for_submission(item):
        return _error("This submission request is not currently accepting submissions.", 409)
    _new_participant(item, current_user.user_id, "member")
    db.session.commit()
    return jsonify({"message": "You joined this submission request."}), 201


@bp.post("/submission-requests/<int:request_id>/submissions")
@login_required
def upload_submission_request_document(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    access = _get_request_access(item)
    if not access["membership"] and not access["participant"]:
        return _error("You do not have permission to submit to this request.", 403)
    if not access["can_submit"]:
        return _error("This submission request is not currently accepting submissions.", 409)

    limited = consume_auth_limits(
        "submission_request_upload",
        identity=current_user.user_id,
        ip_limit=30,
        identity_limit=20,
        window_seconds=3600,
    )
    if limited:
        payload, status, retry_after = limited
        response = jsonify(payload)
        response.status_code = status
        response.headers["Retry-After"] = str(retry_after)
        response.headers["Cache-Control"] = "no-store"
        return response

    file_storage = request.files.get("document")
    if not file_storage or not file_storage.filename:
        return _error("Choose a document to submit.")
    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        return _error("The uploaded filename is invalid.")
    extension = os.path.splitext(original_filename)[1].lower().lstrip(".")
    if extension not in (item.accepted_file_types or []):
        return _error("This file format is not accepted for the submission request.")
    if not is_allowed_file(original_filename, current_app.config["ALLOWED_EXTENSIONS"]):
        return _error("Only PDF, DOCX and TXT documents are supported.")

    maximum_bytes = item.max_file_size_mb * 1024 * 1024
    file_bytes = file_storage.read(maximum_bytes + 1)
    if not file_bytes:
        return _error("The selected document is empty.")
    if len(file_bytes) > maximum_bytes:
        return _error(f"The document exceeds this request's {item.max_file_size_mb} MB limit.", 413)

    try:
        extracted_text = extract_text(original_filename, file_bytes)
    except ValueError as exc:
        return _error(str(exc))

    existing_submissions = DocumentSubmission.query.filter_by(
        request_id=request_id,
        contributor_user_id=current_user.user_id,
    ).order_by(DocumentSubmission.attempt_number.desc()).all()
    if existing_submissions and not item.allow_resubmissions:
        return _error("This request does not allow another submission from your account.", 409)

    now = _now()
    due_at = item.due_at
    if due_at and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    is_late = bool(due_at and now > due_at)
    title = str(request.form.get("title", "")).strip()
    if len(title) > 255:
        return _error("The document title cannot exceed 255 characters.")
    title = title or os.path.splitext(original_filename)[0]

    storage_name = make_storage_filename(original_filename)
    storage_path = os.path.join(current_app.config["UPLOAD_FOLDER"], storage_name)
    try:
        os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
        with open(storage_path, "wb") as stored_file:
            stored_file.write(file_bytes)

        document = Document(
            user_id=current_user.user_id,
            title=title[:255],
            original_filename=original_filename[:255],
            storage_path=storage_name,
            file_type=extension,
            document_type="submission",
            extracted_text=extracted_text,
            file_hash=calculate_sha256(file_bytes),
            workspace_id=item.workspace_id,
            visibility_scope="private",
            processing_status="processed",
        )
        db.session.add(document)
        db.session.flush()
        submission = DocumentSubmission(
            request_id=request_id,
            contributor_user_id=current_user.user_id,
            document_id=document.document_id,
            attempt_number=(existing_submissions[0].attempt_number + 1) if existing_submissions else 1,
            status="submitted",
            is_late=is_late,
            submitted_at=now,
        )
        db.session.add(submission)
        db.session.flush()
        _new_participant(
            item,
            current_user.user_id,
            "external" if access["participant"] and access["participant"].participation_type == "external" else "member",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        if os.path.exists(storage_path):
            os.remove(storage_path)
        current_app.logger.exception("Could not store submission for request %s.", request_id)
        return _error("The document could not be saved. Please try again.", 500)

    comparison = run_submission_request_comparison(submission)
    db.session.refresh(submission)
    # Similarity analysis is retained for authorised reviewers. Contributors
    # receive a submission receipt and any reviewer feedback, not analysis data.
    return jsonify({
        "message": "Your document was submitted successfully. You can return here to see reviewer feedback when it is available.",
        "submission": _submission_payload(submission),
    }), 201


@bp.post("/submission-requests/<int:request_id>/submissions/<int:submission_id>/review")
@login_required
def review_submission(request_id, submission_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _reviewer_access(item, membership):
        return _error("You do not have review access to this submission request.", 403)
    submission = DocumentSubmission.query.filter_by(
        submission_id=submission_id,
        request_id=request_id,
    ).first()
    if not submission:
        return _error("Submission not found in this request.", 404)

    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip().lower()
    feedback = str(data.get("feedback", "")).strip()
    if decision not in {"no_action", "revision_requested", "further_review"}:
        return _error("Select a valid review outcome.")
    if len(feedback) > 5000:
        return _error("Review feedback cannot exceed 5,000 characters.")

    review = SubmissionReview(
        submission_id=submission_id,
        reviewer_user_id=current_user.user_id,
        decision=decision,
        feedback=feedback or None,
        reviewed_at=_now(),
    )
    db.session.add(review)
    db.session.commit()
    return jsonify({"message": "Review saved successfully."}), 201


@bp.post("/submission-requests/<int:request_id>/status")
@login_required
def update_submission_request_status(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    if not _manager(membership):
        return _error("Only workspace owners and administrators can change request status.", 403)
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip().lower()
    if status not in {"draft", "open", "closed", "archived"}:
        return _error("Select a valid request status.")
    item.status = status
    db.session.commit()
    return jsonify({
        "message": "Submission request status updated.",
        "submission_request": _payload(item, include_counts=True),
    })
