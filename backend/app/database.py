from time import perf_counter

from sqlalchemy import inspect, text

from app.extensions import db
from app.reference_models import ReferenceEntry
from app.models import (
    Assignment,
    Comparison,
    Document,
    User,
    Workspace,
    WorkspaceInvite,
    WorkspaceMembership,
)
from app.submission_models import (
    DocumentSubmission,
    SubmissionRequest,
    SubmissionRequestParticipant,
    SubmissionRequestReviewer,
    SubmissionReview,
)


MIGRATION_TABLE = "acasift_schema_migrations"
LEGACY_BASELINE_VERSION = "2026-11-10-legacy-workspace-submission-baseline"
REFERENCE_ARCHITECTURE_VERSION = "2026-11-10-unified-reference-architecture-v1"
SIMPLIFIED_REFERENCE_POLICY_VERSION = "2026-11-10-simplified-reference-comparison-v1"
ACQUISITION_ENGINE_VERSION = "2026-11-11-multi-source-acquisition-engine-v1"

REQUIRED_COLUMNS = {
    "users": {
        "user_id", "full_name", "email", "password_hash", "role", "is_active", "created_at",
        "first_name", "last_name", "other_names", "email_verified_at",
        "email_verification_token_hash", "email_verification_expires_at",
        "pending_email", "email_change_token_hash", "email_change_expires_at",
        "profile_image_data", "profile_image_mime", "profile_image_updated_at",
        "password_reset_token_hash", "password_reset_expires_at", "auth_version",
    },
    "workspaces": {"workspace_id", "workspace_type", "owner_user_id", "description"},
    "workspace_memberships": {"workspace_id", "user_id", "role"},
    "documents": {"document_type", "workspace_id", "visibility_scope"},
    "comparisons": {"workspace_id"},
    "workspace_invites": {"workspace_id", "role", "course_id"},
    "assignments": {"assignment_id"},
    "academic_submissions": {"submission_id"},
    "assignment_assessments": {"submission_id", "assessor_user_id"},
    "submission_requests": {"request_id", "legacy_assignment_id", "max_file_size_mb", "allow_late_submissions"},
    "document_submissions": {"submission_id", "legacy_submission_id"},
    "submission_reviews": {"submission_id", "reviewer_user_id"},
    "comparison_results": {"coverage_method"},
}

REQUIRED_TABLES = {
    "users", "workspaces", "workspace_memberships", "workspace_invites",
    "documents", "comparisons", "comparison_results", "assignments",
    "courses", "course_memberships", "academic_submissions",
    "assignment_assessments", "submission_requests",
    "submission_request_participants", "submission_request_reviewers",
    "document_submissions", "submission_reviews",
}


def _ensure_migration_table():
    with db.engine.begin() as connection:
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
                version VARCHAR(120) PRIMARY KEY,
                execution_mode VARCHAR(32) NOT NULL,
                applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))


def _applied_migrations():
    with db.engine.connect() as connection:
        rows = connection.execute(
            text(f"SELECT version FROM {MIGRATION_TABLE}")
        ).scalars().all()
    return set(rows)


def _record_migration(version, execution_mode):
    with db.engine.begin() as connection:
        connection.execute(
            text(
                f"INSERT INTO {MIGRATION_TABLE} (version, execution_mode) "
                "VALUES (:version, :execution_mode) "
                "ON CONFLICT (version) DO NOTHING"
            ),
            {"version": version, "execution_mode": execution_mode},
        )


def _legacy_baseline_status(app):
    """Return whether the existing legacy migration work is already complete.

    This fast-path lets databases already migrated by AcaSift 0.11.3 acquire a
    migration-ledger baseline without repeating full-table ORM loops.
    """
    inspector = inspect(db.engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(REQUIRED_TABLES - existing_tables)
    if missing_tables:
        return False, [f"missing tables: {', '.join(missing_tables)}"]

    missing_columns = []
    for table_name, required in REQUIRED_COLUMNS.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        absent = sorted(required - actual)
        if absent:
            missing_columns.append(f"{table_name}: {', '.join(absent)}")
    if missing_columns:
        return False, [f"missing columns: {'; '.join(missing_columns)}"]

    checks = (
        (
            "users_missing_personal_workspace",
            """SELECT COUNT(*) FROM users u
               WHERE NOT EXISTS (
                   SELECT 1
                   FROM workspace_memberships wm
                   JOIN workspaces w ON w.workspace_id = wm.workspace_id
                   WHERE wm.user_id = u.user_id AND w.workspace_type = 'personal'
               )""",
        ),
        (
            "legacy_assignments_not_converted",
            """SELECT COUNT(*) FROM assignments a
               WHERE NOT EXISTS (
                   SELECT 1 FROM submission_requests sr
                   WHERE sr.legacy_assignment_id = a.assignment_id
               )""",
        ),
        (
            "legacy_submissions_not_converted",
            """SELECT COUNT(*) FROM academic_submissions s
               WHERE NOT EXISTS (
                   SELECT 1 FROM document_submissions ds
                   WHERE ds.legacy_submission_id = s.submission_id
               )""",
        ),
        (
            "legacy_reviews_not_converted",
            """SELECT COUNT(*)
               FROM assignment_assessments aa
               JOIN document_submissions ds
                 ON ds.legacy_submission_id = aa.submission_id
               WHERE NOT EXISTS (
                   SELECT 1 FROM submission_reviews sr
                   WHERE sr.submission_id = ds.submission_id
                     AND sr.reviewer_user_id = aa.assessor_user_id
               )""",
        ),
        (
            "legacy_workspace_roles_not_normalized",
            """SELECT COUNT(*) FROM workspace_memberships
               WHERE role IN ('student', 'lecturer')""",
        ),
        (
            "legacy_invites_not_normalized",
            """SELECT COUNT(*) FROM workspace_invites
               WHERE role <> 'member' OR course_id IS NOT NULL""",
        ),
        (
            "legacy_workspace_types_not_normalized",
            """SELECT COUNT(*) FROM workspaces
               WHERE workspace_type = 'organization'""",
        ),
        (
            "submission_documents_without_workspace",
            """SELECT COUNT(*) FROM documents
               WHERE document_type = 'submission' AND workspace_id IS NULL""",
        ),
        (
            "comparisons_without_workspace",
            """SELECT COUNT(*) FROM comparisons
               WHERE workspace_id IS NULL""",
        ),
        (
            "platform_references_not_normalized",
            """SELECT COUNT(*) FROM documents
               WHERE document_type = 'reference'
                 AND workspace_id IS NULL
                 AND visibility_scope <> 'platform'""",
        ),
    )

    failures = []
    maximum_upload_mb = max(1, int(app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)))
    with db.engine.connect() as connection:
        for label, statement in checks:
            count = connection.execute(text(statement)).scalar_one()
            if count:
                failures.append(f"{label}: {count}")
        oversized_requests = connection.execute(
            text("SELECT COUNT(*) FROM submission_requests WHERE max_file_size_mb > :maximum"),
            {"maximum": maximum_upload_mb},
        ).scalar_one()
        if oversized_requests:
            failures.append(f"submission_requests_above_upload_limit: {oversized_requests}")

    return not failures, failures


def _ensure_fast_indexes():
    """Ensure compatibility indexes without rescanning or rewriting data."""
    indexes = (
        "CREATE INDEX IF NOT EXISTS ix_documents_workspace_id ON documents (workspace_id)",
        "CREATE INDEX IF NOT EXISTS ix_documents_visibility_scope ON documents (visibility_scope)",
        "CREATE INDEX IF NOT EXISTS ix_comparisons_workspace_id ON comparisons (workspace_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_change_token_hash ON users (email_change_token_hash)",
    )
    with db.engine.begin() as connection:
        for statement in indexes:
            connection.execute(text(statement))


def _run_legacy_data_migration(app):
    """Run the pre-ledger additive schema and data migration exactly once."""
    with app.app_context():
        existing_tables = set(inspect(db.engine).get_table_names())
        if not REQUIRED_TABLES.issubset(existing_tables):
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
                user_column_names = {column["name"] for column in inspect(connection).get_columns("users")}
                user_additions = {
                    "email_verified_at": "TIMESTAMP",
                    "email_verification_token_hash": "VARCHAR(64)",
                    "email_verification_expires_at": "TIMESTAMP",
                    "pending_email": "VARCHAR(150)",
                    "email_change_token_hash": "VARCHAR(64)",
                    "email_change_expires_at": "TIMESTAMP",
                    "profile_image_mime": "VARCHAR(50)",
                    "profile_image_updated_at": "TIMESTAMP",
                    "password_reset_token_hash": "VARCHAR(64)",
                    "password_reset_expires_at": "TIMESTAMP",
                    "auth_version": "INTEGER NOT NULL DEFAULT 0",
                }
                for column_name, sql_type in user_additions.items():
                    if column_name not in user_column_names:
                        connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {sql_type}"))
                if "profile_image_data" not in user_column_names:
                    binary_type = "BYTEA" if db.engine.dialect.name == "postgresql" else "BLOB"
                    connection.execute(text(
                        f"ALTER TABLE users ADD COLUMN profile_image_data {binary_type}"
                    ))
                connection.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email_change_token_hash "
                    "ON users (email_change_token_hash)"
                ))
                # Existing active accounts predate email verification. Preserve
                # access by marking them verified during this additive migration.
                connection.execute(text(
                    "UPDATE users SET email_verified_at = COALESCE(email_verified_at, created_at) "
                    "WHERE is_active = TRUE AND email_verified_at IS NULL"
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
        if inspector.has_table("submission_requests"):
            request_columns = {column["name"] for column in inspector.get_columns("submission_requests")}
            if "allow_late_submissions" not in request_columns:
                with db.engine.begin() as connection:
                    connection.execute(text(
                        "ALTER TABLE submission_requests ADD COLUMN allow_late_submissions "
                        "BOOLEAN NOT NULL DEFAULT FALSE"
                    ))

        inspector = inspect(db.engine)
        if inspector.has_table("submission_requests"):
            maximum_upload_mb = max(1, int(app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024)))
            SubmissionRequest.query.filter(
                SubmissionRequest.max_file_size_mb > maximum_upload_mb
            ).update(
                {"max_file_size_mb": maximum_upload_mb},
                synchronize_session=False,
            )

        if inspector.has_table("workspace_invites"):
            invite_columns = {column["name"] for column in inspector.get_columns("workspace_invites")}
            if "course_id" not in invite_columns:
                with db.engine.begin() as connection:
                    connection.execute(text(
                        "ALTER TABLE workspace_invites ADD COLUMN course_id INTEGER"
                    ))

        # Existing shared workspaces keep their IDs, members and historical data.
        inspector = inspect(db.engine)
        if inspector.has_table("workspaces"):
            workspace_columns = {column["name"] for column in inspector.get_columns("workspaces")}
            with db.engine.begin() as connection:
                if "description" not in workspace_columns:
                    connection.execute(text("ALTER TABLE workspaces ADD COLUMN description TEXT"))
                connection.execute(text(
                    "UPDATE workspaces SET workspace_type = 'shared' "
                    "WHERE workspace_type = 'organization'"
                ))

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
        # administrator-curated references retain their records and receive a
        # rights-review state in the unified reference migration below.
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
        # Introduce the generic submission model without deleting legacy academic
        # records. Each legacy assignment and its submissions/reviews are copied
        # once into the new model, with source IDs retained for auditability.
        for legacy_assignment in Assignment.query.order_by(Assignment.assignment_id.asc()).all():
            generic_request = SubmissionRequest.query.filter_by(
                legacy_assignment_id=legacy_assignment.assignment_id
            ).first()
            if generic_request is None:
                legacy_status = legacy_assignment.status
                request_status = {
                    "published": "open",
                    "closed": "closed",
                    "draft": "draft",
                }.get(legacy_status, "archived")
                generic_request = SubmissionRequest(
                    workspace_id=legacy_assignment.course.workspace_id,
                    title=legacy_assignment.title,
                    description=legacy_assignment.description,
                    instructions=legacy_assignment.instructions,
                    due_at=legacy_assignment.due_at,
                    status=request_status,
                    accepted_file_types=["pdf", "docx", "txt"],
                    max_file_size_mb=max(1, int(app.config["MAX_CONTENT_LENGTH"] / (1024 * 1024))),
                    allow_late_submissions=legacy_assignment.allow_late_submissions,
                    allow_resubmissions=legacy_assignment.allow_resubmissions,
                    allow_external_participants=True,
                    created_by_user_id=legacy_assignment.created_by_user_id,
                    legacy_assignment_id=legacy_assignment.assignment_id,
                    created_at=legacy_assignment.created_at,
                    updated_at=legacy_assignment.updated_at,
                )
                db.session.add(generic_request)
                db.session.flush()

            course = legacy_assignment.course
            for course_member in course.memberships:
                if course_member.role == "lecturer":
                    existing_reviewer = SubmissionRequestReviewer.query.filter_by(
                        request_id=generic_request.request_id,
                        user_id=course_member.user_id,
                    ).first()
                    if not existing_reviewer:
                        db.session.add(SubmissionRequestReviewer(
                            request_id=generic_request.request_id,
                            user_id=course_member.user_id,
                            assigned_by_user_id=legacy_assignment.created_by_user_id,
                        ))
                elif course_member.role == "student":
                    existing_participant = SubmissionRequestParticipant.query.filter_by(
                        request_id=generic_request.request_id,
                        user_id=course_member.user_id,
                    ).first()
                    if existing_participant is None:
                        db.session.add(SubmissionRequestParticipant(
                            request_id=generic_request.request_id,
                            user_id=course_member.user_id,
                            participation_type="member",
                            status="active",
                        ))

            for legacy_submission in legacy_assignment.submissions:
                generic_submission = DocumentSubmission.query.filter_by(
                    legacy_submission_id=legacy_submission.submission_id
                ).first()
                if generic_submission is None:
                    generic_submission = DocumentSubmission(
                        request_id=generic_request.request_id,
                        contributor_user_id=legacy_submission.student_user_id,
                        document_id=legacy_submission.document_id,
                        comparison_id=legacy_submission.comparison_id,
                        legacy_submission_id=legacy_submission.submission_id,
                        attempt_number=legacy_submission.attempt_number,
                        status=legacy_submission.status,
                        is_late=legacy_submission.is_late,
                        submitted_at=legacy_submission.submitted_at,
                    )
                    db.session.add(generic_submission)
                    db.session.flush()

                existing_participant = SubmissionRequestParticipant.query.filter_by(
                    request_id=generic_request.request_id,
                    user_id=legacy_submission.student_user_id,
                ).first()
                if existing_participant is None:
                    db.session.add(SubmissionRequestParticipant(
                        request_id=generic_request.request_id,
                        user_id=legacy_submission.student_user_id,
                        participation_type="member",
                        status="active",
                    ))

                legacy_assessment = legacy_submission.assessment
                if legacy_assessment:
                    existing_review = SubmissionReview.query.filter_by(
                        submission_id=generic_submission.submission_id,
                        reviewer_user_id=legacy_assessment.assessor_user_id,
                    ).first()
                    if existing_review is None:
                        db.session.add(SubmissionReview(
                            submission_id=generic_submission.submission_id,
                            reviewer_user_id=legacy_assessment.assessor_user_id,
                            decision=legacy_assessment.decision,
                            feedback=legacy_assessment.feedback,
                            reviewed_at=legacy_assessment.reviewed_at,
                        ))
        # Normalize former academic workspace roles into the generic Member role.
        # Historical course memberships remain stored for audit and migration only.
        WorkspaceMembership.query.filter(
            WorkspaceMembership.role.in_(("student", "lecturer"))
        ).update({"role": "member"}, synchronize_session=False)
        WorkspaceInvite.query.filter(
            WorkspaceInvite.role != "member"
        ).update({"role": "member", "course_id": None}, synchronize_session=False)
        WorkspaceInvite.query.filter(WorkspaceInvite.course_id.isnot(None)).update(
            {"course_id": None}, synchronize_session=False
        )
        SubmissionReview.query.filter_by(decision="no_concern").update(
            {"decision": "no_action"}, synchronize_session=False
        )
        SubmissionReview.query.filter_by(decision="discuss_with_student").update(
            {"decision": "further_review"}, synchronize_session=False
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



def _run_reference_architecture_migration(app):
    """Create scoped reference entries and preserve provenance for existing sources."""
    from app.models import ComparisonResult

    with app.app_context():
        # create_all adds the new reference_entries table without modifying existing tables.
        db.create_all()
        inspector = inspect(db.engine)
        if inspector.has_table("comparison_results"):
            columns = {column["name"] for column in inspector.get_columns("comparison_results")}
            if "source_scope" not in columns:
                with db.engine.begin() as connection:
                    connection.execute(text(
                        "ALTER TABLE comparison_results ADD COLUMN source_scope VARCHAR(20)"
                    ))
            with db.engine.begin() as connection:
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_comparison_results_source_scope "
                    "ON comparison_results (source_scope)"
                ))

        existing_keys = {
            (entry.document_id, entry.scope_key)
            for entry in ReferenceEntry.query.with_entities(
                ReferenceEntry.document_id, ReferenceEntry.scope_key
            ).all()
        }

        legacy_references = (
            db.session.query(Document, Workspace.workspace_type)
            .outerjoin(Workspace, Workspace.workspace_id == Document.workspace_id)
            .filter(Document.document_type == "reference")
            .yield_per(250)
        )
        for document, workspace_type in legacy_references:
            if document.visibility_scope == "platform":
                scope = "global"
                scope_key = "global"
                status = "review_required"
                owner_user_id = None
                workspace_id = None
                rights_basis = "legacy_unverified"
                provenance_type = "legacy_platform_reference"
                rights_verified = False
            elif document.visibility_scope == "workspace" and workspace_type == "shared" and document.workspace_id:
                scope = "workspace"
                scope_key = f"workspace:{document.workspace_id}"
                status = "review_required"
                owner_user_id = None
                workspace_id = document.workspace_id
                rights_basis = "legacy_unverified"
                provenance_type = "legacy_workspace_reference"
                rights_verified = False
            else:
                scope = "personal"
                scope_key = f"personal:{document.user_id}"
                status = "active"
                owner_user_id = document.user_id
                workspace_id = None
                rights_basis = "personal_use_only"
                provenance_type = "legacy_personal_reference"
                rights_verified = False

            key = (document.document_id, scope_key)
            if key in existing_keys:
                continue
            db.session.add(ReferenceEntry(
                document_id=document.document_id,
                scope=scope,
                scope_key=scope_key,
                owner_user_id=owner_user_id,
                workspace_id=workspace_id,
                status=status,
                provenance_type=provenance_type,
                source_title=document.title,
                rights_basis=rights_basis,
                rights_verified=rights_verified,
                created_by_user_id=document.user_id,
                created_at=document.uploaded_at,
                updated_at=document.uploaded_at,
            ))
            existing_keys.add(key)

        request_submissions = (
            db.session.query(DocumentSubmission, Document)
            .join(Document, Document.document_id == DocumentSubmission.document_id)
            .yield_per(250)
        )
        for submission, document in request_submissions:
            scope_key = f"request:{submission.request_id}"
            key = (document.document_id, scope_key)
            if key in existing_keys:
                continue
            db.session.add(ReferenceEntry(
                document_id=document.document_id,
                scope="request",
                scope_key=scope_key,
                owner_user_id=submission.contributor_user_id,
                request_id=submission.request_id,
                status="active" if submission.status in ("submitted", "analysed", "analysis_failed") else "archived",
                provenance_type="submission_request_document",
                source_title=document.title,
                rights_basis="request_scoped_submission",
                rights_verified=False,
                created_by_user_id=submission.contributor_user_id,
                created_at=submission.submitted_at,
                updated_at=submission.submitted_at,
            ))
            existing_keys.add(key)

        db.session.flush()
        pending_results = (
            db.session.query(ComparisonResult, Document)
            .join(Document, Document.document_id == ComparisonResult.reference_document_id)
            .filter(ComparisonResult.source_scope.is_(None))
            .yield_per(250)
        )
        for result, reference in pending_results:
            if reference.document_type == "submission":
                result.source_scope = "request"
            elif reference.visibility_scope == "platform":
                result.source_scope = "global"
            elif reference.visibility_scope == "workspace":
                result.source_scope = "workspace"
            else:
                result.source_scope = "personal"

        db.session.commit()
        app.logger.info(
            "Unified reference architecture migration completed: %s reference entries registered.",
            ReferenceEntry.query.count(),
        )


def _run_simplified_reference_policy_migration(app):
    """Retire user-managed reference scopes without deleting historical files.

    New personal comparisons use the administrator-managed global bank. New
    Submission Request comparisons resolve peer submissions directly from
    document_submissions. Personal, workspace and request ReferenceEntry rows
    are therefore archived but retained for historical traceability.
    """
    with app.app_context():
        if not inspect(db.engine).has_table("reference_entries"):
            raise RuntimeError("The reference_entries table is missing; the reference architecture migration must run first.")

        with db.engine.begin() as connection:
            result = connection.execute(text(
                "UPDATE reference_entries "
                "SET status = 'archived', updated_at = CURRENT_TIMESTAMP "
                "WHERE scope IN ('personal', 'workspace', 'request') "
                "AND status <> 'archived'"
            ))

        app.logger.info(
            "Simplified reference policy migration completed: archived %s legacy user-managed reference entries.",
            result.rowcount if result.rowcount is not None else 0,
        )


# Keep migrations in ascending dependency order. Add future schema/data changes
# here with a new immutable version identifier and an idempotent migration
# function. Never edit a migration that has already been released.
def _run_acquisition_engine_migration(app):
    """Create the additive acquisition metadata and job tables."""
    with app.app_context():
        # SQLAlchemy create_all only creates missing tables; it does not alter
        # existing production tables or touch existing documents/reports.
        db.create_all()
        app.logger.info("Multi-source acquisition tables are ready.")


# Keep migrations in ascending dependency order. Add future migrations
# without modifying migration functions that have already shipped.
MIGRATIONS = (
    (LEGACY_BASELINE_VERSION, _run_legacy_data_migration),
    (REFERENCE_ARCHITECTURE_VERSION, _run_reference_architecture_migration),
    (SIMPLIFIED_REFERENCE_POLICY_VERSION, _run_simplified_reference_policy_migration),
    (ACQUISITION_ENGINE_VERSION, _run_acquisition_engine_migration),
)


def initialize_database(app):
    """Bootstrap the schema and apply only migrations not recorded as complete."""
    started_at = perf_counter()
    with app.app_context():
        inspector = inspect(db.engine)
        ledger_exists = inspector.has_table(MIGRATION_TABLE)

        # create_all is a first-install/bootstrap operation, not a per-restart
        # operation. Once the migration ledger exists, future schema changes
        # must be represented by explicit, versioned migrations.
        if not ledger_exists:
            db.create_all()
            _ensure_migration_table()
            app.logger.info(
                "Database bootstrap: created or verified initial tables and migration ledger."
            )

        applied = _applied_migrations()
        executed = []

        for version, migration in MIGRATIONS:
            if version in applied:
                continue

            if version == LEGACY_BASELINE_VERSION:
                baseline_complete, reasons = _legacy_baseline_status(app)
                if baseline_complete:
                    # 0.11.3 already performed these migrations at deployment.
                    # Verify the resulting schema/data invariants and stamp the
                    # baseline rather than repeating full-table ORM loops.
                    _ensure_fast_indexes()
                    _record_migration(version, "verified_existing_baseline")
                    applied.add(version)
                    executed.append((version, "verified_existing_baseline"))
                    app.logger.info(
                        "Database migration baseline verified; skipped legacy data migration."
                    )
                    continue

                app.logger.warning(
                    "Legacy database migration required; outstanding checks: %s",
                    "; ".join(reasons),
                )
                db.session.remove()
                migration(app)
                db.session.remove()
                baseline_complete, reasons = _legacy_baseline_status(app)
                if not baseline_complete:
                    raise RuntimeError(
                        "Database migration did not satisfy required checks: "
                        + "; ".join(reasons)
                    )
                _record_migration(version, "executed_legacy_migration")
                applied.add(version)
                executed.append((version, "executed_legacy_migration"))
                app.logger.info(
                    "One-time legacy database migration completed and recorded."
                )
                continue

            # Future migrations own their schema/data changes and must be safe
            # to retry if the process stops before their ledger record is saved.
            migration(app)
            _record_migration(version, "executed")
            applied.add(version)
            executed.append((version, "executed"))

        elapsed = perf_counter() - started_at
        if not executed:
            app.logger.info(
                "Database initialisation complete: no pending migrations (%.2f seconds).",
                elapsed,
            )
            return "current"

        app.logger.info(
            "Database initialisation complete: %s migration(s), elapsed_seconds=%.2f.",
            len(executed),
            elapsed,
        )
        return ",".join(mode for _, mode in executed)
