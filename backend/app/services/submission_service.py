"""Similarity analysis for generic submission requests."""

from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models import (
    Comparison,
    ComparisonResult,
    MatchedPassage,
    Report,
)
from app.services.similarity_service import compare_against_repository
from app.services.reference_service import resolve_reference_sources
from app.submission_models import DocumentSubmission


def _eligible_sources(submission):
    """Resolve only eligible peer submissions from this request."""
    return resolve_reference_sources(
        workspace_id=submission.request.workspace_id,
        request_id=submission.request_id,
        exclude_document_id=submission.document_id,
        exclude_contributor_user_id=submission.contributor_user_id,
    )


def run_submission_request_comparison(submission):
    """Compare a request submission only with other submissions in that request."""
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
        eligible_sources = _eligible_sources(submission)
        sources = [document for document, _scope in eligible_sources]
        scope_by_document_id = {
            document.document_id: scope for document, scope in eligible_sources
        }
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
                source_scope=scope_by_document_id.get(reference.document_id),
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
