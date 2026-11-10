"""Similarity analysis for generic submission requests."""

from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models import (
    Comparison,
    ComparisonResult,
    Document,
    MatchedPassage,
    Report,
)
from app.services.similarity_service import compare_against_repository
from app.submission_models import DocumentSubmission


def _eligible_sources(submission):
    request = submission.request
    submitted_document = submission.document
    maximum_per_scope = max(1, int(current_app.config.get("MAX_COMPARISON_SOURCES", 50)))

    global_sources = Document.query.filter(
        Document.document_type == "reference",
        Document.processing_status == "processed",
        Document.visibility_scope == "platform",
        Document.document_id != submitted_document.document_id,
    ).order_by(Document.uploaded_at.desc()).limit(maximum_per_scope).all()

    workspace_sources = Document.query.filter(
        Document.document_type == "reference",
        Document.processing_status == "processed",
        Document.visibility_scope == "workspace",
        Document.workspace_id == request.workspace_id,
        Document.document_id != submitted_document.document_id,
    ).order_by(Document.uploaded_at.desc()).limit(maximum_per_scope).all()

    request_sources = (
        Document.query.join(
            DocumentSubmission,
            DocumentSubmission.document_id == Document.document_id,
        )
        .filter(
            DocumentSubmission.request_id == request.request_id,
            DocumentSubmission.contributor_user_id != submission.contributor_user_id,
            DocumentSubmission.status.in_(("submitted", "analysed", "analysis_failed")),
            Document.processing_status == "processed",
            Document.document_id != submitted_document.document_id,
        )
        .order_by(DocumentSubmission.submitted_at.desc())
        .limit(maximum_per_scope)
        .all()
    )

    # Keep each approved source scope represented. A large global collection must
    # not consume the entire comparison budget and silently exclude workspace or
    # same-request evidence. The configured cap applies independently per scope.
    sources = []
    seen_hashes = set()
    for documents in (global_sources, workspace_sources, request_sources):
        for document in documents:
            fingerprint = document.file_hash or f"document:{document.document_id}"
            if fingerprint in seen_hashes:
                continue
            seen_hashes.add(fingerprint)
            sources.append(document)

    return sources


def run_submission_request_comparison(submission):
    """Compare a request submission against global, workspace and request sources."""
    comparison = Comparison(
        submitted_document_id=submission.document_id,
        user_id=submission.contributor_user_id,
        workspace_id=submission.request.workspace_id,
        status="processing",
    )
    db.session.add(comparison)
    db.session.flush()
    submission.comparison_id = comparison.comparison_id
    db.session.commit()

    try:
        sources = _eligible_sources(submission)
        analysis = compare_against_repository(
            submission.document.extracted_text,
            sources,
            ngram_size=current_app.config["NGRAM_SIZE"],
        )

        for item in analysis:
            reference = item["reference_document"]
            result = ComparisonResult(
                comparison_id=comparison.comparison_id,
                reference_document_id=reference.document_id,
                cosine_similarity=item["cosine_similarity"],
                matched_ngram_coverage=item["matched_ngram_coverage"],
                matched_ngram_count=item["matched_ngram_count"],
                total_query_ngrams=item["total_query_ngrams"],
                coverage_method="ngram_windows",
            )
            db.session.add(result)
            db.session.flush()

            for passage in item["passages"]:
                db.session.add(MatchedPassage(
                    result_id=result.result_id,
                    submitted_start=passage["submitted_start"],
                    submitted_end=passage["submitted_end"],
                    reference_start=passage["reference_start"],
                    reference_end=passage["reference_end"],
                    matched_text=passage["matched_text"],
                ))

        comparison.status = "completed"
        comparison.completed_at = datetime.now(timezone.utc)
        submission.status = "analysed"
        db.session.add(Report(comparison_id=comparison.comparison_id))
        db.session.commit()
        return comparison

    except Exception:
        db.session.rollback()
        failed = db.session.get(Comparison, comparison.comparison_id)
        current_submission = db.session.get(DocumentSubmission, submission.submission_id)
        if failed:
            failed.status = "failed"
            failed.completed_at = datetime.now(timezone.utc)
        if current_submission:
            current_submission.status = "analysis_failed"
            current_submission.comparison_id = comparison.comparison_id
        db.session.commit()
        current_app.logger.exception(
            "Similarity analysis failed for submission request %s, submission %s.",
            submission.request_id,
            submission.submission_id,
        )
        return db.session.get(Comparison, comparison.comparison_id)
