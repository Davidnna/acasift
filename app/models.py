from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint

from flask_login import UserMixin
from werkzeug.security import check_password_hash

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    # full_name remains as a denormalised display-name field for existing document
    # records and older clients. Structured name fields are authoritative going forward.
    full_name = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)
    other_names = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="user")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    documents = db.relationship("Document", back_populates="uploader", lazy=True)
    comparisons = db.relationship("Comparison", back_populates="user", lazy=True)

    def get_id(self):
        return str(self.user_id)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == "admin"


class Document(db.Model):
    __tablename__ = "documents"

    document_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    storage_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    document_type = db.Column(db.String(30), nullable=False, index=True)
    extracted_text = db.Column(db.Text, nullable=False)
    file_hash = db.Column(db.String(64), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=True, index=True)
    # private: uploader only; workspace: authorised workspace members; platform: curated shared source.
    visibility_scope = db.Column(db.String(20), nullable=False, default="private", index=True)
    processing_status = db.Column(db.String(30), nullable=False, default="processed")
    uploaded_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    uploader = db.relationship("User", back_populates="documents")
    submitted_comparisons = db.relationship(
        "Comparison",
        foreign_keys="Comparison.submitted_document_id",
        back_populates="submitted_document",
        lazy=True,
    )
    source_results = db.relationship(
        "ComparisonResult",
        foreign_keys="ComparisonResult.reference_document_id",
        back_populates="reference_document",
        lazy=True,
    )


class Comparison(db.Model):
    __tablename__ = "comparisons"

    comparison_id = db.Column(db.Integer, primary_key=True)
    submitted_document_id = db.Column(
        db.Integer, db.ForeignKey("documents.document_id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=True, index=True)
    status = db.Column(db.String(30), nullable=False, default="processing")
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = db.Column(db.DateTime(timezone=True))

    user = db.relationship("User", back_populates="comparisons")
    submitted_document = db.relationship(
        "Document", foreign_keys=[submitted_document_id], back_populates="submitted_comparisons"
    )
    results = db.relationship(
        "ComparisonResult", back_populates="comparison", cascade="all, delete-orphan", lazy=True
    )
    report = db.relationship(
        "Report", back_populates="comparison", uselist=False, cascade="all, delete-orphan"
    )


class ComparisonResult(db.Model):
    __tablename__ = "comparison_results"

    result_id = db.Column(db.Integer, primary_key=True)
    comparison_id = db.Column(db.Integer, db.ForeignKey("comparisons.comparison_id"), nullable=False, index=True)
    reference_document_id = db.Column(db.Integer, db.ForeignKey("documents.document_id"), nullable=False, index=True)
    cosine_similarity = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    matched_ngram_coverage = db.Column(db.Numeric(7, 4), nullable=False, default=0)
    matched_ngram_count = db.Column(db.Integer, nullable=False, default=0)
    total_query_ngrams = db.Column(db.Integer, nullable=False, default=0)
    coverage_method = db.Column(db.String(20), nullable=False, default="ngram_windows")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    comparison = db.relationship("Comparison", back_populates="results")
    reference_document = db.relationship(
        "Document", foreign_keys=[reference_document_id], back_populates="source_results"
    )
    passages = db.relationship(
        "MatchedPassage", back_populates="result", cascade="all, delete-orphan", lazy=True
    )


class MatchedPassage(db.Model):
    __tablename__ = "matched_passages"

    passage_id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.Integer, db.ForeignKey("comparison_results.result_id"), nullable=False, index=True)
    submitted_start = db.Column(db.Integer, nullable=False)
    submitted_end = db.Column(db.Integer, nullable=False)
    reference_start = db.Column(db.Integer, nullable=False)
    reference_end = db.Column(db.Integer, nullable=False)
    matched_text = db.Column(db.Text, nullable=False)

    result = db.relationship("ComparisonResult", back_populates="passages")


class Report(db.Model):
    __tablename__ = "reports"

    report_id = db.Column(db.Integer, primary_key=True)
    comparison_id = db.Column(
        db.Integer, db.ForeignKey("comparisons.comparison_id"), nullable=False, unique=True
    )
    report_path = db.Column(db.String(500))
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    comparison = db.relationship("Comparison", back_populates="report")


class Workspace(db.Model):
    __tablename__ = "workspaces"

    workspace_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False)
    workspace_type = db.Column(db.String(24), nullable=False, default="personal", index=True)
    status = db.Column(db.String(24), nullable=False, default="active", index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    memberships = db.relationship("WorkspaceMembership", back_populates="workspace", cascade="all, delete-orphan", lazy=True)
    documents = db.relationship("Document", backref="workspace", lazy=True)
    comparisons = db.relationship("Comparison", backref="workspace", lazy=True)


class WorkspaceMembership(db.Model):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership_user"),)

    membership_id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    # owner, admin, lecturer, student, member
    role = db.Column(db.String(24), nullable=False, default="member")
    status = db.Column(db.String(24), nullable=False, default="active")
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    workspace = db.relationship("Workspace", back_populates="memberships")
    user = db.relationship("User", backref=db.backref("workspace_memberships", lazy=True))


class WorkspaceRequest(db.Model):
    __tablename__ = "workspace_requests"

    request_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    organization_name = db.Column(db.String(180), nullable=False)
    organization_type = db.Column(db.String(40), nullable=False)
    website = db.Column(db.String(255), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(24), nullable=False, default="pending", index=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    review_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    requester = db.relationship("User", foreign_keys=[user_id])
    reviewer = db.relationship("User", foreign_keys=[reviewed_by_user_id])
