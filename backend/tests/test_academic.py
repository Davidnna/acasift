import io
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
    ComparisonResult,
    Course,
    CourseMembership,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.services.workspace_service import ensure_personal_workspace


class AcademicConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-academic-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    NGRAM_SIZE = 4
    MAX_COMPARISON_SOURCES = 50


class AcademicWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        AcademicConfig.UPLOAD_FOLDER = os.path.join(self.temp_dir.name, "uploads")
        self.app = create_app(AcademicConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.workspace = Workspace(
            name="Example University",
            workspace_type="shared",
            status="active",
            owner_user_id=1,
        )
        self.lecturer = self._make_user("Lecturer", "One", "lecturer@example.test")
        db.session.flush()
        self.workspace.owner_user_id = self.lecturer.user_id
        db.session.add(self.workspace)
        db.session.flush()
        db.session.add(WorkspaceMembership(
            workspace_id=self.workspace.workspace_id,
            user_id=self.lecturer.user_id,
            role="lecturer",
            status="active",
        ))
        self.student_one = self._make_user("Student", "One", "student1@example.test")
        self.student_two = self._make_user("Student", "Two", "student2@example.test")
        db.session.flush()
        for student in (self.student_one, self.student_two):
            db.session.add(WorkspaceMembership(
                workspace_id=self.workspace.workspace_id,
                user_id=student.user_id,
                role="student",
                status="active",
            ))
            ensure_personal_workspace(student)
        ensure_personal_workspace(self.lecturer)
        db.session.commit()

        self.lecturer_client = self._login(self.lecturer, "lecturer-password-123")
        self.student_one_client = self._login(self.student_one, "student1-password-123")
        self.student_two_client = self._login(self.student_two, "student2-password-123")
        self._activate_workspace(self.lecturer_client)
        self._activate_workspace(self.student_one_client)
        self._activate_workspace(self.student_two_client)

        response = self.lecturer_client.post("/api/courses", json={
            "code": "CSC401",
            "title": "Research Methods",
            "description": "Research design and academic writing.",
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.course_id = response.get_json()["course"]["id"]
        self.join_code = response.get_json()["join_code"]
        for client in (self.student_one_client, self.student_two_client):
            joined = client.post("/api/courses/join", json={"join_code": self.join_code})
            self.assertEqual(joined.status_code, 201, joined.get_json())

        assignment_response = self.lecturer_client.post(
            f"/api/courses/{self.course_id}/assignments",
            json={
                "title": "Literature Review",
                "description": "Submit a short literature review.",
                "instructions": "Discuss the supplied research topic.",
                "due_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                "status": "published",
                "allow_late_submissions": False,
                "allow_resubmissions": False,
            },
        )
        self.assertEqual(assignment_response.status_code, 201, assignment_response.get_json())
        self.assignment_id = assignment_response.get_json()["assignment"]["id"]

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()
        self.temp_dir.cleanup()

    def _make_user(self, first, last, email):
        user = User(
            first_name=first,
            last_name=last,
            full_name=f"{first} {last}",
            email=email,
            password_hash=generate_password_hash(f"{email.split('@')[0]}-password-123"),
            role="user",
            is_active=True,
        )
        db.session.add(user)
        return user

    def _login(self, user, password):
        client = self.app.test_client()
        response = client.post("/api/auth/login", json={"email": user.email, "password": password})
        self.assertEqual(response.status_code, 200, response.get_json())
        return client

    def _activate_workspace(self, client):
        with client.session_transaction() as session:
            session["active_workspace_id"] = self.workspace.workspace_id

    def _submit(self, client, title, content, assignment_id=None):
        target_assignment_id = assignment_id or self.assignment_id
        return client.post(
            f"/api/assignments/{target_assignment_id}/submit",
            data={
                "title": title,
                "document": (io.BytesIO(content.encode("utf-8")), f"{title}.txt"),
            },
            content_type="multipart/form-data",
        )

    def test_init_db_migrates_legacy_request_submissions_and_reviews(self):
        uploaded = self._submit(
            self.student_one_client,
            "Migration Test Document",
            "A sufficiently long document used to verify preservation during migration.",
        )
        self.assertEqual(uploaded.status_code, 201, uploaded.get_json())
        legacy_submission_id = uploaded.get_json()["submission"]["id"]
        assessment = self.lecturer_client.post(
            f"/api/submissions/{legacy_submission_id}/assessment",
            json={"decision": "discuss_with_student", "feedback": "Migration feedback."},
        )
        self.assertEqual(assessment.status_code, 200, assessment.get_json())

        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)
        second_run = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(second_run.exit_code, 0, second_run.output)

        from app.submission_models import (
            DocumentSubmission, SubmissionRequest, SubmissionRequestParticipant,
            SubmissionRequestReviewer, SubmissionReview,
        )

        migrated = SubmissionRequest.query.filter_by(
            legacy_assignment_id=self.assignment_id
        ).one()
        self.assertEqual(migrated.title, "Literature Review")
        self.assertEqual(migrated.status, "open")
        self.assertEqual(migrated.workspace_id, self.workspace.workspace_id)
        generic_submission = DocumentSubmission.query.filter_by(
            legacy_submission_id=legacy_submission_id
        ).one()
        self.assertEqual(generic_submission.request_id, migrated.request_id)
        self.assertTrue(SubmissionRequestParticipant.query.filter_by(
            request_id=migrated.request_id,
            user_id=self.student_one.user_id,
            status="active",
        ).first())
        self.assertTrue(SubmissionRequestReviewer.query.filter_by(
            request_id=migrated.request_id,
            user_id=self.lecturer.user_id,
        ).first())
        self.assertTrue(SubmissionReview.query.filter_by(
            submission_id=generic_submission.submission_id,
            reviewer_user_id=self.lecturer.user_id,
            decision="discuss_with_student",
        ).first())

    def test_course_and_assignment_are_created_for_organisation(self):
        response = self.lecturer_client.get("/api/courses")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["courses"][0]["code"], "CSC401")
        detail = self.student_one_client.get(f"/api/courses/{self.course_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["assignments"][0]["title"], "Literature Review")

    def test_academic_features_are_unavailable_in_personal_workspaces(self):
        personal_workspace = ensure_personal_workspace(self.lecturer)
        db.session.commit()
        with self.lecturer_client.session_transaction() as session:
            session["active_workspace_id"] = personal_workspace.workspace_id

        self.assertEqual(self.lecturer_client.get("/api/courses").status_code, 403)
        self.assertEqual(self.lecturer_client.get("/api/assignments").status_code, 403)
        self.assertEqual(
            self.lecturer_client.get(f"/api/courses/{self.course_id}").status_code,
            404,
        )
        self.assertEqual(
            self.lecturer_client.get(f"/api/assignments/{self.assignment_id}").status_code,
            404,
        )

        # Restore the shared workspace so tear-down and later tests remain isolated.
        self._activate_workspace(self.lecturer_client)

    def test_student_cannot_create_assignment_or_view_unenrolled_course(self):
        denied = self.student_one_client.post(
            f"/api/courses/{self.course_id}/assignments",
            json={"title": "Unauthorised assignment", "status": "published"},
        )
        self.assertEqual(denied.status_code, 403)
        other = self._make_user("Other", "Person", "other@example.test")
        db.session.flush()
        db.session.add(WorkspaceMembership(
            workspace_id=self.workspace.workspace_id,
            user_id=other.user_id,
            role="member",
            status="active",
        ))
        ensure_personal_workspace(other)
        db.session.commit()
        other_client = self._login(other, "other-password-123")
        with other_client.session_transaction() as session:
            session["active_workspace_id"] = self.workspace.workspace_id
        self.assertEqual(other_client.get(f"/api/courses/{self.course_id}").status_code, 403)
        self.assertEqual(other_client.get("/api/courses").status_code, 403)
        self.assertEqual(other_client.get("/api/assignments").status_code, 403)

    def test_join_code_is_scoped_to_workspace_and_student_role(self):
        wrong = self.student_one_client.post("/api/courses/join", json={"join_code": "F" * 16})
        self.assertEqual(wrong.status_code, 404)
        already = self.student_one_client.post("/api/courses/join", json={"join_code": self.join_code})
        self.assertEqual(already.status_code, 409)

    def test_assignment_submission_is_compared_only_with_same_assignment_peers(self):
        phrase = "Academic integrity requires careful source acknowledgement and transparent research methods."
        first = self._submit(self.student_one_client, "Student One Review", phrase)
        self.assertEqual(first.status_code, 201, first.get_json())
        second = self._submit(self.student_two_client, "Student Two Review", f"Introduction. {phrase} Conclusion.")
        self.assertEqual(second.status_code, 201, second.get_json())

        second_id = second.get_json()["submission"]["id"]
        second_report = self.student_two_client.get(f"/api/submissions/{second_id}")
        self.assertEqual(second_report.status_code, 200)
        comparison = second_report.get_json()["comparison"]
        self.assertEqual(comparison["peer_count"], 1)
        self.assertNotIn("results", comparison)
        self.assertNotIn("Student One", str(second_report.get_json()))
        self.assertNotIn(phrase, str(second_report.get_json()))

        # The generic comparison endpoint must not expose the academic peer report.
        submission = AcademicSubmission.query.get(second_id)
        blocked = self.student_two_client.get(f"/api/comparisons/{submission.comparison_id}")
        self.assertEqual(blocked.status_code, 403)

    def test_lecturer_can_run_cohort_analysis_and_view_peer_evidence(self):
        phrase = "Research methods require transparent sampling and accurate documentation of sources."
        self.assertEqual(self._submit(self.student_one_client, "First Review", phrase).status_code, 201)
        self.assertEqual(self._submit(self.student_two_client, "Second Review", f"{phrase} This is an additional conclusion.").status_code, 201)

        result = self.lecturer_client.post(f"/api/assignments/{self.assignment_id}/analyse")
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertEqual(result.get_json()["completed"], 2)

        submissions = AcademicSubmission.query.filter_by(assignment_id=self.assignment_id).all()
        self.assertEqual(len(submissions), 2)
        for submission in submissions:
            detail = self.lecturer_client.get(f"/api/submissions/{submission.submission_id}")
            self.assertEqual(detail.status_code, 200)
            payload = detail.get_json()
            self.assertEqual(payload["comparison"]["peer_count"], 1)
            self.assertIn("results", payload["comparison"])
            self.assertTrue(payload["comparison"]["results"][0]["reference_document"]["student"])

    def test_lecturer_can_assess_submission_and_student_can_see_feedback(self):
        response = self._submit(self.student_one_client, "Assessment Review", "This is a sufficiently long academic text for assessment.")
        self.assertEqual(response.status_code, 201)
        submission_id = response.get_json()["submission"]["id"]
        assessed = self.lecturer_client.post(f"/api/submissions/{submission_id}/assessment", json={
            "decision": "discuss_with_student",
            "feedback": "Please meet to discuss the matching passages and source attribution.",
        })
        self.assertEqual(assessed.status_code, 200, assessed.get_json())
        student_detail = self.student_one_client.get(f"/api/submissions/{submission_id}")
        self.assertEqual(student_detail.status_code, 200)
        self.assertEqual(student_detail.get_json()["assessment"]["decision"], "discuss_with_student")

    def test_student_cannot_view_another_students_submission_or_assess_it(self):
        response = self._submit(self.student_one_client, "Private Review", "Private academic content for the first student only.")
        self.assertEqual(response.status_code, 201)
        submission_id = response.get_json()["submission"]["id"]
        self.assertEqual(self.student_two_client.get(f"/api/submissions/{submission_id}").status_code, 403)
        self.assertEqual(self.student_two_client.post(f"/api/submissions/{submission_id}/assessment", json={
            "decision": "no_concern", "feedback": "Unauthorised",
        }).status_code, 403)

    def test_peer_comparisons_never_cross_assignment_boundaries(self):
        second_assignment = self.lecturer_client.post(
            f"/api/courses/{self.course_id}/assignments",
            json={
                "title": "Separate Research Task",
                "description": "A separate assignment in the same course.",
                "status": "published",
            },
        )
        self.assertEqual(second_assignment.status_code, 201, second_assignment.get_json())
        second_assignment_id = second_assignment.get_json()["assignment"]["id"]
        phrase = "The same sentence appears in separate assignment submissions for boundary testing."
        first = self._submit(self.student_one_client, "First Assignment Work", phrase, self.assignment_id)
        second = self._submit(self.student_two_client, "Second Assignment Work", phrase, second_assignment_id)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        second_submission_id = second.get_json()["submission"]["id"]
        report = self.student_two_client.get(f"/api/submissions/{second_submission_id}")
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.get_json()["comparison"]["peer_count"], 0)

    def test_lecturer_can_close_assignment_and_block_new_submissions(self):
        response = self.lecturer_client.post(
            f"/api/assignments/{self.assignment_id}/status",
            json={"status": "closed"},
        )
        self.assertEqual(response.status_code, 200)
        detail = self.student_one_client.get(f"/api/assignments/{self.assignment_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.get_json()["can_submit"])
        submitted = self._submit(self.student_one_client, "Closed Assignment", "This work should not be accepted.")
        self.assertEqual(submitted.status_code, 409)

    def test_student_cannot_submit_twice_when_resubmissions_disabled(self):
        first = self._submit(self.student_one_client, "First Attempt", "Original academic content for the first attempt.")
        self.assertEqual(first.status_code, 201)
        second = self._submit(self.student_one_client, "Second Attempt", "Different academic content for the second attempt.")
        self.assertEqual(second.status_code, 409)


if __name__ == "__main__":
    unittest.main()
