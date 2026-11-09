from datetime import datetime, timezone

from flask import current_app

from app.extensions import db
from app.models import (
    AcademicSubmission,
    Comparison,
    ComparisonResult,
    MatchedPassage,
    Report,
)
from app.services.similarity_service import compare_against_repository


def utc_now():
    return datetime.now(timezone.utc)


def run_assignment_comparison(submission, peer_documents):
    """Create or refresh one submission's comparison against same-assignment peers."""
    if submission.comparison_id:
        comparison = db.session.get(Comparison, submission.comparison_id)
        if comparison is None:
            submission.comparison_id = None
            comparison = None
    else:
        comparison = None

    if comparison is None:
        comparison = Comparison(
            submitted_document_id=submission.document_id,
            user_id=submission.student_user_id,
            workspace_id=submission.assignment.course.workspace_id,
            status="processing",
        )
        db.session.add(comparison)
        db.session.flush()
        submission.comparison_id = comparison.comparison_id
    else:
        comparison.results.clear()
        comparison.status = "processing"
        comparison.started_at = utc_now()
        comparison.completed_at = None

    analysis = compare_against_repository(
        submission.document.extracted_text,
        peer_documents,
        ngram_size=current_app.config["NGRAM_SIZE"],
    )

    for item in analysis:
        result = ComparisonResult(
            comparison_id=comparison.comparison_id,
            reference_document_id=item["reference_document"].document_id,
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
    comparison.completed_at = utc_now()
    submission.status = "analysed"
    if comparison.report is None:
        db.session.add(Report(comparison_id=comparison.comparison_id))
    else:
        comparison.report.generated_at = utc_now()
    db.session.commit()
    return comparison
