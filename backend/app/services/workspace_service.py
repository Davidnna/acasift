from flask import session

from app.models import Workspace, WorkspaceMembership


def membership_for(user, workspace_id):
    """Return an active membership in a live shared workspace only."""
    if not workspace_id or not getattr(user, "is_authenticated", False):
        return None
    return WorkspaceMembership.query.join(Workspace).filter(
        WorkspaceMembership.user_id == user.user_id,
        WorkspaceMembership.workspace_id == workspace_id,
        WorkspaceMembership.status == "active",
        Workspace.status == "active",
        Workspace.workspace_type == "shared",
    ).first()


def get_active_workspace(user):
    """Resolve the user's selected shared workspace without creating one."""
    if not getattr(user, "is_authenticated", False):
        session.pop("active_workspace_id", None)
        return None

    selected_id = session.get("active_workspace_id")
    if selected_id:
        membership = membership_for(user, selected_id)
        if membership:
            return membership.workspace

    membership = (
        WorkspaceMembership.query.join(Workspace)
        .filter(
            WorkspaceMembership.user_id == user.user_id,
            WorkspaceMembership.status == "active",
            Workspace.status == "active",
            Workspace.workspace_type == "shared",
        )
        .order_by(Workspace.created_at.asc(), Workspace.workspace_id.asc())
        .first()
    )

    if membership:
        session["active_workspace_id"] = membership.workspace_id
        return membership.workspace

    session.pop("active_workspace_id", None)
    return None


def is_workspace_manager(membership):
    return bool(membership and membership.role in {"owner", "admin"})
