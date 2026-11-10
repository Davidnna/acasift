"""Reference collection registration, provenance and source resolution."""

from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import Document, Workspace
from app.submission_models import DocumentSubmission
from app.reference_models import ReferenceEntry

ACTIVE_STATUS = "active"
REVIEW_REQUIRED_STATUS = "review_required"
ARCHIVED_STATUS = "archived"
WITHDRAWN_STATUS = "withdrawn"
QUARANTINED_STATUS = "quarantined"

GLOBAL_RIGHTS_BASES = {
    "open_license",
    "public_domain",
    "author_permission",
    "publisher_agreement",
    "owned_content",
    "other_authorization",
}


def reference_scope_key(scope, owner_user_id=None, workspace_id=None, request_id=None):
    if scope == "global":
        return "global"
    if scope == "personal" and owner_user_id:
        return f"personal:{int(owner_user_id)}"
    if scope == "workspace" and workspace_id:
        return f"workspace:{int(workspace_id)}"
    if scope == "request" and request_id:
        return f"request:{int(request_id)}"
    raise ValueError("The reference collection scope is invalid.")


def register_reference_entry(
    document,
    scope,
    created_by_user_id,
    *,
    owner_user_id=None,
    workspace_id=None,
    request_id=None,
    status=ACTIVE_STATUS,
    provenance_type="user_upload",
    source_title=None,
    source_url=None,
    doi=None,
    rights_basis=None,
    license_name=None,
    license_url=None,
    rights_notes=None,
    rights_verified=False,
    verified_by_user_id=None,
    verified_at=None,
):
    """Create or update a document's placement in one reference collection."""
    scope_key = reference_scope_key(
        scope,
        owner_user_id=owner_user_id,
        workspace_id=workspace_id,
        request_id=request_id,
    )
    entry = ReferenceEntry.query.filter_by(
        document_id=document.document_id,
        scope_key=scope_key,
    ).first()
    if entry is None:
        entry = ReferenceEntry(
            document_id=document.document_id,
            scope=scope,
            scope_key=scope_key,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
            request_id=request_id,
            created_by_user_id=created_by_user_id,
        )
        db.session.add(entry)

    entry.scope = scope
    entry.status = status
    entry.provenance_type = provenance_type
    entry.source_title = (source_title or document.title or "").strip()[:255] or None
    entry.source_url = source_url
    entry.doi = doi
    entry.rights_basis = rights_basis
    entry.license_name = license_name
    entry.license_url = license_url
    entry.rights_notes = rights_notes
    entry.rights_verified = bool(rights_verified)
    entry.verified_by_user_id = verified_by_user_id
    entry.verified_at = verified_at
    entry.owner_user_id = owner_user_id
    entry.workspace_id = workspace_id
    entry.request_id = request_id
    return entry


def entry_for_document(document_id, scope_key):
    return ReferenceEntry.query.filter_by(
        document_id=document_id,
        scope_key=scope_key,
    ).first()


def reference_entry_payload(entry):
    document = entry.document
    return {
        "id": entry.entry_id,
        "document_id": entry.document_id,
        "scope": entry.scope,
        "status": entry.status,
        "provenance_type": entry.provenance_type,
        "source_title": entry.source_title,
        "source_url": entry.source_url,
        "doi": entry.doi,
        "rights_basis": entry.rights_basis,
        "license_name": entry.license_name,
        "license_url": entry.license_url,
        "rights_notes": entry.rights_notes,
        "rights_verified": bool(entry.rights_verified),
        "verified_at": entry.verified_at.isoformat() if entry.verified_at else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "document": {
            "id": document.document_id,
            "title": document.title,
            "original_filename": document.original_filename,
            "file_type": document.file_type,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "uploader": document.uploader.full_name if document.uploader else None,
        },
    }


def list_reference_entries(*, scope, owner_user_id=None, workspace_id=None, request_id=None, include_inactive=False):
    query = ReferenceEntry.query.options(
        joinedload(ReferenceEntry.document).joinedload(Document.uploader),
    ).filter(ReferenceEntry.scope == scope)
    if owner_user_id is not None:
        query = query.filter(ReferenceEntry.owner_user_id == owner_user_id)
    if workspace_id is not None:
        query = query.filter(ReferenceEntry.workspace_id == workspace_id)
    if request_id is not None:
        query = query.filter(ReferenceEntry.request_id == request_id)
    if not include_inactive:
        query = query.filter(ReferenceEntry.status.in_((ACTIVE_STATUS, REVIEW_REQUIRED_STATUS)))
    return query.order_by(ReferenceEntry.created_at.desc(), ReferenceEntry.entry_id.desc()).all()


def resolve_reference_sources(
    *,
    user_id,
    workspace_id,
    request_id=None,
    exclude_document_id=None,
    exclude_contributor_user_id=None,
    maximum_per_scope=50,
):
    """Return eligible (Document, scope) pairs in policy priority order.

    Global and shared-workspace references require recorded rights verification.
    Personal references are private to their owner. Request references are
    restricted to submissions belonging to the same request and exclude the
    contributor's own submissions.
    """
    maximum = max(1, int(maximum_per_scope))
    workspace = db.session.get(Workspace, workspace_id) if workspace_id else None
    candidates = []

    global_entries = (
        ReferenceEntry.query.options(joinedload(ReferenceEntry.document))
        .filter(
            ReferenceEntry.scope == "global",
            ReferenceEntry.status == ACTIVE_STATUS,
            ReferenceEntry.rights_verified.is_(True),
        )
        .order_by(ReferenceEntry.created_at.desc())
        .limit(maximum)
        .all()
    )
    candidates.extend((entry.document, "global") for entry in global_entries)

    if workspace and workspace.workspace_type == "personal":
        personal_entries = (
            ReferenceEntry.query.options(joinedload(ReferenceEntry.document))
            .filter(
                ReferenceEntry.scope == "personal",
                ReferenceEntry.owner_user_id == user_id,
                ReferenceEntry.status == ACTIVE_STATUS,
            )
            .order_by(ReferenceEntry.created_at.desc())
            .limit(maximum)
            .all()
        )
        candidates.extend((entry.document, "personal") for entry in personal_entries)
    elif workspace and workspace.workspace_type == "shared":
        workspace_entries = (
            ReferenceEntry.query.options(joinedload(ReferenceEntry.document))
            .filter(
                ReferenceEntry.scope == "workspace",
                ReferenceEntry.workspace_id == workspace_id,
                ReferenceEntry.status == ACTIVE_STATUS,
                ReferenceEntry.rights_verified.is_(True),
            )
            .order_by(ReferenceEntry.created_at.desc())
            .limit(maximum)
            .all()
        )
        candidates.extend((entry.document, "workspace") for entry in workspace_entries)

    if request_id is not None:
        request_query = (
            ReferenceEntry.query.options(joinedload(ReferenceEntry.document))
            .join(DocumentSubmission, DocumentSubmission.document_id == ReferenceEntry.document_id)
            .filter(
                ReferenceEntry.scope == "request",
                ReferenceEntry.request_id == request_id,
                ReferenceEntry.status == ACTIVE_STATUS,
                DocumentSubmission.request_id == request_id,
                DocumentSubmission.status.in_(("submitted", "analysed", "analysis_failed")),
            )
        )
        if exclude_contributor_user_id is not None:
            request_query = request_query.filter(
                DocumentSubmission.contributor_user_id != exclude_contributor_user_id
            )
        request_entries = request_query.order_by(
            DocumentSubmission.submitted_at.desc()
        ).limit(maximum).all()
        candidates.extend((entry.document, "request") for entry in request_entries)

    # Prefer the first eligible scope for duplicate files. This preserves the
    # global > workspace/personal > request ordering while avoiding score inflation.
    result = []
    seen_hashes = set()
    for document, scope in candidates:
        if not document or document.document_id == exclude_document_id:
            continue
        if document.processing_status != "processed":
            continue
        fingerprint = document.file_hash or f"document:{document.document_id}"
        if fingerprint in seen_hashes:
            continue
        seen_hashes.add(fingerprint)
        result.append((document, scope))
    return result


def archive_reference_entry(entry):
    entry.status = ARCHIVED_STATUS
    entry.updated_at = datetime.now(timezone.utc)
    db.session.add(entry)
    return entry
