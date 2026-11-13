"""Similarity analysis for generic submission requests."""

from datetime import datetime, timezone
import json

from flask import current_app
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    Comparison,
    ComparisonResult,
    MatchedPassage,
    Report,
    Document,
    ExternalComparisonResult,
    ExternalMatchedPassage,
)
from app.services.similarity_service import compare_against_repository
from app.services.external_similarity_service import compare_with_live_scholarly_sources
from app.submission_models import DocumentSubmission


def _eligible_sources(submission):
    """Resolve every eligible peer submission in this same shared Submission Request."""
    request_record = submission.request
    if (
        not request_record
        or not request_record.workspace
        or request_record.workspace.status != "active"
        or request_record.workspace.workspace_type != "shared"
    ):
        return []

    query = (
        DocumentSubmission.query.options(joinedload(DocumentSubmission.document))
        .join(Document, Document.document_id == DocumentSubmission.document_id)
        .filter(
            DocumentSubmission.request_id == submission.request_id,
            DocumentSubmission.status.in_(("submitted", "analysed", "analysis_failed")),
            Document.processing_status == "processed",
            Document.document_type == "submission",
            Document.workspace_id == request_record.workspace_id,
            Document.document_id != submission.document_id,
            DocumentSubmission.contributor_user_id != submission.contributor_user_id,
        )
    )
    records = query.order_by(
        DocumentSubmission.submitted_at.desc(),
        DocumentSubmission.submission_id.desc(),
    ).all()

    result = []
    seen_hashes = set()
    for peer in records:
        document = peer.document
        if not document:
            continue
        fingerprint = document.file_hash or f"document:{document.document_id}"
        if fingerprint in seen_hashes:
            continue
        seen_hashes.add(fingerprint)
        result.append((document, "request"))
    return result


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
                fuzzy_similarity=item["fuzzy_similarity"],
                fuzzy_coverage=item["fuzzy_coverage"],
                semantic_similarity=item["semantic_similarity"],
                semantic_coverage=item["semantic_coverage"],
                composite_similarity=item["composite_similarity"],
                semantic_status=item["semantic_status"],
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
                    match_method=passage.get("match_method", "exact_ngram"),
                    match_score=passage.get("match_score", 100),
                ))

        # Live external scholarly discovery is independent of the peer-source
        # comparison. Provider failures are recorded without discarding successful
        # internal peer analysis.
        comparison.external_search_status = "running"
        db.session.commit()
        try:
            external_analysis = compare_with_live_scholarly_sources(
                submission.document.extracted_text,
                ngram_size=current_app.config["NGRAM_SIZE"],
                document_title=submission.document.title,
            )
            comparison.external_search_status = external_analysis["status"]
            comparison.external_sources_discovered = external_analysis["sources_discovered"]
            comparison.external_sources_compared = external_analysis["sources_compared"]
            comparison.external_sources_with_matches = external_analysis["sources_with_matches"]
            comparison.external_provider_summary = json.dumps(
                external_analysis["providers"],
                ensure_ascii=False,
            )[:12000]
            comparison.external_search_completed_at = datetime.now(timezone.utc)

            for item in external_analysis["evidence"]:
                external_result = ExternalComparisonResult(
                    comparison_id=comparison.comparison_id,
                    provider=item["provider"],
                    providers_json=json.dumps(item.get("providers") or [], ensure_ascii=False),
                    provider_id=item.get("provider_id"),
                    title=item["title"][:1000],
                    authors_json=json.dumps(item.get("authors") or [], ensure_ascii=False),
                    publication_year=item.get("year"),
                    journal_title=(item.get("journal") or "")[:500] or None,
                    doi=item.get("doi"),
                    source_url=(item.get("source_url") or "")[:2000] or None,
                    full_text_url=(item.get("full_text_url") or "")[:2000] or None,
                    license_name=item.get("license_name"),
                    license_url=item.get("license_url"),
                    cosine_similarity=item["cosine_similarity"],
                    exact_ngram_coverage=item["exact_ngram_coverage"],
                    matched_ngram_count=item["matched_ngram_count"],
                    total_query_ngrams=item["total_query_ngrams"],
                    fuzzy_similarity=item["fuzzy_similarity"],
                    fuzzy_coverage=item["fuzzy_coverage"],
                    semantic_similarity=item["semantic_similarity"],
                    semantic_coverage=item["semantic_coverage"],
                    semantic_status=item["semantic_status"],
                    composite_similarity=item["composite_similarity"],
                )
                db.session.add(external_result)
                db.session.flush()

                for passage in item["passages"]:
                    db.session.add(ExternalMatchedPassage(
                        external_result_id=external_result.external_result_id,
                        submitted_start=passage["submitted_start"],
                        submitted_end=passage["submitted_end"],
                        matched_text=passage["matched_text"][:350],
                        source_excerpt=passage["source_excerpt"][:350],
                        match_method=passage["match_method"],
                        match_score=passage["match_score"],
                    ))
        except Exception as external_error:
            db.session.rollback()
            comparison = db.session.get(Comparison, comparison.comparison_id)
            if comparison:
                comparison.external_search_status = "failed"
                comparison.external_search_error = (
                    f"External scholarly discovery could not complete ({type(external_error).__name__})."
                )
                comparison.external_search_completed_at = datetime.now(timezone.utc)
            current_app.logger.exception(
                "External scholarly comparison failed for comparison %s.",
                comparison.comparison_id if comparison else "unknown",
            )

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
