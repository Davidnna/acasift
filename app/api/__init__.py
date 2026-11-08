from flask import Blueprint, jsonify, request
from flask_login import current_user, login_user, login_required, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import generate_password_hash

from app.decorators import admin_required
from app.extensions import db
from app.models import Comparison, Document, User
from app.services.workflow_service import run_comparison, save_uploaded_document

bp = Blueprint("api", __name__, url_prefix="/api")


def _date(value):
    return value.isoformat() if value else None


def _user_payload(user):
    return {
        "id": user.user_id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "is_admin": user.is_admin,
    }


def _document_payload(document):
    return {
        "id": document.document_id,
        "user_id": document.user_id,
        "uploader": document.uploader.full_name if document.uploader else None,
        "title": document.title,
        "original_filename": document.original_filename,
        "file_type": document.file_type,
        "document_type": document.document_type,
        "processing_status": document.processing_status,
        "uploaded_at": _date(document.uploaded_at),
    }


def _comparison_payload(comparison, include_results=False):
    payload = {
        "id": comparison.comparison_id,
        "status": comparison.status,
        "started_at": _date(comparison.started_at),
        "completed_at": _date(comparison.completed_at),
        "submitted_document": _document_payload(comparison.submitted_document),
    }
    if include_results:
        results = sorted(
            comparison.results,
            key=lambda item: (float(item.cosine_similarity), float(item.matched_ngram_coverage)),
            reverse=True,
        )
        payload["results"] = []
        for result in results:
            reference = result.reference_document
            passages = []
            for passage in result.passages:
                passages.append({
                    "id": passage.passage_id,
                    "submitted_start": passage.submitted_start,
                    "submitted_end": passage.submitted_end,
                    "reference_start": passage.reference_start,
                    "reference_end": passage.reference_end,
                    "matched_text": passage.matched_text,
                    "reference_text": (reference.extracted_text or "")[passage.reference_start:passage.reference_end],
                })
            payload["results"].append({
                "id": result.result_id,
                "reference_document": _document_payload(reference),
                "cosine_similarity": float(result.cosine_similarity),
                "matched_ngram_coverage": float(result.matched_ngram_coverage),
                "matched_ngram_count": result.matched_ngram_count,
                "total_query_ngrams": result.total_query_ngrams,
                "passages": passages,
            })
    return payload


def _error(message, status=400):
    return jsonify({"error": message}), status


@bp.get("/csrf")
def csrf_token():
    return jsonify({"csrf_token": generate_csrf()})


@bp.get("/auth/me")
def me():
    if not current_user.is_authenticated:
        return _error("Authentication required.", 401)
    return jsonify({"user": _user_payload(current_user)})


@bp.post("/auth/login")
def login():
    if current_user.is_authenticated:
        return jsonify({"user": _user_payload(current_user)})

    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    user = User.query.filter_by(email=email).first()

    if not user or not user.is_active or not user.check_password(password):
        return _error("Invalid email address or password, or the account is inactive.", 401)

    login_user(user)
    return jsonify({"user": _user_payload(user)})


@bp.post("/auth/logout")
@login_required
def logout():
    logout_user()
    return jsonify({"message": "You have been signed out."})


@bp.get("/dashboard")
@login_required
def dashboard():
    if current_user.is_admin:
        document_count = Document.query.filter_by(user_id=current_user.user_id).count()
        comparison_count = Comparison.query.count()
        recent_documents = Document.query.order_by(Document.uploaded_at.desc()).limit(6).all()
        recent_comparisons = Comparison.query.order_by(Comparison.started_at.desc()).limit(6).all()
    else:
        document_count = Document.query.filter_by(user_id=current_user.user_id).count()
        comparison_count = Comparison.query.filter_by(user_id=current_user.user_id).count()
        recent_documents = (
            Document.query.filter_by(user_id=current_user.user_id)
            .order_by(Document.uploaded_at.desc()).limit(6).all()
        )
        recent_comparisons = (
            Comparison.query.filter_by(user_id=current_user.user_id)
            .order_by(Comparison.started_at.desc()).limit(6).all()
        )

    reference_count = Document.query.filter_by(
        document_type="reference", processing_status="processed"
    ).count()
    return jsonify({
        "stats": {
            "document_count": document_count,
            "comparison_count": comparison_count,
            "reference_count": reference_count,
        },
        "recent_documents": [_document_payload(item) for item in recent_documents],
        "recent_comparisons": [_comparison_payload(item) for item in recent_comparisons],
    })


@bp.get("/documents")
@login_required
def documents():
    query = Document.query
    if not current_user.is_admin:
        query = query.filter(
            (Document.user_id == current_user.user_id) | (Document.document_type == "reference")
        )
    records = query.order_by(Document.uploaded_at.desc()).all()
    return jsonify({"documents": [_document_payload(item) for item in records]})


@bp.post("/documents")
@login_required
def upload_submission():
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "submission",
        )
        comparison = run_comparison(document)
        return jsonify({
            "message": "Document uploaded and similarity analysis completed.",
            "comparison_id": comparison.comparison_id,
            "comparison": _comparison_payload(comparison),
        }), 201
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception:
        from flask import current_app
        current_app.logger.exception("Submission upload or comparison failed.")
        return _error("The document was stored, but similarity analysis could not be completed. Check the application log.", 500)


@bp.get("/comparisons/<int:comparison_id>")
@login_required
def comparison_detail(comparison_id):
    comparison = db.get_or_404(Comparison, comparison_id)
    if not current_user.is_admin and comparison.user_id != current_user.user_id:
        return _error("You do not have permission to view this report.", 403)
    return jsonify({"comparison": _comparison_payload(comparison, include_results=True)})


@bp.get("/admin/users")
@admin_required
def users():
    records = User.query.order_by(User.created_at.desc()).all()
    return jsonify({"users": [{
        **_user_payload(user),
        "is_active": user.is_active,
        "created_at": _date(user.created_at),
    } for user in records]})


@bp.post("/admin/users")
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    full_name = str(data.get("full_name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "user"))

    if not full_name or not email or not password:
        return _error("Full name, email address and password are required.")
    if "@" not in email or len(email) > 150:
        return _error("Enter a valid email address.")
    if len(password) < 10:
        return _error("The password must contain at least 10 characters.")
    if role not in {"user", "admin"}:
        return _error("The selected account role is invalid.")
    if User.query.filter_by(email=email).first():
        return _error("An account with that email already exists.", 409)

    user = User(
        full_name=full_name[:150],
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        is_active=True,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User account created successfully.", "user": _user_payload(user)}), 201


@bp.get("/admin/references")
@admin_required
def references():
    records = Document.query.filter_by(document_type="reference").order_by(Document.uploaded_at.desc()).all()
    return jsonify({"documents": [_document_payload(item) for item in records]})


@bp.post("/admin/references")
@admin_required
def upload_reference():
    try:
        document = save_uploaded_document(
            request.files.get("document"),
            request.form.get("title", ""),
            "reference",
        )
        return jsonify({
            "message": f"Reference document '{document.title}' added to the repository.",
            "document": _document_payload(document),
        }), 201
    except ValueError as exc:
        return _error(str(exc), 400)
    except Exception:
        from flask import current_app
        current_app.logger.exception("Reference document upload failed.")
        return _error("The reference document could not be saved.", 500)
