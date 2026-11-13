"""Legacy reference metadata mappings retained for production-record compatibility.

The 0.16.0 application no longer exposes permanent reference-bank uploads or
reference acquisition. Historical rows remain available for audit/migration only.
"""

from datetime import datetime, timezone
from sqlalchemy import Index, UniqueConstraint

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class ReferenceEntry(db.Model):
    """Historical reference placement; not used by new similarity comparisons."""

    __tablename__ = "reference_entries"
    __table_args__ = (
        UniqueConstraint("document_id", "scope_key", name="uq_reference_entry_document_scope"),
        Index("ix_reference_entries_scope_status", "scope", "status"),
        Index("ix_reference_entries_workspace_status", "workspace_id", "status"),
        Index("ix_reference_entries_owner_status", "owner_user_id", "status"),
        Index("ix_reference_entries_request_status", "request_id", "status"),
    )

    entry_id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.document_id"), nullable=False, index=True)
    # New active records use the global scope only. Personal, workspace and
    # request scopes remain in the schema solely for historical traceability.
    scope = db.Column(db.String(20), nullable=False, index=True)
    # Deterministic key permits one canonical document to have several placements.
    scope_key = db.Column(db.String(100), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=True, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey("submission_requests.request_id"), nullable=True, index=True)
    status = db.Column(db.String(24), nullable=False, default="active", index=True)
    provenance_type = db.Column(db.String(32), nullable=False, default="user_upload")
    source_title = db.Column(db.String(255), nullable=True)
    source_url = db.Column(db.String(1000), nullable=True)
    doi = db.Column(db.String(255), nullable=True)
    rights_basis = db.Column(db.String(40), nullable=True)
    license_name = db.Column(db.String(160), nullable=True)
    license_url = db.Column(db.String(1000), nullable=True)
    rights_notes = db.Column(db.Text, nullable=True)
    rights_verified = db.Column(db.Boolean, nullable=False, default=False)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    document = db.relationship("Document", foreign_keys=[document_id])
    owner = db.relationship("User", foreign_keys=[owner_user_id])
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    verifier = db.relationship("User", foreign_keys=[verified_by_user_id])
    workspace = db.relationship("Workspace", foreign_keys=[workspace_id])
    request = db.relationship("SubmissionRequest", foreign_keys=[request_id])


