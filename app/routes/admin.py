from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from app.decorators import admin_required
from app.extensions import db
from app.models import Document, User
from app.routes.documents import _save_uploaded_document

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "user")

        if not full_name or not email or not password:
            flash("All account fields are required.", "danger")
        elif len(password) < 10:
            flash("The password must contain at least 10 characters.", "danger")
        elif role not in {"user", "admin"}:
            flash("The selected account role is invalid.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "danger")
        else:
            user = User(
                full_name=full_name,
                email=email,
                password_hash=generate_password_hash(password),
                role=role,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            flash("User account created successfully.", "success")
            return redirect(url_for("admin.users"))

    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin_users.html", users=all_users)


@bp.route("/references")
@admin_required
def references():
    documents = Document.query.filter_by(document_type="reference").order_by(Document.uploaded_at.desc()).all()
    return render_template("documents.html", documents=documents, admin_reference_view=True)


@bp.route("/references/upload", methods=["GET", "POST"])
@admin_required
def upload_reference():
    if request.method == "POST":
        try:
            document = _save_uploaded_document(
                request.files.get("document"),
                request.form.get("title", ""),
                "reference",
            )
            flash(f"Reference document '{document.title}' added to the repository.", "success")
            return redirect(url_for("admin.references"))
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception:
            current_app.logger.exception("Reference document upload failed.")
            flash("The reference document could not be saved.", "danger")

    return render_template("upload.html", mode="reference")
