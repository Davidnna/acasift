import hmac
import re

from flask import Blueprint, current_app, jsonify, request

from flask_login import current_user, login_user, login_required, logout_user
from flask_wtf.csrf import generate_csrf
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import select, func, text

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
        "first_name": user.first_name,
        "last_name": user.last_name,
        "other_names": user.other_names,
        "email": user.email,
        "role": user.role,
        "is_admin": user.is_admin,
        "is_active": user.is_active,
        "created_at": _date(user.created_at),
    }


def _validated_name_parts(data):
    first_name = str(data.get("first_name", "")).strip()
    last_name = str(data.get("last_name", "")).strip()
    other_names = str(data.get("other_names", "")).strip()
    if not first_name or not last_name:
        return None, _error("First name and last name are required.")
    if len(first_name) > 80 or len(last_name) > 80 or len(other_names) > 80:
        return None, _error("Each name field must contain no more than 80 characters.")
    display_name = " ".join(part for part in (first_name, other_names, last_name) if part)
    if len(display_name) > 255:
        return None, _error("The combined name is too long.")
    return {
        "first_name": first_name,
        "last_name": last_name,
        "other_names": other_names or None,
        "full_name": display_name,
    }, None


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
                "coverage_method": result.coverage_method,
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


@bp.get("/account")
@login_required
def account_overview():
    documents = Document.query.filter_by(user_id=current_user.user_id).order_by(
        Document.uploaded_at.desc()
    ).limit(5).all()
    comparisons = Comparison.query.filter_by(user_id=current_user.user_id).order_by(
        Comparison.started_at.desc()
    ).limit(5).all()
    return jsonify({
        "user": _user_payload(current_user),
        "activity": {
            "document_count": Document.query.filter_by(user_id=current_user.user_id).count(),
            "comparison_count": Comparison.query.filter_by(user_id=current_user.user_id).count(),
            "recent_documents": [_document_payload(item) for item in documents],
            "recent_comparisons": [_comparison_payload(item) for item in comparisons],
        },
    })


@bp.post("/account/profile")
@login_required
def update_account_profile():
    data = request.get_json(silent=True) or {}
    name_parts, error = _validated_name_parts(data)
    if error:
        return error
    current_user.first_name = name_parts["first_name"]
    current_user.last_name = name_parts["last_name"]
    current_user.other_names = name_parts["other_names"]
    current_user.full_name = name_parts["full_name"]
    db.session.commit()
    return jsonify({"message": "Personal information updated successfully.", "user": _user_payload(current_user)})


@bp.post("/account/password")
@login_required
def change_account_password():
    data = request.get_json(silent=True) or {}
    current_password = str(data.get("current_password", ""))
    new_password = str(data.get("new_password", ""))
    confirm_password = str(data.get("confirm_password", ""))
    if not current_password or not check_password_hash(current_user.password_hash, current_password):
        return _error("Your current password is incorrect.", 400)
    if len(new_password) < 10 or len(new_password) > 256:
        return _error("Your new password must contain between 10 and 256 characters.")
    if new_password != confirm_password:
        return _error("The new password and confirmation do not match.")
    if check_password_hash(current_user.password_hash, new_password):
        return _error("Choose a password different from your current password.")
    current_user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    return jsonify({"message": "Your password has been changed successfully."})


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
    name_parts, name_error = _validated_name_parts(data)
    if name_error:
        return name_error
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    role = str(data.get("role", "user"))

    if not email or not password:
        return _error("Email address and password are required.")
    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return _error("Enter a valid email address.")
    if len(password) < 10 or len(password) > 256:
        return _error("The password must contain between 10 and 256 characters.")
    if role not in {"user", "admin"}:
        return _error("The selected account role is invalid.")
    if User.query.filter_by(email=email).first():
        return _error("An account with that email already exists.", 409)

    user = User(
        **name_parts,
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


@bp.get("/bootstrap/status")
def bootstrap_status():
    """Expose only whether one-time first-admin setup can currently be used."""
    token = str(current_app.config.get("ADMIN_BOOTSTRAP_TOKEN") or "")
    token_is_configured = len(token) >= 32
    admin_exists = db.session.execute(
        select(User.user_id).where(User.role == "admin").limit(1)
    ).first() is not None

    response = jsonify({"available": token_is_configured and not admin_exists})
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@bp.post("/bootstrap/first-admin")
def bootstrap_first_admin():
    """Create exactly one initial administrator when a high-entropy token is configured."""
    configured_token = str(current_app.config.get("ADMIN_BOOTSTRAP_TOKEN") or "")
    if len(configured_token) < 32:
        return _error("Initial administrator setup is disabled. Configure a strong setup token first.", 410)

    data = request.get_json(silent=True) or {}
    supplied_token = str(data.get("setup_token", ""))
    if len(supplied_token) > 512 or not hmac.compare_digest(supplied_token.encode('utf-8'), configured_token.encode('utf-8')):
        return _error("The setup token is invalid.", 403)

    name_parts, name_error = _validated_name_parts(data)
    if name_error:
        return name_error
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if len(email) > 150 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return _error("Enter a valid email address.")
    if len(password) < 10 or len(password) > 256:
        return _error("Your password must contain between 10 and 256 characters.")

    created_user = None
    outcome = None

    try:
        # PostgreSQL advisory transaction lock serialises simultaneous bootstrap
        # attempts across Render workers. The administrator count is checked only
        # after acquiring the lock, so two requests cannot both create an admin.
        with db.session.begin():
            if db.engine.dialect.name == "postgresql":
                db.session.execute(text("SELECT pg_advisory_xact_lock(731245908113)"))

            existing_admin = db.session.execute(
                select(User.user_id).where(User.role == "admin").limit(1)
            ).first()

            if existing_admin:
                outcome = "completed"
            else:
                existing_email = db.session.execute(
                    select(User.user_id).where(func.lower(User.email) == email).limit(1)
                ).first()

                if existing_email:
                    outcome = "email_exists"
                else:
                    created_user = User(
                        **name_parts,
                        email=email,
                        password_hash=generate_password_hash(password),
                        role="admin",
                        is_active=True,
                    )
                    db.session.add(created_user)
                    db.session.flush()

    except Exception:
        db.session.rollback()
        current_app.logger.exception("First administrator bootstrap failed.")
        return _error("The administrator account could not be created. Please try again.", 500)

    if outcome == "completed":
        return _error("Initial administrator setup has already been completed.", 409)
    if outcome == "email_exists":
        return _error("An account with that email already exists. Use a different email address.", 409)

    # Sign in only after the database transaction commits successfully.
    login_user(created_user, remember=False, fresh=True)
    response = jsonify({
        "message": "Your AcaSift administrator account has been created.",
        "user": _user_payload(created_user),
    })
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response, 201
