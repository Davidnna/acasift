"""Legacy acquisition metadata mappings retained for production-record compatibility.

The 0.16.0 application retires persistent scholarly acquisition and full-text
ingestion. Existing rows are not deleted; new comparisons use transient discovery.
"""

from datetime import datetime, timezone

from sqlalchemy import Index, UniqueConstraint

from app.extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class ScholarlyRecord(db.Model):
    """Canonical scholarly metadata record discovered from one or more APIs."""

    __tablename__ = "scholarly_records"
    __table_args__ = (
        UniqueConstraint("canonical_key", name="uq_scholarly_record_canonical_key"),
        Index("ix_scholarly_records_status_rights", "status", "rights_status"),
        Index("ix_scholarly_records_provider", "primary_provider", "created_at"),
        Index("ix_scholarly_records_doi", "doi"),
    )

    record_id = db.Column(db.Integer, primary_key=True)
    canonical_key = db.Column(db.String(80), nullable=False)
    doi = db.Column(db.String(255), nullable=True)
    title = db.Column(db.String(1000), nullable=False)
    authors_json = db.Column(db.Text, nullable=True)
    abstract_text = db.Column(db.Text, nullable=True)
    publication_year = db.Column(db.Integer, nullable=True)
    journal_title = db.Column(db.String(500), nullable=True)
    primary_provider = db.Column(db.String(40), nullable=False)
    provider_ids_json = db.Column(db.Text, nullable=False, default="[]")
    source_url = db.Column(db.String(1500), nullable=True)
    full_text_url = db.Column(db.String(2000), nullable=True)
    full_text_format = db.Column(db.String(20), nullable=True)
    license_name = db.Column(db.String(160), nullable=True)
    license_url = db.Column(db.String(1000), nullable=True)
    rights_status = db.Column(db.String(30), nullable=False, default="unknown")
    status = db.Column(db.String(30), nullable=False, default="discovered")
    document_id = db.Column(db.Integer, db.ForeignKey("documents.document_id"), nullable=True, index=True)
    download_attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.Text, nullable=True)
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    document = db.relationship("Document", foreign_keys=[document_id])


class AcquisitionSearchState(db.Model):
    """Resumable pagination state for one provider and search expression."""

    __tablename__ = "acquisition_search_states"
    __table_args__ = (
        UniqueConstraint("provider", "query_hash", name="uq_acquisition_search_provider_query"),
    )

    state_id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(40), nullable=False)
    query_hash = db.Column(db.String(64), nullable=False)
    search_query = db.Column("query", db.String(500), nullable=False)
    cursor = db.Column(db.Text, nullable=True)
    offset = db.Column(db.Integer, nullable=False, default=0)
    page = db.Column(db.Integer, nullable=False, default=1)
    total_available = db.Column(db.Integer, nullable=True)
    exhausted = db.Column(db.Boolean, nullable=False, default=False)
    last_run_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class AcquisitionJob(db.Model):
    """A bounded administrator-triggered discovery and ingestion run."""

    __tablename__ = "acquisition_jobs"
    __table_args__ = (
        Index("ix_acquisition_jobs_status_created", "status", "created_at"),
    )

    job_id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(40), nullable=False)
    search_query = db.Column("query", db.String(500), nullable=False)
    requested_limit = db.Column(db.Integer, nullable=False, default=20)
    status = db.Column(db.String(24), nullable=False, default="queued")
    discovered_count = db.Column(db.Integer, nullable=False, default=0)
    new_records_count = db.Column(db.Integer, nullable=False, default=0)
    duplicate_count = db.Column(db.Integer, nullable=False, default=0)
    indexed_count = db.Column(db.Integer, nullable=False, default=0)
    metadata_only_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
    search_state_id = db.Column(db.Integer, db.ForeignKey("acquisition_search_states.state_id"), nullable=True, index=True)
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    finished_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    requested_by = db.relationship("User", foreign_keys=[requested_by_user_id])
    search_state = db.relationship("AcquisitionSearchState", foreign_keys=[search_state_id])
