import os

import click
from sqlalchemy import inspect, text
from flask import Flask, jsonify, redirect, request, url_for
from werkzeug.security import generate_password_hash

from config import Config
from app.extensions import csrf, db, login_manager
from flask_wtf.csrf import CSRFError


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "main.spa"
    login_manager.login_message_category = "warning"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.api import bp as api_bp
    from app.routes.main import bp as main_bp

    app.register_blueprint(api_bp)
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
        """Create database tables."""
        with app.app_context():
            db.create_all()
            inspector = inspect(db.engine)
            if inspector.has_table("comparison_results"):
                columns = {column["name"] for column in inspector.get_columns("comparison_results")}
                if "coverage_method" not in columns:
                    # Existing rows receive the legacy label so their stored unique-N-gram
                    # metrics are not misrepresented as the 0.4.0 occurrence-based metric.
                    with db.engine.begin() as connection:
                        connection.execute(text(
                            "ALTER TABLE comparison_results "
                            "ADD COLUMN coverage_method VARCHAR(20) NOT NULL DEFAULT 'unique_ngrams'"
                        ))
        click.echo("Database tables created and additive migrations checked.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt="Administrator name")
    @click.option("--email", prompt="Administrator email")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(name, email, password):
        """Create an administrator account."""
        email = email.strip().lower()
        if len(password) < 10:
            raise click.ClickException("Use a password containing at least 10 characters.")
        with app.app_context():
            existing = User.query.filter_by(email=email).first()
            if existing:
                raise click.ClickException("An account with that email already exists.")
            user = User(
                full_name=name.strip(),
                email=email,
                password_hash=generate_password_hash(password),
                role="admin",
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
        click.echo(f"Administrator account created for {email}.")

    @app.errorhandler(413)
    def file_too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "The uploaded file exceeds the configured size limit."}), 413
        return jsonify({"error": "The uploaded file exceeds the configured size limit."}), 413

    return app
