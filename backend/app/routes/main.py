from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, send_from_directory

bp = Blueprint("main", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


# Preserve the earlier Flask-rendered application URLs during the React migration.
@bp.get("/dashboard")
def legacy_dashboard():
    return redirect("/app/dashboard", code=302)


@bp.get("/documents")
def legacy_documents():
    return redirect("/app/documents", code=302)


@bp.get("/documents/upload")
def legacy_document_upload():
    return redirect("/app/documents", code=302)


@bp.get("/comparisons/<int:comparison_id>")
def legacy_comparison(comparison_id):
    return redirect(f"/app/comparisons/{comparison_id}", code=302)


@bp.get("/admin/users")
def legacy_admin_users():
    return redirect("/app/admin/users", code=302)


@bp.get("/admin/references")
def legacy_admin_references():
    return redirect("/app/admin/references", code=302)


@bp.get("/admin/references/upload")
def legacy_admin_reference_upload():
    return redirect("/app/admin/references", code=302)


@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def spa(path):
    """Serve the React single-page application for all frontend routes."""
    if path == "api" or path.startswith("api/"):
        return jsonify({"error": "API endpoint not found."}), 404
    spa_directory = Path(current_app.static_folder) / "spa"
    index_file = spa_directory / "index.html"
    if not index_file.exists():
        return jsonify({"error": "Frontend build is missing. Run npm run build in frontend/."}), 503
    return send_from_directory(str(spa_directory), "index.html")
