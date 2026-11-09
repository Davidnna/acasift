import hashlib
import os
import re
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    AcademicSubmission,
    Assignment,
    AssignmentAssessment,
    Comparison,
    Course,
    CourseMembership,
    Document,
    User,
    Workspace,
    WorkspaceMembership,
)
from app.services.academic_service import run_assignment_comparison
from app.services.auth_security import consume_auth_limits
from app.services.document_service import calculate_sha256, extract_text, is_allowed_file, make_storage_filename
from app.services.workspace_service import get_active_workspace, is_workspace_manager, membership_for

bp = Blueprint("academic_api", __name__, url_prefix="/api")


def _error(message, status=400):
    return jsonify({"error": message}), status


def _date(value):
    return value.isoformat() if value else None


def _token_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_datetime(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Enter a valid assignment deadline.")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _course_context(course_id, require_member=True):
    workspace = get_active_workspace(current_user)
    course = Course.query.filter_by(
        course_id=course_id,
        workspace_id=workspace.workspace_id,
        status="active",
    ).first()
    if not course:
        return None, None, None, False
    workspace_membership = membership_for(current_user, course.workspace_id)
    if not workspace_membership:
        return course, None, None, False
    course_membership = CourseMembership.query.filter_by(
        course_id=course.course_id,
        user_id=current_user.user_id,
        status="active",
    ).first()
    instructor = is_workspace_manager(workspace_membership) or bool(
        course_membership and course_membership.role == "lecturer"
    )
    if require_member and not instructor and not course_membership:
        return course, workspace_membership, None, False
    return course, workspace_membership, course_membership, instructor


def _assignment_context(assignment_id):
    workspace = get_active_workspace(current_user)
    assignment = (
        Assignment.query.join(Course)
        .filter(
            Assignment.assignment_id == assignment_id,
            Course.workspace_id == workspace.workspace_id,
            Course.status == "active",
        ).first()
    )
    if not assignment:
        return None, None, None, False
    course, workspace_membership, course_membership, instructor = _course_context(assignment.course_id)
    if not course or (not instructor and not course_membership):
        return assignment, None, None, False
    return assignment, course_membership, workspace_membership, instructor


def _course_payload(course, membership=None, instructor=False):
    return {
        "id": course.course_id,
        "workspace_id": course.workspace_id,
        "code": course.code,
        "title": course.title,
        "description": course.description,
        "status": course.status,
        "my_role": "lecturer" if instructor else (membership.role if membership else None),
        "is_instructor": bool(instructor),
        "member_count": CourseMembership.query.filter_by(course_id=course.course_id, status="active").count(),
        "assignment_count": Assignment.query.filter_by(course_id=course.course_id).count(),
        "created_at": _date(course.created_at),
    }


def _assignment_payload(assignment, include_counts=False):
    payload = {
        "id": assignment.assignment_id,
        "course_id": assignment.course_id,
        "title": assignment.title,
        "description": assignment.description,
        "instructions": assignment.instructions,
        "due_at": _date(assignment.due_at),
        "status": assignment.status,
        "allow_late_submissions": assignment.allow_late_submissions,
        "allow_resubmissions": assignment.allow_resubmissions,
        "created_by": assignment.creator.full_name if assignment.creator else None,
        "created_at": _date(assignment.created_at),
    }
    if include_counts:
        payload["submission_count"] = AcademicSubmission.query.filter_by(assignment_id=assignment.assignment_id).count()
    return payload


def _submission_payload(submission, include_student=False):
    payload = {
        "id": submission.submission_id,
        "assignment_id": submission.assignment_id,
        "document_id": submission.document_id,
        "title": submission.document.title,
        "filename": submission.document.original_filename,
        "attempt_number": submission.attempt_number,
        "status": submission.status,
        "is_late": submission.is_late,
        "submitted_at": _date(submission.submitted_at),
        "comparison_status": submission.comparison.status if submission.comparison else "not_started",
        "has_assessment": submission.assessment is not None,
        "assessment_decision": submission.assessment.decision if submission.assessment else None,
    }
    if include_student:
        payload["student"] = {
            "id": submission.student.user_id,
            "full_name": submission.student.full_name,
            "email": submission.student.email,
        }
    return payload


def _assessment_payload(assessment):
    if not assessment:
        return None
    return {
        "decision": assessment.decision,
        "feedback": assessment.feedback,
        "assessor": assessment.assessor.full_name if assessment.assessor else None,
        "reviewed_at": _date(assessment.reviewed_at),
    }


def _make_join_code():
    return secrets.token_hex(8).upper()


def _workspace_can_create(workspace, membership):
    return bool(
        workspace.workspace_type == "shared"
        and membership
        and membership.role in {"owner", "admin", "lecturer"}
    )


@bp.get("/courses")
@login_required
def list_courses():
    workspace = get_active_workspace(current_user)
    workspace_membership = membership_for(current_user, workspace.workspace_id)
    manager = is_workspace_manager(workspace_membership)
    can_create = _workspace_can_create(workspace, workspace_membership)
    query = Course.query.filter_by(workspace_id=workspace.workspace_id, status="active")
    if not manager:
        query = query.join(CourseMembership).filter(
            CourseMembership.user_id == current_user.user_id,
            CourseMembership.status == "active",
        )
    records = query.order_by(Course.code.asc()).all()
    courses = []
    for course in records:
        membership = CourseMembership.query.filter_by(
            course_id=course.course_id, user_id=current_user.user_id, status="active"
        ).first()
        instructor = manager or bool(membership and membership.role == "lecturer")
        courses.append(_course_payload(course, membership, instructor))
    return jsonify({
        "workspace": {"id": workspace.workspace_id, "name": workspace.name, "type": workspace.workspace_type},
        "courses": courses,
        "can_create": can_create,
        "can_join": bool(workspace.workspace_type == "shared" and workspace_membership and workspace_membership.role == "student"),
        "message": None if workspace.workspace_type == "shared" else "Create or join a shared workspace to use courses and assignments.",
    })


@bp.post("/courses")
@login_required
def create_course():
    workspace = get_active_workspace(current_user)
    workspace_membership = membership_for(current_user, workspace.workspace_id)
    if not _workspace_can_create(workspace, workspace_membership):
        return _error("Only workspace owners, administrators and lecturers can create courses in a shared workspace.", 403)
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,39}", code):
        return _error("Enter a course code containing 2–40 letters, numbers, hyphens or underscores.")
    if not title or len(title) > 180:
        return _error("Enter a course title containing no more than 180 characters.")
    if len(description) > 5000:
        return _error("The course description is too long.")
    join_code = _make_join_code()
    course = Course(
        workspace_id=workspace.workspace_id,
        code=code,
        title=title,
        description=description or None,
        status="active",
        join_code_hash=_token_hash(join_code),
        created_by_user_id=current_user.user_id,
    )
    db.session.add(course)
    try:
        db.session.flush()
        db.session.add(CourseMembership(
            course_id=course.course_id,
            user_id=current_user.user_id,
            role="lecturer",
            status="active",
            added_by_user_id=current_user.user_id,
        ))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("A course with this code already exists in the active workspace.", 409)
    return jsonify({"course": _course_payload(course, None, True), "join_code": join_code}), 201


@bp.post("/courses/join")
@login_required
def join_course():
    limited = consume_auth_limits(
        "course_join", identity=current_user.user_id,
        ip_limit=30, identity_limit=10, window_seconds=900,
    )
    if limited:
        payload, status, retry_after = limited
        response = jsonify(payload)
        response.status_code = status
        response.headers["Retry-After"] = str(retry_after)
        response.headers["Cache-Control"] = "no-store"
        return response
    workspace = get_active_workspace(current_user)
    workspace_membership = membership_for(current_user, workspace.workspace_id)
    if workspace.workspace_type != "shared" or not workspace_membership or workspace_membership.role != "student":
        return _error("You must join a shared workspace with the Student role before joining a course.", 403)
    data = request.get_json(silent=True) or {}
    code = re.sub(r"\s+", "", str(data.get("join_code", ""))).upper()
    if not re.fullmatch(r"[A-F0-9]{16}", code):
        return _error("Enter the 16-character course enrolment code.")
    course = Course.query.filter_by(
        workspace_id=workspace.workspace_id,
        join_code_hash=_token_hash(code),
        status="active",
    ).first()
    if not course:
        return _error("That course code is invalid, expired or belongs to another workspace.", 404)
    existing = CourseMembership.query.filter_by(course_id=course.course_id, user_id=current_user.user_id).first()
    if existing and existing.status == "active":
        return _error("You are already enrolled in this course.", 409)
    if existing:
        existing.status = "active"
        existing.role = "student"
        existing.enrolled_at = datetime.now(timezone.utc)
    else:
        db.session.add(CourseMembership(
            course_id=course.course_id,
            user_id=current_user.user_id,
            role="student",
            status="active",
            added_by_user_id=course.created_by_user_id,
        ))
    db.session.commit()
    return jsonify({"message": f"You have joined {course.code} — {course.title}.", "course_id": course.course_id}), 201


@bp.get("/courses/<int:course_id>")
@login_required
def course_detail(course_id):
    course, workspace_membership, membership, instructor = _course_context(course_id)
    if not course:
        return _error("Course not found in the active workspace.", 404)
    if not instructor and not membership:
        return _error("You are not enrolled in this course.", 403)
    assignments = Assignment.query.filter_by(course_id=course.course_id)
    if not instructor:
        assignments = assignments.filter(Assignment.status.in_(["published", "closed"]))
    assignment_records = assignments.order_by(Assignment.due_at.asc().nullslast(), Assignment.created_at.desc()).all()
    payload = {
        "course": _course_payload(course, membership, instructor),
        "assignments": [_assignment_payload(item, include_counts=instructor) for item in assignment_records],
        "can_manage": instructor,
        "members": [],
    }
    if instructor:
        roster = CourseMembership.query.filter_by(course_id=course.course_id, status="active").order_by(CourseMembership.role.asc()).all()
        payload["members"] = [{
            "id": item.user.user_id,
            "full_name": item.user.full_name,
            "email": item.user.email,
            "role": item.role,
            "enrolled_at": _date(item.enrolled_at),
        } for item in roster]
    return jsonify(payload)


@bp.post("/courses/<int:course_id>/join-code")
@login_required
def rotate_course_join_code(course_id):
    course, _workspace_membership, _membership, instructor = _course_context(course_id)
    if not course:
        return _error("Course not found in the active workspace.", 404)
    if not instructor:
        return _error("Only course lecturers and workspace managers can rotate the enrolment code.", 403)
    join_code = _make_join_code()
    course.join_code_hash = _token_hash(join_code)
    db.session.commit()
    return jsonify({"join_code": join_code, "message": "A new enrolment code has been generated. The previous code is no longer valid."})


@bp.post("/courses/<int:course_id>/members")
@login_required
def add_course_member(course_id):
    course, workspace_membership, _membership, instructor = _course_context(course_id)
    if not course:
        return _error("Course not found in the active workspace.", 404)
    if not instructor:
        return _error("Only course lecturers and workspace managers can manage course membership.", 403)
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    role = str(data.get("role", "student")).strip().lower()
    if role not in {"student", "lecturer"}:
        return _error("Choose student or lecturer as the course role.")
    target = User.query.filter_by(email=email, is_active=True).first()
    if not target:
        return _error("No active AcaSift account was found for that email address.", 404)
    target_workspace_membership = WorkspaceMembership.query.filter_by(
        workspace_id=course.workspace_id, user_id=target.user_id, status="active"
    ).first()
    if not target_workspace_membership:
        return _error("This person must first be a member of the shared workspace.", 409)
    if target_workspace_membership.role not in {role, "owner", "admin"}:
        return _error(f"The person's workspace role must be {role} before adding them to the course.", 409)
    existing = CourseMembership.query.filter_by(course_id=course.course_id, user_id=target.user_id).first()
    if existing and existing.status == "active":
        return _error("This person is already a member of the course.", 409)
    if existing:
        existing.role = role
        existing.status = "active"
        existing.added_by_user_id = current_user.user_id
        existing.enrolled_at = datetime.now(timezone.utc)
    else:
        db.session.add(CourseMembership(
            course_id=course.course_id,
            user_id=target.user_id,
            role=role,
            status="active",
            added_by_user_id=current_user.user_id,
        ))
    db.session.commit()
    return jsonify({"message": f"{target.full_name} was added to {course.code} as {role}."}), 201


@bp.get("/assignments")
@login_required
def list_assignments():
    workspace = get_active_workspace(current_user)
    workspace_membership = membership_for(current_user, workspace.workspace_id)
    manager = is_workspace_manager(workspace_membership)
    query = Assignment.query.join(Course).filter(
        Course.workspace_id == workspace.workspace_id,
        Course.status == "active",
    )
    if manager:
        pass
    else:
        query = query.join(CourseMembership).filter(
            CourseMembership.user_id == current_user.user_id,
            CourseMembership.status == "active",
        )
    records = query.order_by(Assignment.due_at.asc().nullslast(), Assignment.created_at.desc()).all()
    items = []
    for assignment in records:
        membership = CourseMembership.query.filter_by(
            course_id=assignment.course_id, user_id=current_user.user_id, status="active"
        ).first()
        instructor = manager or bool(membership and membership.role == "lecturer")
        if not instructor and assignment.status == "draft":
            continue
        items.append({
            **_assignment_payload(assignment, include_counts=instructor),
            "course_code": assignment.course.code,
            "course_title": assignment.course.title,
            "is_instructor": instructor,
        })
    return jsonify({"assignments": items, "workspace": {"name": workspace.name, "type": workspace.workspace_type}})


@bp.post("/courses/<int:course_id>/assignments")
@login_required
def create_assignment(course_id):
    course, _workspace_membership, _membership, instructor = _course_context(course_id)
    if not course:
        return _error("Course not found in the active workspace.", 404)
    if not instructor:
        return _error("Only course lecturers and workspace managers can create assignments.", 403)
    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    description = str(data.get("description", "")).strip()
    instructions = str(data.get("instructions", "")).strip()
    status = str(data.get("status", "draft")).strip().lower()
    if not title or len(title) > 180:
        return _error("Enter an assignment title containing no more than 180 characters.")
    if len(description) > 3000 or len(instructions) > 10000:
        return _error("The assignment description or instructions are too long.")
    if status not in {"draft", "published"}:
        return _error("An assignment must be saved as a draft or published.")
    try:
        due_at = _parse_datetime(data.get("due_at"))
    except ValueError as exc:
        return _error(str(exc))
    assignment = Assignment(
        course_id=course.course_id,
        title=title,
        description=description or None,
        instructions=instructions or None,
        due_at=due_at,
        status=status,
        allow_late_submissions=_bool(data.get("allow_late_submissions")),
        allow_resubmissions=_bool(data.get("allow_resubmissions")),
        created_by_user_id=current_user.user_id,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({"assignment": _assignment_payload(assignment, True), "message": "Assignment created successfully."}), 201


@bp.post("/assignments/<int:assignment_id>/status")
@login_required
def update_assignment_status(assignment_id):
    assignment, _membership, _workspace_membership, instructor = _assignment_context(assignment_id)
    if not assignment:
        return _error("Assignment not found in the active workspace.", 404)
    if not instructor:
        return _error("Only course lecturers and workspace managers can change assignment status.", 403)
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip().lower()
    if status not in {"draft", "published", "closed"}:
        return _error("Choose draft, published or closed as the assignment status.")
    assignment.status = status
    db.session.commit()
    return jsonify({"message": f"Assignment status changed to {status}.", "assignment": _assignment_payload(assignment)})


@bp.get("/assignments/<int:assignment_id>")
@login_required
def assignment_detail(assignment_id):
    assignment, membership, workspace_membership, instructor = _assignment_context(assignment_id)
    if not assignment:
        return _error("Assignment not found in the active workspace.", 404)
    if not instructor and not membership:
        return _error("You are not enrolled in this course.", 403)
    if not instructor and assignment.status == "draft":
        return _error("This assignment has not been published.", 404)
    query = AcademicSubmission.query.filter_by(assignment_id=assignment.assignment_id)
    if not instructor:
        query = query.filter_by(student_user_id=current_user.user_id)
    submissions = query.order_by(AcademicSubmission.submitted_at.desc()).all()
    now = datetime.now(timezone.utc)
    due_at = assignment.due_at
    if due_at and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    is_past_due = bool(due_at and due_at < now)
    can_submit = bool(
        not instructor
        and assignment.status == "published"
        and (not is_past_due or assignment.allow_late_submissions)
        and (assignment.allow_resubmissions or not submissions)
    )
    return jsonify({
        "assignment": _assignment_payload(assignment, include_counts=instructor),
        "course": _course_payload(assignment.course, membership, instructor),
        "is_instructor": instructor,
        "can_submit": can_submit,
        "is_past_due": is_past_due,
        "submissions": [_submission_payload(item, include_student=instructor) for item in submissions],
    })


@bp.post("/assignments/<int:assignment_id>/submit")
@login_required
def submit_assignment_file(assignment_id):
    assignment, membership, _workspace_membership, instructor = _assignment_context(assignment_id)
    if not assignment:
        return _error("Assignment not found in the active workspace.", 404)
    if instructor or not membership or membership.role != "student":
        return _error("Only enrolled students can submit work to this assignment.", 403)
    if assignment.status != "published":
        return _error("This assignment is not currently accepting submissions.", 409)
    now = datetime.now(timezone.utc)
    due_at = assignment.due_at
    if due_at and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    is_late = bool(due_at and now > due_at)
    if is_late and not assignment.allow_late_submissions:
        return _error("The assignment deadline has passed and late submissions are not allowed.", 409)
    previous = AcademicSubmission.query.filter_by(
        assignment_id=assignment.assignment_id,
        student_user_id=current_user.user_id,
    ).order_by(AcademicSubmission.attempt_number.desc()).all()
    if previous and not assignment.allow_resubmissions:
        return _error("You have already submitted this assignment. Resubmissions are disabled.", 409)

    file_storage = request.files.get("document")
    if not file_storage or not file_storage.filename:
        return _error("Choose a document to submit.")
    original_filename = secure_filename(file_storage.filename)
    if not original_filename or not is_allowed_file(original_filename, current_app.config["ALLOWED_EXTENSIONS"]):
        return _error("Only PDF, DOCX and TXT documents are supported.")
    file_bytes = file_storage.read()
    if not file_bytes:
        return _error("The selected document is empty.")
    try:
        extracted_text = extract_text(original_filename, file_bytes)
    except ValueError as exc:
        return _error(str(exc))
    file_hash = calculate_sha256(file_bytes)
    if any(item.document.file_hash == file_hash for item in previous):
        return _error("This exact file has already been submitted for this assignment.", 409)

    storage_name = make_storage_filename(original_filename)
    storage_path = current_app.config["UPLOAD_FOLDER"]
    with open(os.path.join(storage_path, storage_name), "wb") as stored_file:
        stored_file.write(file_bytes)
    document_title = str(request.form.get("title") or "").strip()
    if not document_title:
        document_title = original_filename.rsplit(".", 1)[0]
    document = Document(
        user_id=current_user.user_id,
        workspace_id=assignment.course.workspace_id,
        visibility_scope="private",
        title=document_title[:255],
        original_filename=original_filename[:255],
        storage_path=storage_name,
        file_type=original_filename.rsplit(".", 1)[-1].lower(),
        document_type="submission",
        extracted_text=extracted_text,
        file_hash=file_hash,
        processing_status="processed",
    )
    db.session.add(document)
    db.session.flush()
    submission = AcademicSubmission(
        assignment_id=assignment.assignment_id,
        student_user_id=current_user.user_id,
        document_id=document.document_id,
        attempt_number=(previous[0].attempt_number + 1) if previous else 1,
        status="submitted",
        is_late=is_late,
    )
    db.session.add(submission)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        try:
            os.remove(os.path.join(storage_path, storage_name))
        except OSError:
            current_app.logger.warning("Could not remove an uncommitted assignment upload: %s", storage_name)
        return _error("A submission was recorded at the same time. Refresh the page and check your submission history.", 409)

    try:
        peers = (
            Document.query.join(AcademicSubmission, AcademicSubmission.document_id == Document.document_id)
            .filter(
                AcademicSubmission.assignment_id == assignment.assignment_id,
                AcademicSubmission.submission_id != submission.submission_id,
                AcademicSubmission.status.in_(["submitted", "analysed", "analysis_failed"]),
            )
            .order_by(AcademicSubmission.submitted_at.desc())
            .limit(current_app.config["MAX_COMPARISON_SOURCES"])
            .all()
        )
        run_assignment_comparison(submission, peers)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Assignment submission peer comparison failed.")
        submission = db.session.get(AcademicSubmission, submission.submission_id)
        if submission:
            submission.status = "analysis_failed"
            db.session.commit()
    return jsonify({
        "submission": _submission_payload(submission),
        "message": "Your assignment has been submitted. Similarity analysis is available in your submission overview.",
    }), 201


@bp.post("/assignments/<int:assignment_id>/analyse")
@login_required
def analyse_assignment_cohort(assignment_id):
    assignment, _membership, _workspace_membership, instructor = _assignment_context(assignment_id)
    if not assignment:
        return _error("Assignment not found in the active workspace.", 404)
    if not instructor:
        return _error("Only course lecturers and workspace managers can run cohort-wide analysis.", 403)
    submissions = AcademicSubmission.query.filter_by(assignment_id=assignment.assignment_id).order_by(AcademicSubmission.submitted_at.asc()).all()
    if len(submissions) < 2:
        return _error("At least two student submissions are required for peer comparison.", 409)
    documents = {item.submission_id: item.document for item in submissions}
    completed = 0
    for submission in submissions:
        peers = [doc for item_id, doc in documents.items() if item_id != submission.submission_id]
        peers = peers[:current_app.config["MAX_COMPARISON_SOURCES"]]
        try:
            run_assignment_comparison(submission, peers)
            completed += 1
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Cohort-wide analysis failed for submission %s.", submission.submission_id)
            failed = db.session.get(AcademicSubmission, submission.submission_id)
            if failed:
                failed.status = "analysis_failed"
                db.session.commit()
    return jsonify({
        "message": f"Cohort-wide analysis completed for {completed} of {len(submissions)} submissions.",
        "completed": completed,
        "total": len(submissions),
    })


@bp.get("/submissions/<int:submission_id>")
@login_required
def academic_submission_detail(submission_id):
    submission = AcademicSubmission.query.get_or_404(submission_id)
    assignment = submission.assignment
    course, workspace_membership, course_membership, instructor = _course_context(assignment.course_id)
    if not course or (not instructor and current_user.user_id != submission.student_user_id):
        return _error("You do not have permission to view this submission.", 403)
    if not instructor and not course_membership:
        return _error("You are not enrolled in this course.", 403)
    comparison = submission.comparison
    assessment = _assessment_payload(submission.assessment)
    payload = {
        "submission": _submission_payload(submission, include_student=instructor),
        "assignment": _assignment_payload(assignment),
        "course": _course_payload(course, course_membership, instructor),
        "is_instructor": instructor,
        "assessment": assessment,
        "comparison": None,
    }
    if comparison:
        results = sorted(
            comparison.results,
            key=lambda item: (float(item.cosine_similarity), float(item.matched_ngram_coverage)),
            reverse=True,
        )
        if instructor:
            detail_results = []
            for result in results:
                reference = result.reference_document
                detail_results.append({
                    "id": result.result_id,
                    "reference_document": {
                        "id": reference.document_id,
                        "title": reference.title,
                        "filename": reference.original_filename,
                        "student": reference.uploader.full_name if reference.uploader else "Student",
                    },
                    "cosine_similarity": float(result.cosine_similarity),
                    "matched_ngram_coverage": float(result.matched_ngram_coverage),
                    "matched_ngram_count": result.matched_ngram_count,
                    "total_query_ngrams": result.total_query_ngrams,
                    "passages": [{
                        "id": passage.passage_id,
                        "matched_text": passage.matched_text,
                        "reference_text": (reference.extracted_text or "")[passage.reference_start:passage.reference_end],
                        "submitted_start": passage.submitted_start,
                        "submitted_end": passage.submitted_end,
                    } for passage in result.passages],
                })
            payload["comparison"] = {
                "status": comparison.status,
                "started_at": _date(comparison.started_at),
                "completed_at": _date(comparison.completed_at),
                "peer_count": len(results),
                "results": detail_results,
            }
        else:
            payload["comparison"] = {
                "status": comparison.status,
                "started_at": _date(comparison.started_at),
                "completed_at": _date(comparison.completed_at),
                "peer_count": len(results),
                "highest_cosine_similarity": max((float(item.cosine_similarity) for item in results), default=0.0),
                "highest_ngram_coverage": max((float(item.matched_ngram_coverage) for item in results), default=0.0),
                "note": "This overview does not reveal other students' identities, documents or matched passages. Detailed peer-source evidence is available to authorised course lecturers.",
            }
    return jsonify(payload)


@bp.post("/submissions/<int:submission_id>/assessment")
@login_required
def assess_academic_submission(submission_id):
    submission = AcademicSubmission.query.get_or_404(submission_id)
    course, _workspace_membership, _course_membership, instructor = _course_context(submission.assignment.course_id)
    if not course:
        return _error("Submission not found in the active workspace.", 404)
    if not instructor:
        return _error("Only course lecturers and workspace managers can assess submissions.", 403)
    data = request.get_json(silent=True) or {}
    decision = str(data.get("decision", "")).strip().lower()
    feedback = str(data.get("feedback", "")).strip()
    if decision not in {"no_concern", "discuss_with_student", "further_review"}:
        return _error("Choose a valid review outcome.")
    if len(feedback) > 5000:
        return _error("Feedback must not exceed 5,000 characters.")
    assessment = submission.assessment
    if assessment is None:
        assessment = AssignmentAssessment(submission_id=submission.submission_id)
        db.session.add(assessment)
    assessment.assessor_user_id = current_user.user_id
    assessment.decision = decision
    assessment.feedback = feedback or None
    assessment.reviewed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Your assessment has been saved.", "assessment": _assessment_payload(assessment)})
