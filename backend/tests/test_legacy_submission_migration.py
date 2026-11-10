import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from config import Config
from app import create_app
from app.extensions import db
from app.models import (
    AcademicSubmission,
    Assignment,
    AssignmentAssessment,
    Course,
    CourseMembership,
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


class LegacyMigrationConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-generic-migration-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}


class LegacySubmissionMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        LegacyMigrationConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(LegacyMigrationConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.owner = self._make_user("owner@example.test")
        self.contributor = self._make_user("contributor@example.test")
        db.session.flush()
        self.workspace = Workspace(
            name="Former Academic Workspace",
            workspace_type="shared",
            status="active",
            owner_user_id=self.owner.user_id,
        )
        db.session.add(self.workspace)
        db.session.flush()
        db.session.add_all([
            WorkspaceMembership(
                workspace_id=self.workspace.workspace_id,
                user_id=self.owner.user_id,
                role="owner",
                status="active",
            ),
            WorkspaceMembership(
                workspace_id=self.workspace.workspace_id,
                user_id=self.contributor.user_id,
                role="student",
                status="active",
            ),
        ])
        self.course = Course(
            workspace_id=self.workspace.workspace_id,
            code="OLD-01",
            title="Legacy Course Record",
            description="Retained only as historical migration data.",
            status="active",
            join_code_hash="a" * 64,
            created_by_user_id=self.owner.user_id,
        )
        db.session.add(self.course)
        db.session.flush()
        db.session.add_all([
            CourseMembership(
                course_id=self.course.course_id,
                user_id=self.owner.user_id,
                role="lecturer",
                status="active",
                added_by_user_id=self.owner.user_id,
            ),
            CourseMembership(
                course_id=self.course.course_id,
                user_id=self.contributor.user_id,
                role="student",
                status="active",
                added_by_user_id=self.owner.user_id,
            ),
        ])
        self.assignment = Assignment(
            course_id=self.course.course_id,
            title="Legacy Assignment",
            description="Historical request description.",
            instructions="Historical instructions.",
            due_at=datetime.now(timezone.utc) + timedelta(days=3),
            status="published",
            allow_late_submissions=True,
            allow_resubmissions=True,
            created_by_user_id=self.owner.user_id,
        )
        db.session.add(self.assignment)
        db.session.flush()
        document = Document(
            user_id=self.contributor.user_id,
            title="Legacy submitted document",
            original_filename="legacy-submission.txt",
            storage_path="legacy-submission.txt",
            file_type="txt",
            document_type="submission",
            extracted_text="A sufficiently long historical document retained during generic migration.",
            file_hash="b" * 64,
            workspace_id=self.workspace.workspace_id,
            visibility_scope="private",
            processing_status="processed",
        )
        db.session.add(document)
        db.session.flush()
        self.legacy_submission = AcademicSubmission(
            assignment_id=self.assignment.assignment_id,
            student_user_id=self.contributor.user_id,
            document_id=document.document_id,
            attempt_number=1,
            status="analysed",
            is_late=False,
        )
        db.session.add(self.legacy_submission)
        db.session.flush()
        db.session.add(AssignmentAssessment(
            submission_id=self.legacy_submission.submission_id,
            assessor_user_id=self.owner.user_id,
            decision="discuss_with_student",
            feedback="Historical feedback must be preserved.",
        ))
        db.session.add(WorkspaceInvite(
            workspace_id=self.workspace.workspace_id,
            course_id=self.course.course_id,
            token_hash="c" * 64,
            role="student",
            created_by_user_id=self.owner.user_id,
        ))
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _make_user(self, email):
        user = User(
            first_name=email.split("@")[0],
            last_name="Test",
            full_name=email.split("@")[0].title(),
            email=email,
            password_hash=generate_password_hash("test-password-123"),
            role="user",
            is_active=True,
            email_verified_at=datetime.now(timezone.utc),
        )
        db.session.add(user)
        return user

    def test_legacy_records_are_migrated_to_generic_requests_without_data_loss(self):
        first = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(first.exit_code, 0, first.output)
        second = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(second.exit_code, 0, second.output)

        request_record = SubmissionRequest.query.filter_by(
            legacy_assignment_id=self.assignment.assignment_id
        ).one()
        self.assertEqual(request_record.title, "Legacy Assignment")
        self.assertEqual(request_record.status, "open")
        self.assertTrue(request_record.allow_late_submissions)
        self.assertTrue(request_record.allow_resubmissions)
        self.assertEqual(request_record.max_file_size_mb, 15)
        self.assertEqual(request_record.workspace_id, self.workspace.workspace_id)

        migrated_submission = DocumentSubmission.query.filter_by(
            legacy_submission_id=self.legacy_submission.submission_id
        ).one()
        self.assertEqual(migrated_submission.request_id, request_record.request_id)
        self.assertEqual(migrated_submission.document_id, self.legacy_submission.document_id)
        self.assertTrue(SubmissionRequestParticipant.query.filter_by(
            request_id=request_record.request_id,
            user_id=self.contributor.user_id,
            status="active",
        ).first())
        self.assertTrue(SubmissionRequestReviewer.query.filter_by(
            request_id=request_record.request_id,
            user_id=self.owner.user_id,
        ).first())
        review = SubmissionReview.query.filter_by(
            submission_id=migrated_submission.submission_id,
            reviewer_user_id=self.owner.user_id,
        ).one()
        self.assertEqual(review.decision, "further_review")
        self.assertEqual(review.feedback, "Historical feedback must be preserved.")

        self.assertEqual(WorkspaceMembership.query.filter_by(
            workspace_id=self.workspace.workspace_id,
            user_id=self.contributor.user_id,
        ).one().role, "member")
        invite = WorkspaceInvite.query.filter_by(token_hash="c" * 64).one()
        self.assertEqual(invite.role, "member")
        self.assertIsNone(invite.course_id)

        # Legacy rows are retained as migration sources rather than deleted.
        self.assertIsNotNone(db.session.get(Assignment, self.assignment.assignment_id))
        self.assertIsNotNone(db.session.get(AcademicSubmission, self.legacy_submission.submission_id))

    def test_previous_domain_api_routes_are_not_registered(self):
        client = self.app.test_client()
        for path in ("/api/courses", "/api/assignments", "/api/submissions/1"):
            response = client.get(path)
            self.assertEqual(response.status_code, 404, (path, response.get_json()))


if __name__ == "__main__":
    unittest.main()
