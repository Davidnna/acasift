from flask import Blueprint, jsonify, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models import Comparison, Document

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("public_home.html")


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/features")
def features():
    return render_template("features.html")


@bp.route("/how-it-works")
def how_it_works():
    return render_template("how_it_works.html")


@bp.route("/faq")
def faq():
    return render_template("faq.html")


@bp.route("/access")
def access():
    return render_template("access.html")


@bp.route("/dashboard")
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
    return render_template(
        "dashboard.html",
        document_count=document_count,
        comparison_count=comparison_count,
        reference_count=reference_count,
        recent_documents=recent_documents,
        recent_comparisons=recent_comparisons,
    )


@bp.route("/health")
def health():
    return jsonify({"status": "ok"}), 200
