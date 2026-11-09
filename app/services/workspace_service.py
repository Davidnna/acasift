from flask import session

from app.extensions import db
from app.models import Comparison, Document, Workspace, WorkspaceMembership


def ensure_personal_workspace(user):
    membership = (
        WorkspaceMembership.query.join(Workspace)
        .filter(WorkspaceMembership.user_id == user.user_id, Workspace.workspace_type == "personal")
        .first()
    )
    if membership:
        workspace = membership.workspace
    else:
        workspace = Workspace(
            name=f"{user.full_name}'s workspace"[:180],
            workspace_type="personal", status="active", owner_user_id=user.user_id,
        )
        db.session.add(workspace)
        db.session.flush()
        db.session.add(WorkspaceMembership(
            workspace_id=workspace.workspace_id, user_id=user.user_id, role="owner", status="active"
        ))
        db.session.flush()

    Document.query.filter(
        Document.user_id == user.user_id, Document.document_type == "submission", Document.workspace_id.is_(None)
    ).update({"workspace_id": workspace.workspace_id, "visibility_scope": "private"}, synchronize_session=False)
    Comparison.query.filter(
        Comparison.user_id == user.user_id, Comparison.workspace_id.is_(None)
    ).update({"workspace_id": workspace.workspace_id}, synchronize_session=False)
    return workspace


def get_active_workspace(user):
    selected_id = session.get("active_workspace_id")
    if selected_id:
        membership = WorkspaceMembership.query.join(Workspace).filter(
            WorkspaceMembership.user_id == user.user_id,
            WorkspaceMembership.workspace_id == selected_id,
            WorkspaceMembership.status == "active", Workspace.status == "active",
        ).first()
        if membership:
            return membership.workspace
    personal = ensure_personal_workspace(user)
    session["active_workspace_id"] = personal.workspace_id
    db.session.commit()
    return personal


def membership_for(user, workspace_id):
    return WorkspaceMembership.query.join(Workspace).filter(
        WorkspaceMembership.user_id == user.user_id,
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.status == "active", Workspace.status == "active",
    ).first()


def is_workspace_manager(membership):
    return bool(membership and membership.role in {"owner", "admin"})
