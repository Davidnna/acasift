import os
import json
from datetime import datetime, timezone

import click
from flask import Flask, jsonify, redirect, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

from config import Config
from app.extensions import csrf, db, login_manager
from flask_wtf.csrf import CSRFError


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    # Render terminates TLS and forwards one trusted proxy hop. ProxyFix restores
    # the client IP and original HTTPS scheme used for secure cookies/rate limits.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "main.spa"
    login_manager.login_message_category = "warning"

    from app.models import (
        AcademicSubmission, Assignment, AssignmentAssessment, Comparison, Course,
        CourseMembership, Document, User, Workspace, WorkspaceInvite, WorkspaceMembership,
    )
    from app.submission_models import (
        DocumentSubmission, SubmissionRequest, SubmissionRequestParticipant,
        SubmissionRequestReviewer, SubmissionReview,
    )
    from app.reference_models import ReferenceEntry
    # Legacy acquisition ORM mappings remain loaded solely to preserve existing
    # production metadata records. The 0.16.0 acquisition API and ingestion job
    # workflow are retired; live discovery is transient and uses no repository.
    from app.acquisition_models import AcquisitionJob, ScholarlyRecord

    @login_manager.user_loader
    def load_user(user_id):
        try:
            if ":" in str(user_id):
                raw_id, raw_version = str(user_id).split(":", 1)
                user = db.session.get(User, int(raw_id))
                if not user or int(raw_version) != int(user.auth_version or 0):
                    return None
                return user
            # Legacy cookies used only the integer user ID. Preserve them for
            # version-zero users; password changes invalidate these old cookies.
            user = db.session.get(User, int(user_id))
            if not user or int(user.auth_version or 0) != 0:
                return None
            return user
        except (TypeError, ValueError):
            return None

    from app.api import bp as api_bp
    from app.api.workspaces import bp as workspaces_api_bp
    from app.submission_api import bp as submission_api_bp
    from app.routes.main import bp as main_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(workspaces_api_bp)
    app.register_blueprint(submission_api_bp)
    app.register_blueprint(main_bp)

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify({"error": "Authentication required."}), 401
        return redirect(url_for("main.spa", path="login"))

    @app.errorhandler(403)
    def forbidden(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "You do not have permission to perform this action."}), 403
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "API endpoint not found."}), 404
        return jsonify({"error": "Not found."}), 404

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Your session token is invalid or expired. Refresh and try again."}), 400
        return jsonify({"error": "The form session has expired."}), 400

    @app.cli.command("init-db")
    def init_db():
        """Create the initial schema and apply pending database migrations."""
        from app.database import initialize_database

        mode = initialize_database(app)
        click.echo(f"Database initialisation complete ({mode}).")


    @app.cli.command("create-admin")
    @click.option("--first-name", prompt="First name")
    @click.option("--last-name", prompt="Last name")
    @click.option("--other-names", prompt="Other names (optional)", default="")
    @click.option("--email", prompt="Administrator email")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(first_name, last_name, other_names, email, password):
        """Create an administrator account."""
        first_name = first_name.strip()
        last_name = last_name.strip()
        other_names = other_names.strip()
        email = email.strip().lower()
        if not first_name or not last_name:
            raise click.ClickException("First name and last name are required.")
        if len(password) < 10:
            raise click.ClickException("Use a password containing at least 10 characters.")
        with app.app_context():
            existing = User.query.filter_by(email=email).first()
            if existing:
                raise click.ClickException("An account with that email already exists.")
            display_name = " ".join(part for part in (first_name, other_names, last_name) if part)
            user = User(
                first_name=first_name,
                last_name=last_name,
                other_names=other_names or None,
                full_name=display_name,
                email=email,
                password_hash=generate_password_hash(password),
                role="admin",
                is_active=True,
                email_verified_at=datetime.now(timezone.utc),
            )
            db.session.add(user)
            db.session.commit()
        click.echo(f"Administrator account created for {email}.")

    @app.after_request
    def secure_auth_response_headers(response):
        if request.path in {"/verify-email", "/reset-password"} or request.path.startswith("/api/auth/"):
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @app.errorhandler(413)
    def file_too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "The uploaded file exceeds the configured size limit."}), 413
        return jsonify({"error": "The uploaded file exceeds the configured size limit."}), 413

    return app
