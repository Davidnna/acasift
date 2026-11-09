import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request, session
from flask_login import current_user, login_required
from sqlalchemy import case

from app.extensions import db
from app.models import (
    Course,
    CourseMembership,
    User,
    Workspace,
    WorkspaceInvite,
    WorkspaceMembership,
)
from app.services.auth_security import consume_auth_limits
from app.services.workspace_service import (
    ensure_personal_workspace,
    get_active_workspace,
    is_workspace_manager,
    membership_for,
)

bp = Blueprint("workspace_api", __name__, url_prefix="/api")


def _date(value):
    return value.isoformat() if value else None


def _error(message, status=400):
    return jsonify({"error": message}), status


def _workspace_payload(workspace, membership=None):
    return {
        "id": workspace.workspace_id,
        "name": workspace.name,
        "description": workspace.description,
        "type": workspace.workspace_type,
        "status": workspace.status,
        "role": membership.role if membership else None,
        "is_owner": bool(membership and membership.role == "owner"),
        "member_count": WorkspaceMembership.query.filter_by(
            workspace_id=workspace.workspace_id, status="active"
        ).count(),
        "created_at": _date(workspace.created_at),
    }


def _invite_expired(invite):
    expires_at = invite.expires_at
    if not expires_at:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def _invite_status(invite):
    if invite.revoked_at:
        return "revoked"
    if _invite_expired(invite):
        return "expired"
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return "used_up"
    return "active"


def _invite_payload(invite):
    return {
        "id": invite.invite_id,
        "role": invite.role,
        "course_id": invite.course_id,
        "course_title": invite.course.title if invite.course else None,
        "course_code": invite.course.code if invite.course else None,
        "status": _invite_status(invite),
        "expires_at": _date(invite.expires_at),
        "max_uses": invite.max_uses,
        "use_count": invite.use_count,
        "created_at": _date(invite.created_at),
        "created_by": invite.creator.full_name if invite.creator else None,
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
    active_membership = membership_for(current_user, active.workspace_id)
    members = []
    invites = []
    if is_workspace_manager(active_membership) and active.workspace_type == "shared":
        members = [{
            "id": item.user.user_id,
            "full_name": item.user.full_name,
            "email": item.user.email,
            "role": item.role,
        } for item in WorkspaceMembership.query.filter_by(
            workspace_id=active.workspace_id, status="active"
        ).order_by(WorkspaceMembership.created_at.asc()).all()]
        invites = [
            _invite_payload(item) for item in WorkspaceInvite.query.filter_by(
                workspace_id=active.workspace_id
            ).order_by(WorkspaceInvite.created_at.desc()).all()
        ]
    workspace_courses = []
    if is_workspace_manager(active_membership) and active.workspace_type == "shared":
        workspace_courses = [{
            "id": item.course_id,
            "code": item.code,
            "title": item.title,
            "status": item.status,
        } for item in Course.query.filter_by(
            workspace_id=active.workspace_id, status="active"
        ).order_by(Course.code.asc()).all()]
    return jsonify({
        "active_workspace_id": active.workspace_id,
        "workspaces": [_workspace_payload(item.workspace, item) for item in memberships],
        "pending_request": None,
        "can_manage_members": bool(
            is_workspace_manager(active_membership) and active.workspace_type == "shared"
        ),
        "is_workspace_owner": bool(active_membership and active_membership.role == "owner"),
        "members": members,
        "invites": invites,
        "courses": workspace_courses,
    })


@bp.post("/workspaces")
@login_required
def create_shared_workspace():
    limited = consume_auth_limits(
        "workspace_create", identity=current_user.user_id,
        ip_limit=20, identity_limit=10, window_seconds=3600,
    )
    if limited:
        payload, status, retry_after = limited
        response = jsonify(payload)
        response.status_code = status
        response.headers["Retry-After"] = str(retry_after)
        response.headers["Cache-Control"] = "no-store"
        return response
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name or len(name) > 180:
        return _error("Enter a workspace name containing no more than 180 characters.")
    if len(description) > 2000:
        return _error("The workspace description cannot exceed 2,000 characters.")

    workspace = Workspace(
        name=name,
        description=description or None,
        workspace_type="shared",
        status="active",
        owner_user_id=current_user.user_id,
    )
    db.session.add(workspace)
    db.session.flush()
    membership = WorkspaceMembership(
        workspace_id=workspace.workspace_id,
        user_id=current_user.user_id,
        role="owner",
        status="active",
    )
    db.session.add(membership)
    db.session.commit()
    session["active_workspace_id"] = workspace.workspace_id
    return jsonify({
        "message": "Shared workspace created successfully.",
        "workspace": _workspace_payload(workspace, membership),
    }), 201


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


@bp.get("/workspaces/<int:workspace_id>/members")
@login_required
def workspace_members(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can manage members.", 403)
    if membership.workspace.workspace_type != "shared":
        return _error("Personal workspaces cannot have additional members.", 400)
    records = WorkspaceMembership.query.filter_by(workspace_id=workspace_id, status="active").all()
    return jsonify({"members": [{
        "id": item.user.user_id,
        "full_name": item.user.full_name,
        "email": item.user.email,
        "role": item.role,
    } for item in records]})


@bp.post("/workspaces/<int:workspace_id>/members")
@login_required
def add_workspace_member(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can manage members.", 403)
    if membership.workspace.workspace_type != "shared":
        return _error("Personal workspaces cannot have additional members.", 400)
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "member")).strip().lower()
    if role not in {"admin", "lecturer", "student", "member"}:
        return _error("Select a valid workspace role.")
    if role == "admin" and membership.role != "owner":
        return _error("Only the workspace owner can appoint another administrator.", 403)
    target = User.query.filter_by(email=email, is_active=True).first()
    if not target:
        return _error("No active AcaSift account was found for that email address.", 404)
    if target.user_id == membership.workspace.owner_user_id:
        return _error("The workspace owner already has owner privileges.", 409)
    existing = WorkspaceMembership.query.filter_by(workspace_id=workspace_id, user_id=target.user_id).first()
    if existing and existing.status == "active":
        return _error("This user is already a member of the workspace.", 409)
    if existing:
        existing.role = role
        existing.status = "active"
    else:
        db.session.add(WorkspaceMembership(
            workspace_id=workspace_id, user_id=target.user_id, role=role, status="active"
        ))
    db.session.commit()
    return jsonify({"message": f"{target.full_name} was added to the workspace."}), 201


@bp.post("/workspaces/<int:workspace_id>/members/<int:user_id>/role")
@login_required
def update_workspace_member_role(workspace_id, user_id):
    actor_membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(actor_membership):
        return _error("Only workspace owners and administrators can manage member roles.", 403)
    if actor_membership.workspace.workspace_type != "shared":
        return _error("Personal workspaces do not have additional members.", 400)
    target = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id, user_id=user_id, status="active"
    ).first()
    if not target:
        return _error("Workspace member not found.", 404)
    if target.role == "owner":
        return _error("Workspace ownership cannot be changed through member-role management.", 403)
    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "")).strip().lower()
    if role not in {"admin", "lecturer", "student", "member"}:
        return _error("Select a valid workspace role.")
    if (role == "admin" or target.role == "admin") and actor_membership.role != "owner":
        return _error("Only the workspace owner can appoint or change an administrator.", 403)
    target.role = role
    db.session.commit()
    return jsonify({"message": f"{target.user.full_name}'s workspace role was updated.", "role": role})


@bp.post("/workspaces/<int:workspace_id>/members/<int:user_id>/remove")
@login_required
def remove_workspace_member(workspace_id, user_id):
    actor_membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(actor_membership):
        return _error("Only workspace owners and administrators can remove members.", 403)
    target = WorkspaceMembership.query.filter_by(
        workspace_id=workspace_id, user_id=user_id, status="active"
    ).first()
    if not target:
        return _error("Workspace member not found.", 404)
    if target.role == "owner":
        return _error("The workspace owner cannot be removed.", 403)
    if target.role == "admin" and actor_membership.role != "owner":
        return _error("Only the workspace owner can remove another administrator.", 403)
    target.status = "removed"
    db.session.commit()
    return jsonify({"message": f"{target.user.full_name} was removed from the workspace."})


@bp.post("/workspaces/<int:workspace_id>/manage")
@login_required
def manage_workspace(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("You do not have permission to manage this workspace.", 403)
    workspace = membership.workspace
    if workspace.workspace_type != "shared":
        return _error("Personal workspace details cannot be changed here.", 400)

    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name or len(name) > 180:
        return _error("Enter a workspace name containing no more than 180 characters.")
    if len(description) > 2000:
        return _error("The workspace description cannot exceed 2,000 characters.")

    workspace.name = name
    workspace.description = description or None
    db.session.commit()
    return jsonify({"message": "Workspace details updated successfully.", "workspace": _workspace_payload(workspace, membership)})


@bp.post("/workspaces/<int:workspace_id>/leave")
@login_required
def leave_workspace(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not membership:
        return _error("You are not an active member of this workspace.", 404)
    workspace = membership.workspace
    if workspace.workspace_type != "shared":
        return _error("A personal workspace cannot be left. You can manage it from your account.", 400)

    now = datetime.now(timezone.utc)
    if membership.role == "owner":
        successors = WorkspaceMembership.query.filter(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.status == "active",
            WorkspaceMembership.user_id != current_user.user_id,
        ).order_by(
            case(
                (WorkspaceMembership.role == "admin", 0),
                (WorkspaceMembership.role == "lecturer", 1),
                (WorkspaceMembership.role == "student", 2),
                else_=3,
            ),
            WorkspaceMembership.created_at.asc(),
            WorkspaceMembership.membership_id.asc(),
        ).all()

        if successors:
            successor = successors[0]
            successor.role = "owner"
            workspace.owner_user_id = successor.user_id
            message = f"You left the workspace. Ownership has been transferred to {successor.user.full_name}."
        else:
            workspace.status = "deleted"
            for invite in WorkspaceInvite.query.filter_by(workspace_id=workspace_id).all():
                invite.revoked_at = now
            message = "You left the workspace. As no other members remained, the workspace was closed."
    else:
        message = "You have left the workspace."

    membership.status = "left"
    course_memberships = CourseMembership.query.join(Course).filter(
        Course.workspace_id == workspace_id,
        CourseMembership.user_id == current_user.user_id,
        CourseMembership.status == "active",
    ).all()
    for course_membership in course_memberships:
        course_membership.status = "left"

    if session.get("active_workspace_id") == workspace_id:
        session.pop("active_workspace_id", None)
    db.session.commit()
    if session.get("active_workspace_id") is None:
        personal = ensure_personal_workspace(current_user)
        session["active_workspace_id"] = personal.workspace_id
        db.session.commit()
    return jsonify({"message": message, "workspace_id": workspace_id})


@bp.delete("/workspaces/<int:workspace_id>")
@login_required
def delete_workspace(workspace_id):
    membership = membership_for(current_user, workspace_id)
    if not membership or membership.role != "owner":
        return _error("Only the workspace owner can delete this workspace.", 403)
    workspace = membership.workspace
    if workspace.workspace_type != "shared":
        return _error("Personal workspaces cannot be deleted from workspace management.", 400)

    now = datetime.now(timezone.utc)
    workspace.status = "deleted"
    for member in WorkspaceMembership.query.filter_by(workspace_id=workspace_id, status="active").all():
        member.status = "removed"
    for invite in WorkspaceInvite.query.filter_by(workspace_id=workspace_id).all():
        invite.revoked_at = now
    db.session.commit()

    if session.get("active_workspace_id") == workspace_id:
        session.pop("active_workspace_id", None)
    personal = ensure_personal_workspace(current_user)
    session["active_workspace_id"] = personal.workspace_id
    db.session.commit()
    return jsonify({"message": "Workspace deleted successfully."})


@bp.post("/workspaces/<int:workspace_id>/invites")
@login_required
def create_workspace_invite(workspace_id):
    limited = consume_auth_limits(
        "workspace_invite_create", identity=current_user.user_id,
        ip_limit=40, identity_limit=30, window_seconds=900,
    )
    if limited:
        payload, status, retry_after = limited
        response = jsonify(payload)
        response.status_code = status
        response.headers["Retry-After"] = str(retry_after)
        response.headers["Cache-Control"] = "no-store"
        return response
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can create invitation links.", 403)
    workspace = membership.workspace
    if workspace.workspace_type != "shared":
        return _error("Personal workspaces cannot issue invitation links.", 400)

    data = request.get_json(silent=True) or {}
    role = str(data.get("role", "member")).strip().lower()
    if role not in {"member", "student", "lecturer"}:
        return _error("Invitation links can grant Member, Student or Lecturer access. Administrators must be appointed directly by the owner.")

    expires_at = None
    raw_expiry = data.get("expires_at")
    if raw_expiry:
        try:
            expires_at = datetime.fromisoformat(str(raw_expiry).replace("Z", "+00:00"))
        except ValueError:
            return _error("Enter a valid invitation expiration date and time.")
        if expires_at.tzinfo is None:
            return _error("Invitation expiration must include a timezone.")
        expires_at = expires_at.astimezone(timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return _error("The invitation expiration must be in the future.")

    course_id = data.get("course_id")
    course = None
    if course_id not in (None, ""):
        try:
            course_id = int(course_id)
        except (TypeError, ValueError):
            return _error("Select a valid course for this invitation.")
        course = Course.query.filter_by(
            course_id=course_id, workspace_id=workspace_id, status="active"
        ).first()
        if not course:
            return _error("The selected course does not belong to this active workspace.", 404)
        if role not in {"student", "lecturer"}:
            return _error("Course-specific invitations must grant the Student or Lecturer role.")

    max_uses = data.get("max_uses")
    if max_uses not in (None, ""):
        if isinstance(max_uses, bool):
            return _error("The maximum number of uses must be a whole number.")
        try:
            parsed_uses = int(max_uses)
        except (TypeError, ValueError):
            return _error("The maximum number of uses must be a whole number.")
        if str(max_uses).strip() != str(parsed_uses):
            return _error("The maximum number of uses must be a whole number.")
        max_uses = parsed_uses
        if max_uses < 1 or max_uses > 10000:
            return _error("The maximum number of uses must be between 1 and 10,000.")
    else:
        max_uses = None

    raw_token = secrets.token_urlsafe(32)
    invite = WorkspaceInvite(
        workspace_id=workspace_id,
        course_id=course.course_id if course else None,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        role=role,
        created_by_user_id=current_user.user_id,
        expires_at=expires_at,
        max_uses=max_uses,
        use_count=0,
    )
    db.session.add(invite)
    db.session.commit()
    public_url = current_app.config["PUBLIC_APP_URL"].rstrip("/")
    join_url = f"{public_url}/join-workspace?token={quote(raw_token, safe='')}"
    response = jsonify({
        "message": "Workspace invitation link created. Copy it now; the secret token is not stored in recoverable form.",
        "invite": _invite_payload(invite),
        "join_url": join_url,
    })
    response.status_code = 201
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/workspaces/invites/preview")
@login_required
def preview_workspace_invite():
    raw_token = str(request.args.get("token", "")).strip()
    if len(raw_token) < 30 or len(raw_token) > 200:
        return _error("This invitation link is invalid.", 404)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invite = WorkspaceInvite.query.filter_by(token_hash=token_hash).first()
    if not invite:
        return _error("This invitation link is invalid or no longer exists.", 404)
    status = _invite_status(invite)
    if status != "active":
        messages = {
            "revoked": "This invitation link has been revoked.",
            "expired": "This invitation link is no longer available.",
            "used_up": "This invitation link has reached its usage limit.",
        }
        return _error(messages.get(status, "This invitation link is no longer active."), 410)
    if invite.workspace.status != "active":
        return _error("This workspace is no longer active.", 410)
    if invite.course_id and (not invite.course or invite.course.status != "active"):
        return _error("The course associated with this invitation is no longer active.", 410)
    existing = WorkspaceMembership.query.filter_by(
        workspace_id=invite.workspace_id, user_id=current_user.user_id, status="active"
    ).first()
    course_membership = None
    if invite.course_id:
        course_membership = CourseMembership.query.filter_by(
            course_id=invite.course_id, user_id=current_user.user_id, status="active"
        ).first()
    response = jsonify({
        "workspace": _workspace_payload(invite.workspace),
        "role": invite.role,
        "course": ({
            "id": invite.course.course_id,
            "code": invite.course.code,
            "title": invite.course.title,
        } if invite.course else None),
        "is_member": bool(existing),
        "is_course_member": bool(course_membership and course_membership.role == invite.role),
        "invited_by": invite.creator.full_name if invite.creator else "A workspace administrator",
    })
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.post("/workspaces/invites/accept")
@login_required
def accept_workspace_invite():
    limited = consume_auth_limits(
        "workspace_invite_accept", identity=current_user.user_id,
        ip_limit=40, identity_limit=20, window_seconds=900,
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
        return _error("This invitation link is invalid.", 404)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invite = WorkspaceInvite.query.filter_by(token_hash=token_hash).with_for_update().first()
    if not invite or invite.workspace.status != "active":
        return _error("This invitation link is invalid or no longer available.", 404)
    status = _invite_status(invite)
    if status != "active":
        messages = {
            "revoked": "This invitation link has been revoked.",
            "expired": "This invitation link is no longer available.",
            "used_up": "This invitation link has reached its usage limit.",
        }
        return _error(messages.get(status, "This invitation link is no longer active."), 410)

    existing = WorkspaceMembership.query.filter_by(
        workspace_id=invite.workspace_id, user_id=current_user.user_id
    ).first()
    already_active = bool(existing and existing.status == "active")
    workspace_role_updated = False
    if existing:
        if not already_active:
            existing.status = "active"
            # A removed member must rejoin with the role granted by this invite;
            # an old administrator role must never be silently restored.
            existing.role = invite.role
            workspace_role_updated = True
        elif existing.role not in {"owner", "admin"} and existing.role != invite.role:
            existing.role = invite.role
            workspace_role_updated = True
    else:
        db.session.add(WorkspaceMembership(
            workspace_id=invite.workspace_id,
            user_id=current_user.user_id,
            role=invite.role,
            status="active",
        ))

    enrolled_in_course = False
    if invite.course_id:
        if not invite.course or invite.course.status != "active":
            return _error("The course associated with this invitation is no longer active.", 410)
        course_membership = CourseMembership.query.filter_by(
            course_id=invite.course_id, user_id=current_user.user_id
        ).first()
        if not course_membership or course_membership.status != "active" or course_membership.role != invite.role:
            if course_membership:
                course_membership.status = "active"
                course_membership.role = invite.role
                course_membership.added_by_user_id = invite.created_by_user_id
                course_membership.enrolled_at = datetime.now(timezone.utc)
            else:
                db.session.add(CourseMembership(
                    course_id=invite.course_id,
                    user_id=current_user.user_id,
                    role=invite.role,
                    status="active",
                    added_by_user_id=invite.created_by_user_id,
                ))
            enrolled_in_course = True

    if already_active and not enrolled_in_course and not workspace_role_updated:
        session["active_workspace_id"] = invite.workspace_id
        return jsonify({"message": "You are already a member of this workspace.", "workspace_id": invite.workspace_id})

    invite.use_count += 1
    db.session.commit()
    session["active_workspace_id"] = invite.workspace_id
    if enrolled_in_course:
        message = f"You joined {invite.workspace.name} and enrolled in {invite.course.code}."
    elif already_active:
        message = f"You were already a member of {invite.workspace.name}."
    else:
        message = f"You have joined {invite.workspace.name}."
    return jsonify({
        "message": message,
        "workspace_id": invite.workspace_id,
        "course_id": invite.course_id,
    }), 201


@bp.post("/workspaces/<int:workspace_id>/invites/<int:invite_id>/revoke")
@login_required
def revoke_workspace_invite(workspace_id, invite_id):
    membership = membership_for(current_user, workspace_id)
    if not is_workspace_manager(membership):
        return _error("Only workspace owners and administrators can revoke invitation links.", 403)
    invite = WorkspaceInvite.query.filter_by(
        invite_id=invite_id, workspace_id=workspace_id
    ).first()
    if not invite:
        return _error("Invitation link not found.", 404)
    if invite.revoked_at:
        return _error("This invitation link has already been revoked.", 409)
    invite.revoked_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Invitation link revoked successfully."})


