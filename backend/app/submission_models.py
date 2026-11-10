"""Generic document submission models used by collaborative workspaces."""

from datetime import datetime, timezone
from sqlalchemy import Index, UniqueConstraint
from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class SubmissionRequest(db.Model):
    __tablename__ = "submission_requests"
    __table_args__ = (Index("ix_submission_requests_workspace_status", "workspace_id", "status"),)

    request_id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    opens_at = db.Column(db.DateTime(timezone=True), nullable=True)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    allow_late_submissions = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(24), nullable=False, default="draft", index=True)
    accepted_file_types = db.Column(db.JSON, nullable=False, default=list)
    max_file_size_mb = db.Column(db.Integer, nullable=False, default=15)
    allow_resubmissions = db.Column(db.Boolean, nullable=False, default=False)
    allow_external_participants = db.Column(db.Boolean, nullable=False, default=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    # Legacy source identifier keeps migration idempotent and preserves historical traceability.
    legacy_assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.assignment_id"), nullable=True, unique=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    workspace = db.relationship("Workspace", backref=db.backref("submission_requests", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    participants = db.relationship("SubmissionRequestParticipant", back_populates="request", lazy=True)
    reviewers = db.relationship("SubmissionRequestReviewer", back_populates="request", lazy=True)
    submissions = db.relationship("DocumentSubmission", back_populates="request", lazy=True)


class SubmissionRequestParticipant(db.Model):
    __tablename__ = "submission_request_participants"
    __table_args__ = (
        UniqueConstraint("request_id", "user_id", name="uq_request_participant_user"),
        Index("ix_request_participants_user_status", "user_id", "status"),
    )

    participant_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("submission_requests.request_id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    participation_type = db.Column(db.String(20), nullable=False, default="member")
    status = db.Column(db.String(20), nullable=False, default="active")
    joined_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    request = db.relationship("SubmissionRequest", back_populates="participants")
    user = db.relationship("User", foreign_keys=[user_id])


class SubmissionRequestReviewer(db.Model):
    __tablename__ = "submission_request_reviewers"
    __table_args__ = (UniqueConstraint("request_id", "user_id", name="uq_request_reviewer_user"),)

    reviewer_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("submission_requests.request_id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    assigned_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    request = db.relationship("SubmissionRequest", back_populates="reviewers")
    user = db.relationship("User", foreign_keys=[user_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_user_id])


class SubmissionRequestInvite(db.Model):
    __tablename__ = "submission_request_invites"
    __table_args__ = (Index("ix_request_invites_request_revoked", "request_id", "revoked_at"),)

    invite_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("submission_requests.request_id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    max_uses = db.Column(db.Integer, nullable=True)
    use_count = db.Column(db.Integer, nullable=False, default=0)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    request = db.relationship("SubmissionRequest", backref=db.backref("invitation_links", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by_user_id])


class DocumentSubmission(db.Model):
    __tablename__ = "document_submissions"
    __table_args__ = (
        UniqueConstraint("request_id", "contributor_user_id", "attempt_number", name="uq_request_contributor_attempt"),
        Index("ix_document_submissions_request_status", "request_id", "status"),
        Index("ix_document_submissions_contributor", "contributor_user_id", "submitted_at"),
    )

    submission_id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("submission_requests.request_id"), nullable=False, index=True)
    contributor_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.document_id"), nullable=False, unique=True, index=True)
    comparison_id = db.Column(db.Integer, db.ForeignKey("comparisons.comparison_id"), nullable=True, unique=True, index=True)
    # Legacy source identifier keeps migration idempotent and preserves historical traceability.
    legacy_submission_id = db.Column(db.Integer, db.ForeignKey("academic_submissions.submission_id"), nullable=True, unique=True)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(24), nullable=False, default="submitted", index=True)
    is_late = db.Column(db.Boolean, nullable=False, default=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    request = db.relationship("SubmissionRequest", back_populates="submissions")
    contributor = db.relationship("User", foreign_keys=[contributor_user_id])
    document = db.relationship("Document", foreign_keys=[document_id])
    comparison = db.relationship("Comparison", foreign_keys=[comparison_id])
    reviews = db.relationship("SubmissionReview", back_populates="submission", lazy=True)


class SubmissionReview(db.Model):
    __tablename__ = "submission_reviews"
    __table_args__ = (Index("ix_submission_reviews_submission", "submission_id", "reviewed_at"),)

    review_id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("document_submissions.submission_id"), nullable=False, index=True)
    reviewer_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    decision = db.Column(db.String(32), nullable=False)
    feedback = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    submission = db.relationship("DocumentSubmission", back_populates="reviews")
    reviewer = db.relationship("User", foreign_keys=[reviewer_user_id])
