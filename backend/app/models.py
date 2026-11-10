from datetime import datetime, timezone
from sqlalchemy import UniqueConstraint, Index
from sqlalchemy.orm import deferred

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
    email_verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    email_verification_token_hash = db.Column(db.String(64), nullable=True, unique=True)
    email_verification_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    pending_email = db.Column(db.String(150), nullable=True)
    email_change_token_hash = db.Column(db.String(64), nullable=True)
    email_change_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    profile_image_data = deferred(db.Column(db.LargeBinary, nullable=True))
    profile_image_mime = db.Column(db.String(50), nullable=True)
    profile_image_updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    password_reset_token_hash = db.Column(db.String(64), nullable=True, unique=True)
    password_reset_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    auth_version = db.Column(db.Integer, nullable=False, default=0)

    documents = db.relationship("Document", back_populates="uploader", lazy=True)
    comparisons = db.relationship("Comparison", back_populates="user", lazy=True)

    def get_id(self):
        # Versioned session identifiers allow password-reset flows to revoke
        # previously issued sessions without a separate session store.
        return f"{self.user_id}:{self.auth_version or 0}"

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
    description = db.Column(db.Text, nullable=True)
    # personal workspaces are private; shared workspaces support open collaboration.
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


class WorkspaceInvite(db.Model):
    __tablename__ = "workspace_invites"
    __table_args__ = (
        Index("ix_workspace_invites_workspace_status", "workspace_id", "revoked_at", "expires_at"),
    )

    invite_id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.course_id"), nullable=True, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    role = db.Column(db.String(24), nullable=False, default="member")
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    max_uses = db.Column(db.Integer, nullable=True)
    use_count = db.Column(db.Integer, nullable=False, default=0)
    revoked_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    workspace = db.relationship("Workspace", backref=db.backref("invites", lazy=True))
    course = db.relationship("Course", backref=db.backref("workspace_invites", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by_user_id])



class AuthRateLimitEvent(db.Model):
    __tablename__ = "auth_rate_limit_events"
    __table_args__ = (
        Index("ix_auth_rate_action_key_created", "action", "key_hash", "created_at"),
    )

    event_id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(40), nullable=False, index=True)
    key_hash = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)


class Course(db.Model):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint("workspace_id", "code", name="uq_course_workspace_code"),
        Index("ix_courses_workspace_status", "workspace_id", "status"),
    )

    course_id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspaces.workspace_id"), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    join_code_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    workspace = db.relationship("Workspace", backref=db.backref("courses", lazy=True))
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    memberships = db.relationship("CourseMembership", back_populates="course", cascade="all, delete-orphan", lazy=True)
    assignments = db.relationship("Assignment", back_populates="course", cascade="all, delete-orphan", lazy=True)


class CourseMembership(db.Model):
    __tablename__ = "course_memberships"
    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_membership_user"),
        Index("ix_course_memberships_user_status", "user_id", "status"),
    )

    membership_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.course_id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    # lecturer or student. Workspace owner/admin permissions are inherited separately.
    role = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    added_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    enrolled_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    course = db.relationship("Course", back_populates="memberships")
    user = db.relationship("User", foreign_keys=[user_id])
    added_by = db.relationship("User", foreign_keys=[added_by_user_id])


class Assignment(db.Model):
    __tablename__ = "assignments"
    __table_args__ = (Index("ix_assignments_course_status_due", "course_id", "status", "due_at"),)

    assignment_id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.course_id"), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, nullable=True)
    instructions = db.Column(db.Text, nullable=True)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    allow_late_submissions = db.Column(db.Boolean, nullable=False, default=False)
    allow_resubmissions = db.Column(db.Boolean, nullable=False, default=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    course = db.relationship("Course", back_populates="assignments")
    creator = db.relationship("User", foreign_keys=[created_by_user_id])
    submissions = db.relationship("AcademicSubmission", back_populates="assignment", cascade="all, delete-orphan", lazy=True)


class AcademicSubmission(db.Model):
    __tablename__ = "academic_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_user_id", "attempt_number", name="uq_assignment_student_attempt"),
        Index("ix_academic_submissions_assignment_status", "assignment_id", "status"),
        Index("ix_academic_submissions_student_submitted", "student_user_id", "submitted_at"),
    )

    submission_id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.assignment_id"), nullable=False, index=True)
    student_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.document_id"), nullable=False, unique=True, index=True)
    comparison_id = db.Column(db.Integer, db.ForeignKey("comparisons.comparison_id"), nullable=True, unique=True, index=True)
    attempt_number = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(24), nullable=False, default="submitted", index=True)
    is_late = db.Column(db.Boolean, nullable=False, default=False)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    assignment = db.relationship("Assignment", back_populates="submissions")
    student = db.relationship("User", foreign_keys=[student_user_id])
    document = db.relationship("Document", foreign_keys=[document_id])
    comparison = db.relationship("Comparison", foreign_keys=[comparison_id])
    assessment = db.relationship("AssignmentAssessment", back_populates="submission", uselist=False, cascade="all, delete-orphan")


class AssignmentAssessment(db.Model):
    __tablename__ = "assignment_assessments"

    assessment_id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("academic_submissions.submission_id"), nullable=False, unique=True, index=True)
    assessor_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    # no_concern, discuss_with_student, further_review
    decision = db.Column(db.String(32), nullable=False)
    feedback = db.Column(db.Text, nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    submission = db.relationship("AcademicSubmission", back_populates="assessment")
    assessor = db.relationship("User", foreign_keys=[assessor_user_id])
