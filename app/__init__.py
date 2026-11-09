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

    from app.models import User, Workspace, WorkspaceMembership, Document, Comparison

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
            if inspector.has_table("users"):
                user_columns = {column["name"]: column for column in inspector.get_columns("users")}
                with db.engine.begin() as connection:
                    for column_name in ("first_name", "last_name", "other_names"):
                        if column_name not in user_columns:
                            connection.execute(text(
                                f"ALTER TABLE users ADD COLUMN {column_name} VARCHAR(80)"
                            ))
                    # PostgreSQL enforces VARCHAR lengths; widen the cached display name
                    # for structured first/other/last names. SQLite does not require this.
                    if db.engine.dialect.name == "postgresql":
                        full_name_column = user_columns.get("full_name", {})
                        if full_name_column.get("type") and getattr(full_name_column["type"], "length", None) and full_name_column["type"].length < 255:
                            connection.execute(text(
                                "ALTER TABLE users ALTER COLUMN full_name TYPE VARCHAR(255)"
                            ))
            inspector = inspect(db.engine)
            if inspector.has_table("documents"):
                document_columns = {column["name"] for column in inspector.get_columns("documents")}
                with db.engine.begin() as connection:
                    if "workspace_id" not in document_columns:
                        connection.execute(text("ALTER TABLE documents ADD COLUMN workspace_id INTEGER"))
                    if "visibility_scope" not in document_columns:
                        connection.execute(text("ALTER TABLE documents ADD COLUMN visibility_scope VARCHAR(20) NOT NULL DEFAULT 'private'"))
            inspector = inspect(db.engine)
            if inspector.has_table("comparisons"):
                comparison_columns = {column["name"] for column in inspector.get_columns("comparisons")}
                if "workspace_id" not in comparison_columns:
                    with db.engine.begin() as connection:
                        connection.execute(text("ALTER TABLE comparisons ADD COLUMN workspace_id INTEGER"))

            # Add referential constraints on existing PostgreSQL installations. SQLite
            # cannot add a foreign key to an existing table without rebuilding it.
            if db.engine.dialect.name == "postgresql":
                for table_name, constraint_name in (
                    ("documents", "fk_documents_workspace_id_workspaces"),
                    ("comparisons", "fk_comparisons_workspace_id_workspaces"),
                ):
                    foreign_keys = inspect(db.engine).get_foreign_keys(table_name)
                    if not any("workspace_id" in item.get("constrained_columns", []) for item in foreign_keys):
                        with db.engine.begin() as connection:
                            connection.execute(text(
                                f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint_name} "
                                "FOREIGN KEY (workspace_id) REFERENCES workspaces (workspace_id)"
                            ))

            # Create one private personal workspace for each existing account.
            # Existing submissions and comparisons are migrated into it. Existing
            # administrator-curated references remain available as platform sources.
            for existing_user in User.query.all():
                membership = (
                    WorkspaceMembership.query.join(Workspace)
                    .filter(
                        WorkspaceMembership.user_id == existing_user.user_id,
                        Workspace.workspace_type == "personal",
                    ).first()
                )
                if membership:
                    personal = membership.workspace
                else:
                    personal = Workspace(
                        name=f"{existing_user.full_name}'s workspace"[:180],
                        workspace_type="personal",
                        status="active",
                        owner_user_id=existing_user.user_id,
                    )
                    db.session.add(personal)
                    db.session.flush()
                    db.session.add(WorkspaceMembership(
                        workspace_id=personal.workspace_id,
                        user_id=existing_user.user_id,
                        role="owner",
                        status="active",
                    ))
                Document.query.filter_by(
                    user_id=existing_user.user_id,
                    document_type="submission",
                    workspace_id=None,
                ).update(
                    {"workspace_id": personal.workspace_id, "visibility_scope": "private"},
                    synchronize_session=False,
                )
                Comparison.query.filter_by(
                    user_id=existing_user.user_id,
                    workspace_id=None,
                ).update({"workspace_id": personal.workspace_id}, synchronize_session=False)

            Document.query.filter_by(document_type="reference", workspace_id=None).update(
                {"workspace_id": None, "visibility_scope": "platform"},
                synchronize_session=False,
            )
            db.session.commit()
            with db.engine.begin() as connection:
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_workspace_id ON documents (workspace_id)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_documents_visibility_scope ON documents (visibility_scope)"))
                connection.execute(text("CREATE INDEX IF NOT EXISTS ix_comparisons_workspace_id ON comparisons (workspace_id)"))

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
            )
            db.session.add(user)
            db.session.flush()
            from app.services.workspace_service import ensure_personal_workspace
            ensure_personal_workspace(user)
            db.session.commit()
        click.echo(f"Administrator account created for {email}.")

    @app.errorhandler(413)
    def file_too_large(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "The uploaded file exceeds the configured size limit."}), 413
        return jsonify({"error": "The uploaded file exceeds the configured size limit."}), 413

    return app
