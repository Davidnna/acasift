import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import {
    ArrowLeft, ArrowRight, BookOpen, CalendarClock, CheckCircle2, ClipboardList,
    Copy, FileCheck2, FileSearch, Plus, RefreshCw, ShieldCheck, Users,
} from 'lucide-react';
import { useState } from 'react';
import { EmptyState, formatDate, formatDateTime, Notice, PageHeading, StatusPill } from '../components/ui';
import type {
    AcademicSubmissionDetailData,
    AcademicSubmissionRecord,
    AssignmentDetailData,
    AssignmentRecord,
    CourseDetailData,
    CourseListData,
} from '../types';

type ActionData = { error?: string; success?: string; joinCode?: string; } | undefined;

function ActionFeedback({ data }: { data: ActionData; }) {
    if (data?.error) return <Notice tone="danger">{data.error}</Notice>;
    if (data?.success) return <Notice tone="success">{data.success}</Notice>;
    return null;
}

function JoinCodePanel({ code }: { code: string; }) {
    const [copied, setCopied] = useState(false);
    const copy = async () => {
        try {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1800);
        } catch {
            setCopied(false);
        }
    };
    return <div className="join-code-panel">
        <div><span className="eyebrow">COURSE ENROLMENT CODE</span><strong>{code}</strong><small>Share this code only with students and lecturers who belong to this workspace.</small></div>
        <button className="button button-secondary" type="button" onClick={copy}><Copy size={15} />{copied ? 'Copied' : 'Copy code'}</button>
    </div>;
}

function CourseCard({ course }: { course: CourseListData['courses'][number]; }) {
    return <Link viewTransition to={`/app/courses/${course.id}`} className="academic-course-card">
        <div className="academic-card-top"><span className="academic-code">{course.code}</span><span className="academic-role">{course.is_instructor ? 'Lecturer' : 'Student'}</span></div>
        <h3>{course.title}</h3>
        <p>{course.description || 'No course description has been added.'}</p>
        <div className="academic-card-meta"><span><Users size={14} />{course.member_count} members</span><span><ClipboardList size={14} />{course.assignment_count} assignments</span></div>
        <span className="academic-card-link">Open course <ArrowRight size={15} /></span>
    </Link>;
}

export function CoursesPage() {
    const data = useLoaderData() as CourseListData;
    const actionData = useActionData() as ActionData;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow="ACADEMIC COLLABORATION" title="Courses" description="Manage courses, assignments and student submissions in any shared workspace." action={<Link viewTransition className="button button-secondary" to="/app/assignments"><ClipboardList size={16} /> View assignments</Link>} />
        <div className="academic-context-strip"><span><BookOpen size={16} /> Active workspace</span><strong>{data.workspace.name}</strong><span className="category-tag">{data.workspace.type === 'shared' ? 'Shared workspace' : 'Personal workspace'}</span></div>
        <ActionFeedback data={actionData} />
        {data.message && <Notice tone="warning">{data.message} <Link className="text-link" to="/app/workspaces">Manage workspaces <ArrowRight size={13} /></Link></Notice>}
        {data.can_create && <section className="panel form-panel academic-form-panel"><div className="panel-heading"><div><h2><Plus size={17} /> Create a course</h2><p>Create a course in this shared workspace. You will be added as its lecturer.</p></div></div>
            <Form method="post" className="form-stack"><input type="hidden" name="_intent" value="create" /><div className="academic-form-grid"><div><label htmlFor="course-code">Course code</label><input id="course-code" name="code" required maxLength={40} placeholder="e.g. CSC401" /></div><div><label htmlFor="course-title">Course title</label><input id="course-title" name="title" required maxLength={180} placeholder="e.g. Research Methods" /></div></div><label htmlFor="course-description">Description <span>Optional</span></label><textarea id="course-description" name="description" rows={3} maxLength={5000} placeholder="Briefly describe the course and its academic focus." /><button className="button button-primary" disabled={busy}>{busy ? 'Creating course…' : 'Create course'} <ArrowRight size={15} /></button></Form>
        </section>}
        {data.can_join && <section className="panel form-panel academic-form-panel"><div className="panel-heading"><div><h2><Users size={17} /> Join a course</h2><p>Enter the enrolment code shared by your lecturer.</p></div></div>
            <Form method="post" className="form-stack"><input type="hidden" name="_intent" value="join" /><label htmlFor="join-code">Course enrolment code</label><input id="join-code" name="join_code" required maxLength={16} minLength={16} placeholder="16-character code" autoCapitalize="characters" /><button className="button button-primary" disabled={busy}>{busy ? 'Joining course…' : 'Join course'} <ArrowRight size={15} /></button></Form>
        </section>}
        <section className="academic-section"><div className="section-heading-inline"><div><span className="eyebrow">YOUR ACADEMIC SPACE</span><h2>Available courses</h2></div><span className="result-count">{data.courses.length} courses</span></div>
            {data.courses.length ? <div className="academic-course-grid">{data.courses.map(course => <CourseCard key={course.id} course={course} />)}</div> : <EmptyState title="No courses available" description={data.workspace.type === 'shared' ? 'Courses you teach or are enrolled in will appear here. Join with a course enrolment code or ask a workspace administrator to assign your role.' : 'Create or join a shared workspace to use courses and assignments.'} action={<Link className="button button-secondary" to="/app/workspaces">Open workspaces</Link>} />}
        </section>
        {actionData?.joinCode && <JoinCodePanel code={actionData.joinCode} />}
    </>;
}

function AssignmentCard({ assignment, isInstructor = false }: { assignment: AssignmentRecord; isInstructor?: boolean; }) {
    return <Link viewTransition to={`/app/assignments/${assignment.id}`} className="academic-assignment-card">
        <div className="academic-card-top"><span className="academic-code">{assignment.course_code || 'ASSIGNMENT'}</span><StatusPill value={assignment.status} /></div>
        <h3>{assignment.title}</h3>
        <p>{assignment.description || 'No description provided.'}</p>
        <div className="academic-card-meta"><span><CalendarClock size={14} />{assignment.due_at ? `Due ${formatDateTime(assignment.due_at)}` : 'No deadline'}</span>{isInstructor && <span><Users size={14} />{assignment.submission_count || 0} submissions</span>}</div>
        <span className="academic-card-link">Open assignment <ArrowRight size={15} /></span>
    </Link>;
}

export function CourseDetailPage() {
    const data = useLoaderData() as CourseDetailData;
    const actionData = useActionData() as ActionData;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow="COURSE SPACE" title={data.course.title} description={`${data.course.code} · ${data.course.member_count} members · ${data.course.assignment_count} assignments`} action={<Link className="button button-secondary" to="/app/courses"><ArrowLeft size={15} /> All courses</Link>} />
        <ActionFeedback data={actionData} />
        <div className="academic-detail-grid">
            <section className="panel academic-overview-panel"><div className="panel-heading"><div><h2>Course information</h2><p>Course details and participation.</p></div><span className="panel-icon"><BookOpen size={18} /></span></div><p>{data.course.description || 'No course description has been added.'}</p><div className="academic-fact-list"><div><span>Course code</span><strong>{data.course.code}</strong></div><div><span>Your role</span><strong>{data.course.is_instructor ? 'Lecturer / course manager' : 'Student'}</strong></div><div><span>Created</span><strong>{formatDate(data.course.created_at)}</strong></div></div></section>
            {data.can_manage && <section className="panel"><div className="panel-heading"><div><h2>Enrolment</h2><p>Generate a code for people in this workspace.</p></div><span className="panel-icon"><Users size={18} /></span></div>{actionData?.joinCode ? <JoinCodePanel code={actionData.joinCode} /> : <p className="muted-note">The enrolment code is stored securely. Generate a new code when you need to share access; generating a new one invalidates the previous code.</p>}<Form method="post"><input type="hidden" name="_intent" value="rotate-code" /><button className="button button-secondary" disabled={busy}><RefreshCw size={15} /> Generate enrolment code</button></Form></section>}
        </div>
        <section className="academic-section"><div className="section-heading-inline"><div><span className="eyebrow">COURSE WORK</span><h2>Assignments</h2></div><span className="result-count">{data.assignments.length} assignments</span></div>
            {data.assignments.length ? <div className="academic-assignment-grid">{data.assignments.map(item => <AssignmentCard key={item.id} assignment={item} isInstructor={data.can_manage} />)}</div> : <EmptyState title="No assignments yet" description={data.can_manage ? 'Create an assignment to begin collecting student work.' : 'Your lecturer has not published any assignments for this course.'} />}
        </section>
        {data.can_manage && <div className="academic-detail-grid academic-management-grid">
            <section className="panel form-panel"><div className="panel-heading"><div><h2><Plus size={17} /> Create assignment</h2><p>Set the task, instructions and deadline.</p></div></div>
                <Form method="post" className="form-stack"><input type="hidden" name="_intent" value="create-assignment" /><label htmlFor="assignment-title">Assignment title</label><input id="assignment-title" name="title" required maxLength={180} placeholder="e.g. Literature review" /><label htmlFor="assignment-description">Short description</label><textarea id="assignment-description" name="description" rows={2} maxLength={3000} placeholder="A short summary students will see." /><label htmlFor="assignment-instructions">Instructions</label><textarea id="assignment-instructions" name="instructions" rows={4} maxLength={10000} placeholder="Describe the task, format and submission requirements." /><label htmlFor="assignment-due">Deadline <span>Optional</span></label><input id="assignment-due" name="due_at" type="datetime-local" /><div className="academic-checkboxes"><label><input type="checkbox" name="allow_late_submissions" /> Accept late submissions</label><label><input type="checkbox" name="allow_resubmissions" /> Allow resubmissions</label></div><label htmlFor="assignment-status">Publishing</label><select id="assignment-status" name="status"><option value="published">Publish immediately</option><option value="draft">Save as draft</option></select><button className="button button-primary" disabled={busy}>{busy ? 'Creating assignment…' : 'Create assignment'} <ArrowRight size={15} /></button></Form>
            </section>
            <section className="panel"><div className="panel-heading"><div><h2><Users size={17} /> Course roster</h2><p>{data.members.length} active course members.</p></div></div>
                <Form method="post" className="form-stack academic-add-member"><input type="hidden" name="_intent" value="add-member" /><label htmlFor="member-email">Add existing workspace member</label><input id="member-email" name="email" type="email" required placeholder="person@example.com" /><label htmlFor="member-role">Course role</label><select id="member-role" name="role"><option value="student">Student</option><option value="lecturer">Lecturer</option></select><button className="button button-secondary" disabled={busy}>Add to course <Plus size={14} /></button><p className="form-hint">The person must already belong to this shared workspace with the matching workspace role.</p></Form>
                <div className="academic-roster">{data.members.map(member => <div className="academic-roster-row" key={member.id}><span className="avatar">{member.full_name.slice(0, 1).toUpperCase()}</span><span><strong>{member.full_name}</strong><small>{member.email}</small></span><span className="category-tag">{member.role}</span></div>)}</div>
            </section>
        </div>}
    </>;
}

export function AssignmentsPage() {
    const data = useLoaderData() as { assignments: AssignmentRecord[]; workspace: { name: string; type: string; }; };
    return <>
        <PageHeading eyebrow="ACADEMIC WORK" title="Assignments" description="Track coursework, deadlines and submission activity across your courses." action={<Link className="button button-primary" to="/app/courses"><BookOpen size={15} /> Browse courses</Link>} />
        <div className="academic-context-strip"><span><BookOpen size={16} /> Active workspace</span><strong>{data.workspace.name}</strong></div>
        {data.assignments.length ? <div className="academic-assignment-grid">{data.assignments.map(item => <AssignmentCard key={item.id} assignment={item} isInstructor={Boolean(item.is_instructor)} />)}</div> : <EmptyState title="No assignments available" description="Published assignments for courses you teach or attend will appear here. Join a course or ask a lecturer to enrol you." action={<Link className="button button-secondary" to="/app/courses">Open courses</Link>} />}
    </>;
}

export function AssignmentDetailPage() {
    const data = useLoaderData() as AssignmentDetailData;
    const actionData = useActionData() as ActionData;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow={`${data.course.code} · ASSIGNMENT`} title={data.assignment.title} description={data.assignment.description || 'Assignment details and submission activity.'} action={<Link className="button button-secondary" to={`/app/courses/${data.course.id}`}><ArrowLeft size={15} /> Back to course</Link>} />
        <ActionFeedback data={actionData} />
        <div className="report-overview academic-report-overview"><div><span>Assignment status</span><strong><StatusPill value={data.assignment.status} /></strong></div><div><span>Deadline</span><strong>{formatDateTime(data.assignment.due_at)}</strong></div><div><span>Submissions</span><strong>{data.is_instructor ? data.submissions.length : data.submissions.length ? data.submissions.length : 'Not submitted'}</strong></div></div>
        {data.assignment.instructions && <section className="panel academic-instructions"><div className="panel-heading"><div><h2>Instructions</h2><p>Review these requirements before submitting.</p></div></div><p>{data.assignment.instructions}</p></section>}
        {data.is_instructor ? <>
            <section className="panel academic-status-panel"><div className="panel-heading"><div><h2>Assignment availability</h2><p>Publish, pause or close submissions for this assignment.</p></div></div><Form method="post" className="academic-status-form"><input type="hidden" name="_intent" value="status" /><select name="status" defaultValue={data.assignment.status}><option value="draft">Draft — hidden from students</option><option value="published">Published — accepting submissions</option><option value="closed">Closed — no new submissions</option></select><button className="button button-secondary" disabled={busy}>Update status</button></Form></section>
            <section className="panel"><div className="panel-heading"><div><h2><Users size={17} /> Student submissions</h2><p>Submissions from students enrolled in this course.</p></div><span className="panel-icon"><FileCheck2 size={18} /></span></div>
                <div className="academic-analysis-banner"><div><strong>Assignment-wide peer analysis</strong><p>Recalculate each submission against all other submissions for this assignment. Student-facing reports remain anonymised.</p></div><Form method="post"><input type="hidden" name="_intent" value="analyse" /><button className="button button-primary" disabled={busy || data.submissions.length < 2}>{busy ? 'Analysing cohort…' : 'Run cohort analysis'} <FileSearch size={15} /></button></Form></div>
                {data.submissions.length ? <div className="table-scroll"><table className="data-table academic-table"><thead><tr><th>Student</th><th>Submission</th><th>Attempt</th><th>Submitted</th><th>Analysis</th><th>Review</th></tr></thead><tbody>{data.submissions.map(item => <tr key={item.id}><td><strong>{item.student?.full_name}</strong><small>{item.student?.email}</small></td><td><strong>{item.title}</strong><small>{item.filename}</small></td><td>#{item.attempt_number}</td><td>{formatDateTime(item.submitted_at)}{item.is_late && <span className="late-label">Late</span>}</td><td><StatusPill value={item.comparison_status} /></td><td><Link className="text-link" to={`/app/submissions/${item.id}`}>Review <ArrowRight size={13} /></Link></td></tr>)}</tbody></table></div> : <EmptyState title="No student submissions" description="Student work will appear here after they submit the assignment." />}
            </section>
        </> : <>
            {data.can_submit && <section className="panel form-panel academic-form-panel"><div className="panel-heading"><div><h2><FileCheck2 size={17} /> Submit your work</h2><p>Upload your assignment as a PDF, DOCX or TXT file.</p></div></div><Form method="post" encType="multipart/form-data" className="form-stack"><input type="hidden" name="_intent" value="submit" /><label htmlFor="submission-title">Submission title <span>Optional</span></label><input id="submission-title" name="title" maxLength={255} placeholder="e.g. Literature review submission" /><label htmlFor="submission-file">Document</label><input id="submission-file" name="document" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" required /><p className="form-hint">Maximum file size is 15 MB. Scanned image-only PDFs are not supported.</p><button className="button button-primary" disabled={busy}>{busy ? 'Uploading and analysing…' : 'Submit assignment'} <ArrowRight size={15} /></button></Form></section>}
            {!data.can_submit && <Notice tone={data.is_past_due ? 'warning' : 'info'}>{data.is_past_due && !data.assignment.allow_late_submissions ? 'The deadline has passed and late submissions are disabled.' : data.assignment.status !== 'published' ? 'This assignment is not currently accepting submissions.' : 'You have already submitted this assignment. Resubmissions are disabled.'}</Notice>}
            <section className="panel"><div className="panel-heading"><div><h2>Your submissions</h2><p>Only your own submission records are shown here.</p></div></div>{data.submissions.length ? <div className="account-list">{data.submissions.map(item => <SubmissionRow key={item.id} item={item} />)}</div> : <EmptyState title="No submission yet" description="Your submission history will appear here after you upload your work." />}</section>
        </>}
        <Notice tone="info"><strong>Academic integrity:</strong> Similarity indicators identify textual overlap for human review. They do not establish plagiarism or academic misconduct on their own.</Notice>
    </>;
}

function SubmissionRow({ item }: { item: AcademicSubmissionRecord; }) {
    return <div className="academic-submission-row"><span className="academic-submission-icon"><FileCheck2 size={17} /></span><span className="academic-submission-copy"><strong>{item.title}</strong><small>Attempt {item.attempt_number} · {formatDateTime(item.submitted_at)}{item.is_late ? ' · Late' : ''}</small></span><StatusPill value={item.status} /><Link className="text-link" to={`/app/submissions/${item.id}`}>View <ArrowRight size={13} /></Link></div>;
}

function decisionLabel(value: string) {
    if (value === 'no_concern') return 'No further action';
    if (value === 'discuss_with_student') return 'Discuss with student';
    if (value === 'further_review') return 'Further review required';
    return value;
}

export function AcademicSubmissionPage() {
    const data = useLoaderData() as AcademicSubmissionDetailData;
    const actionData = useActionData() as ActionData;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const comparison = data.comparison;
    return <>
        <PageHeading eyebrow="SUBMISSION REVIEW" title={data.submission.title} description={`${data.course.code} · ${data.assignment.title} · Attempt ${data.submission.attempt_number}`} action={<Link className="button button-secondary" to={`/app/assignments/${data.assignment.id}`}><ArrowLeft size={15} /> Back to assignment</Link>} />
        <ActionFeedback data={actionData} />
        <div className="report-overview academic-report-overview"><div><span>Submission status</span><strong><StatusPill value={data.submission.status} /></strong></div><div><span>Submitted</span><strong>{formatDateTime(data.submission.submitted_at)}</strong></div><div><span>Peer submissions compared</span><strong>{comparison?.peer_count ?? 0}</strong></div></div>
        {data.is_instructor && data.submission.student && <div className="academic-context-strip"><span><Users size={16} /> Submitted by</span><strong>{data.submission.student.full_name}</strong><span>{data.submission.student.email}</span></div>}
        {comparison ? <>
            {data.is_instructor ? <>
                <Notice tone="warning"><strong>Review standard:</strong> Similarity values are screening indicators, not findings of plagiarism. Consider quotations, citations, common terminology, assignment instructions and the full academic context.</Notice>
                {comparison.results?.length ? <section className="panel"><div className="panel-heading"><div><h2>Peer-source comparison</h2><p>Other submissions in this assignment, ranked by similarity.</p></div></div>
                    {comparison.results.map(result => <article className="comparison-result" key={result.id}><div className="comparison-result-head"><div><h3>{result.reference_document.student}</h3><p>{result.reference_document.title} · {result.reference_document.filename}</p></div><span className="match-count">{result.matched_ngram_count} matching word-sequence windows</span></div><div className="result-metrics"><Metric label="TF-IDF cosine similarity" value={`${result.cosine_similarity.toFixed(2)}%`} /><Metric label="N-gram occurrence coverage" value={`${result.matched_ngram_coverage.toFixed(2)}%`} /><Metric label="Matched / total windows" value={`${result.matched_ngram_count} / ${result.total_query_ngrams}`} /></div>{result.passages.length ? <div className="passage-section"><h4>Identified matching passages</h4>{result.passages.map((passage, index) => <div className="passage-card" key={passage.id}><div className="passage-heading">SUBMITTED PASSAGE · CHARACTERS {passage.submitted_start}–{passage.submitted_end}</div><p>{passage.matched_text}</p><div className="passage-heading reference-heading">PEER SUBMISSION PASSAGE</div><p>{passage.reference_text}</p></div>)}</div> : <p className="muted-note">No matching N-gram passages were identified for this source.</p>}</article>)}
                </section> : <EmptyState title="No peer overlap detected" description="No other submission produced a reportable similarity result. This is not a guarantee that the work contains no unattributed material." />}
            </> : <section className="panel academic-student-summary"><div className="panel-heading"><div><h2><ShieldCheck size={17} /> Your similarity overview</h2><p>Peer identities and other students' text are not disclosed in student reports.</p></div></div>{comparison.status === 'completed' ? comparison.peer_count ? <><div className="result-metrics"><Metric label="Peer submissions compared" value={String(comparison.peer_count)} /><Metric label="Highest cosine similarity" value={`${(comparison.highest_cosine_similarity || 0).toFixed(2)}%`} /><Metric label="Highest N-gram coverage" value={`${(comparison.highest_ngram_coverage || 0).toFixed(2)}%`} /></div><p className="muted-note">{comparison.note}</p></> : <EmptyState title="No peer submissions were available yet" description="Your submission is recorded. The lecturer can run a cohort-wide analysis after more students have submitted." /> : <Notice tone="warning">Similarity analysis has not completed. Your lecturer can rerun the assignment analysis.</Notice>}</section>}
        </> : <Notice tone="info">Your submission has been received. A similarity overview will appear after analysis is run.</Notice>}
        {data.assessment && <section className="panel academic-assessment-panel"><div className="panel-heading"><div><h2>Lecturer feedback</h2><p>Review outcome: {decisionLabel(data.assessment.decision)}</p></div><span className="panel-icon"><CheckCircle2 size={18} /></span></div><p>{data.assessment.feedback || 'No additional feedback was provided.'}</p><small className="muted-note">Reviewed by {data.assessment.assessor || 'Course lecturer'} · {formatDateTime(data.assessment.reviewed_at)}</small></section>}
        {data.is_instructor && <section className="panel form-panel"><div className="panel-heading"><div><h2>Record academic review</h2><p>Save a human assessment and feedback for this submission.</p></div></div><Form method="post" className="form-stack"><label htmlFor="review-decision">Review outcome</label><select id="review-decision" name="decision" defaultValue={data.assessment?.decision || 'further_review'}><option value="no_concern">No further action</option><option value="discuss_with_student">Discuss with student</option><option value="further_review">Further review required</option></select><label htmlFor="review-feedback">Feedback to student</label><textarea id="review-feedback" name="feedback" rows={5} maxLength={5000} defaultValue={data.assessment?.feedback || ''} placeholder="Explain what the student should clarify, correct or discuss." /><button className="button button-primary" disabled={busy}>{busy ? 'Saving review…' : 'Save academic review'} <ArrowRight size={15} /></button></Form></section>}
    </>;
}

function Metric({ label, value }: { label: string; value: string; }) {
    return <div className="result-metric"><span>{label}</span><strong>{value}</strong></div>;
}
