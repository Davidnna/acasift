"""API foundation for generic document submission requests."""

from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import or_

from app.extensions import db
from app.models import WorkspaceMembership
from app.services.workspace_service import membership_for
from app.submission_models import (
    DocumentSubmission,
    SubmissionRequest,
    SubmissionRequestParticipant,
    SubmissionRequestReviewer,
)

bp = Blueprint("submission_api", __name__, url_prefix="/api")


def _error(message, status=400):
    return jsonify({"error": message}), status


def _manager(membership):
    return bool(membership and membership.role in {"owner", "admin"})


def _reviewer_access(submission_request, membership):
    if _manager(membership):
        return True
    return SubmissionRequestReviewer.query.filter_by(
        request_id=submission_request.request_id, user_id=current_user.user_id
    ).first() is not None


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


def _payload(item, include_counts=False):
    payload = {
        "id": item.request_id,
        "workspace_id": item.workspace_id,
        "title": item.title,
        "description": item.description,
        "instructions": item.instructions,
        "opens_at": item.opens_at.isoformat() if item.opens_at else None,
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "status": item.status,
        "accepted_file_types": item.accepted_file_types or [],
        "max_file_size_mb": item.max_file_size_mb,
        "allow_resubmissions": item.allow_resubmissions,
        "allow_external_participants": item.allow_external_participants,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }
    if include_counts:
        payload["submission_count"] = DocumentSubmission.query.filter_by(request_id=item.request_id).count()
        payload["participant_count"] = SubmissionRequestParticipant.query.filter_by(
            request_id=item.request_id, status="active"
        ).count()
    return payload


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
        reviewer_ids = db.session.query(SubmissionRequestReviewer.request_id).filter_by(user_id=current_user.user_id)
        participant_ids = db.session.query(SubmissionRequestParticipant.request_id).filter_by(
            user_id=current_user.user_id, status="active"
        )
        query = query.filter(
            or_(
                SubmissionRequest.status == "open",
                SubmissionRequest.request_id.in_(reviewer_ids.union(participant_ids)),
            )
        )
    items = query.order_by(SubmissionRequest.created_at.desc()).all()
    return jsonify({
        "submission_requests": [_payload(item, include_counts=_manager(membership)) for item in items]
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

    max_size = data.get("max_file_size_mb", 15)
    maximum_allowed_size = max(1, int(current_app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)))
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
    allow_external = data.get("allow_external_participants", True)
    if not isinstance(allow_resubmissions, bool) or not isinstance(allow_external, bool):
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
        allow_resubmissions=allow_resubmissions,
        allow_external_participants=allow_external,
        created_by_user_id=current_user.user_id,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"message": "Submission request created.", "submission_request": _payload(item)}), 201


@bp.get("/submission-requests/<int:request_id>")
@login_required
def submission_request_detail(request_id):
    item = db.session.get(SubmissionRequest, request_id)
    if not item:
        return _error("Submission request not found.", 404)
    membership = membership_for(current_user, item.workspace_id)
    participant = SubmissionRequestParticipant.query.filter_by(
        request_id=request_id, user_id=current_user.user_id, status="active"
    ).first()
    reviewer = SubmissionRequestReviewer.query.filter_by(
        request_id=request_id, user_id=current_user.user_id
    ).first()
    if not membership or membership.workspace.workspace_type != "shared":
        return _error("You do not have access to this submission request.", 403)
    can_discover_open_request = item.status == "open" and bool(membership)
    if not (_manager(membership) or participant or reviewer or can_discover_open_request):
        return _error("You do not have access to this submission request.", 403)

    can_review = _reviewer_access(item, membership)
    submissions_query = DocumentSubmission.query.filter_by(request_id=request_id)
    if not can_review:
        submissions_query = submissions_query.filter_by(contributor_user_id=current_user.user_id)
    submissions = submissions_query.order_by(DocumentSubmission.submitted_at.desc()).all()
    return jsonify({
        "submission_request": _payload(item, include_counts=_manager(membership)),
        "submissions": [{
            "id": row.submission_id,
            "document_id": row.document_id,
            "status": row.status,
            "attempt_number": row.attempt_number,
            "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        } for row in submissions],
        "permissions": {
            "can_manage": _manager(membership),
            "can_review": can_review,
            "can_submit": bool((participant or membership) and item.status == "open"),
        },
    })


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
        workspace_id=item.workspace_id, user_id=user_id, status="active"
    ).first()
    if not target:
        return _error("Reviewers must be active members of this workspace.", 400)
    if target.role in {"owner", "admin"}:
        return _error("Workspace administrators already have review access.", 400)
    existing = SubmissionRequestReviewer.query.filter_by(request_id=request_id, user_id=user_id).first()
    if existing:
        return jsonify({"message": "This member is already a reviewer."})
    db.session.add(SubmissionRequestReviewer(
        request_id=request_id, user_id=user_id, assigned_by_user_id=current_user.user_id
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
    reviewer = SubmissionRequestReviewer.query.filter_by(request_id=request_id, user_id=user_id).first()
    if not reviewer:
        return _error("Reviewer assignment not found.", 404)
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
        return _error("You do not have access to this submission request.", 403)
    if item.status != "open":
        return _error("This submission request is not currently accepting participants.", 409)
    participant = SubmissionRequestParticipant.query.filter_by(
        request_id=request_id, user_id=current_user.user_id
    ).first()
    if participant:
        if participant.status != "active":
            participant.status = "active"
        db.session.commit()
        return jsonify({"message": "You are participating in this request."})
    db.session.add(SubmissionRequestParticipant(
        request_id=request_id, user_id=current_user.user_id, participation_type="member"
    ))
    db.session.commit()
    return jsonify({"message": "You joined this submission request."}), 201


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
    return jsonify({"message": "Submission request status updated.", "submission_request": _payload(item)})
