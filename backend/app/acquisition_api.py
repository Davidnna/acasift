"""Administrator endpoints for scholarly reference acquisition."""

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user

from app.decorators import admin_required
from app.services.acquisition_service import (
    PROVIDERS,
    acquisition_dashboard,
    create_and_run_job,
)

bp = Blueprint("acquisition_api", __name__, url_prefix="/api/admin/acquisition")


@bp.get("")
@admin_required
def dashboard():
    return jsonify(acquisition_dashboard())


@bp.get("/providers")
@admin_required
def providers():
    return jsonify({"providers": [{"id": key, **value} for key, value in PROVIDERS.items()]})


@bp.post("/discover")
@admin_required
def discover():
    data = request.get_json(silent=True) or {}
    provider = str(data.get("provider", "")).strip().lower()
    query = str(data.get("query", "")).strip()
    limit = data.get("limit", 10)
    try:
        result = create_and_run_job(provider, query, limit, current_user.user_id)
        return jsonify({"message": "The source search has finished.", "job": result}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        current_app.logger.exception("Could not start scholarly acquisition.")
        return jsonify({"error": "The source search could not be completed. Please try again later."}), 502
