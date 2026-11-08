import os
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Comparison, ComparisonResult, Document, MatchedPassage, Report
from app.services.document_service import (
    calculate_sha256,
    extract_text,
    is_allowed_file,
    make_storage_filename,
)
from app.services.similarity_service import compare_against_repository

bp = Blueprint("documents", __name__)


def _visible_documents_query():
    if current_user.is_admin:
        return Document.query
    return Document.query.filter(
        (Document.user_id == current_user.user_id) | (Document.document_type == "reference")
    )


def _save_uploaded_document(file_storage, title, document_type):
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a document to upload.")

    original_filename = secure_filename(file_storage.filename)
    if not original_filename:
        raise ValueError("The uploaded filename is invalid.")

    if not is_allowed_file(original_filename, current_app.config["ALLOWED_EXTENSIONS"]):
        raise ValueError("Only PDF, DOCX and TXT documents are supported.")

    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError("The selected document is empty.")

    extracted = extract_text(original_filename, file_bytes)
    storage_name = make_storage_filename(original_filename)
    storage_path = os.path.join(current_app.config["UPLOAD_FOLDER"], storage_name)
    with open(storage_path, "wb") as stored_file:
        stored_file.write(file_bytes)

    document = Document(
        user_id=current_user.user_id,
        title=(title or os.path.splitext(original_filename)[0]).strip()[:255],
        original_filename=original_filename[:255],
        storage_path=storage_name,
        file_type=os.path.splitext(original_filename)[1].lower().lstrip("."),
        document_type=document_type,
        extracted_text=extracted,
        file_hash=calculate_sha256(file_bytes),
        processing_status="processed",
    )
    db.session.add(document)
    db.session.commit()
    return document


def _run_comparison(submitted_document):
    comparison = Comparison(
        submitted_document_id=submitted_document.document_id,
        user_id=current_user.user_id,
        status="processing",
    )
    db.session.add(comparison)
    db.session.commit()

    try:
        references = (
            Document.query.filter(
                Document.document_id != submitted_document.document_id,
                Document.document_type == "reference",
                Document.processing_status == "processed",
            )
            .order_by(Document.uploaded_at.desc())
            .limit(current_app.config["MAX_COMPARISON_SOURCES"])
            .all()
        )

        analysis = compare_against_repository(
            submitted_document.extracted_text,
            references,
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
        db.session.add(Report(comparison_id=comparison.comparison_id))
        db.session.commit()
        return comparison

    except Exception:
        db.session.rollback()
        failed = db.session.get(Comparison, comparison.comparison_id)
        if failed:
            failed.status = "failed"
            failed.completed_at = datetime.now(timezone.utc)
            db.session.commit()
        current_app.logger.exception("Similarity comparison failed.")
        raise


@bp.route("/documents")
@login_required
def list_documents():
    documents = _visible_documents_query().order_by(Document.uploaded_at.desc()).all()
    return render_template("documents.html", documents=documents)


@bp.route("/documents/upload", methods=["GET", "POST"])
@login_required
def upload_submission():
    if request.method == "POST":
        try:
            document = _save_uploaded_document(
                request.files.get("document"),
                request.form.get("title", ""),
                "submission",
            )
            comparison = _run_comparison(document)
            if comparison.results:
                flash("Document uploaded and similarity analysis completed.", "success")
            else:
                flash(
                    "Document uploaded. No other processed documents were available for comparison; add reference documents to the repository.",
                    "warning",
                )
            return redirect(url_for("documents.view_comparison", comparison_id=comparison.comparison_id))
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception:
            flash("The document was stored, but similarity analysis could not be completed. Check the application log.", "danger")

    return render_template("upload.html", mode="submission")


@bp.route("/comparisons/<int:comparison_id>")
@login_required
def view_comparison(comparison_id):
    comparison = db.get_or_404(Comparison, comparison_id)
    if not current_user.is_admin and comparison.user_id != current_user.user_id:
        abort(403)

    results = sorted(
        comparison.results,
        key=lambda item: (float(item.cosine_similarity), float(item.matched_ngram_coverage)),
        reverse=True,
    )
    return render_template("report.html", comparison=comparison, results=results)
