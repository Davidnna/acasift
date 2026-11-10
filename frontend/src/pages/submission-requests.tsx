import { useState } from 'react';
import {
    Form,
    Link,
    useActionData,
    useLoaderData,
    useNavigation,
} from 'react-router-dom';
import {
    ArrowLeft,
    ArrowRight,
    CalendarClock,
    Copy,
    FileSearch,
    FileText,
    Link2,
    Plus,
    Upload,
    UserRoundCheck,
} from 'lucide-react';
import {
    EmptyState,
    formatDateTime,
    Notice,
    PageHeading,
    StatusPill,
} from '../components/ui';
import type {
    SubmissionRequestDetailData,
    SubmissionRequestListData,
} from '../types';

type ActionData = {
    error?: string;
    success?: string;
    inviteUrl?: string;
};

function toDateTimeLocal(value: string | null) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
    return localDate.toISOString().slice(0, 16);
}

function ActionFeedback({ data }: { data: ActionData | undefined; }) {
    if (data?.error) return <Notice tone="danger">{data.error}</Notice>;
    if (data?.success) return <Notice tone="success">{data.success}</Notice>;
    return null;
}

function RequestCard({ request }: { request: SubmissionRequestListData['submission_requests'][number]; }) {
    return <Link viewTransition to={`/app/submission-requests/${request.id}`} className="submission-request-card">
        <div className="submission-request-card-top">
            <span className="submission-request-icon"><FileText size={18} /></span>
            <StatusPill value={request.status} />
        </div>
        <h3>{request.title}</h3>
        <p>{request.description || 'No description has been added.'}</p>
        <div className="submission-request-card-meta">
            <span><FileSearch size={14} />{request.submission_count ?? '—'} submissions</span>
            <span><CalendarClock size={14} />{request.due_at ? `Due ${formatDateTime(request.due_at)}` : 'No deadline'}</span>
        </div>
        <span className="submission-card-link">Open request <ArrowRight size={15} /></span>
    </Link>;
}

export function SubmissionRequestsPage() {
    const data = useLoaderData() as SubmissionRequestListData;
    const actionData = useActionData() as ActionData | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';

    return <>
        <PageHeading
            eyebrow="DOCUMENT COLLABORATION"
            title="Submission Requests"
            description={`Collect documents, run similarity analysis and review submissions in ${data.workspace.name}.`}
        />
        <ActionFeedback data={actionData} />

        {data.can_manage && <section className="panel form-panel">
            <div className="panel-heading">
                <div><h2><Plus size={17} /> Create a Submission Request</h2><p>Define what participants should submit and how the request will operate.</p></div>
            </div>
            <Form method="post" className="form-stack">
                <input type="hidden" name="_intent" value="create" />
                <label htmlFor="request-title">Title</label>
                <input id="request-title" name="title" required maxLength={180} placeholder="e.g. Research report collection" />
                <label htmlFor="request-description">Description <span>Optional</span></label>
                <textarea id="request-description" name="description" rows={2} maxLength={5000} placeholder="Briefly explain the purpose of this request." />
                <label htmlFor="request-instructions">Submission instructions <span>Optional</span></label>
                <textarea id="request-instructions" name="instructions" rows={4} maxLength={10000} placeholder="Explain what participants should provide and any requirements they should follow." />
                <div className="submission-request-form-grid">
                    <div><label htmlFor="request-opens">Opens at <span>Optional</span></label><input id="request-opens" name="opens_at" type="datetime-local" /></div>
                    <div><label htmlFor="request-due">Deadline <span>Optional</span></label><input id="request-due" name="due_at" type="datetime-local" /></div>
                </div>
                <div className="submission-request-form-grid">
                    <div><label htmlFor="request-max-size">Maximum file size (MB)</label><input id="request-max-size" name="max_file_size_mb" type="number" min="1" max="15" defaultValue="15" required /></div>
                    <fieldset className="submission-options-fieldset">
                        <legend>Accepted formats</legend>
                        <div className="submission-format-options" id="request-formats">
                            <label><input type="checkbox" name="accepted_file_types" value="pdf" defaultChecked /> PDF</label>
                            <label><input type="checkbox" name="accepted_file_types" value="docx" defaultChecked /> DOCX</label>
                            <label><input type="checkbox" name="accepted_file_types" value="txt" defaultChecked /> TXT</label>
                        </div>
                    </fieldset>
                </div>
                <fieldset className="submission-options-fieldset submission-rules-fieldset">
                    <legend>Submission rules</legend>
                    <div className="submission-request-settings">
                        <label><input type="checkbox" name="allow_late_submissions" /> Accept submissions after the deadline</label>
                        <label><input type="checkbox" name="allow_resubmissions" /> Allow participants to submit more than once</label>
                        <label><input type="checkbox" name="allow_external_participants" defaultChecked /> Allow authenticated people outside this workspace to submit using a request link</label>
                    </div>
                </fieldset>
                <p className="form-hint">New requests start as drafts. Open a request when its instructions and settings are ready.</p>
                <button className="button button-primary" disabled={busy}>{busy ? 'Creating request…' : 'Create Submission Request'} <ArrowRight size={15} /></button>
            </Form>
        </section>}

        <section className="submission-request-section">
            <div className="section-heading-inline">
                <div><span className="eyebrow">SHARED WORKSPACE</span><h2>Available requests</h2></div>
                <span className="result-count">{data.submission_requests.length} requests</span>
            </div>
            {data.submission_requests.length ? <div className="submission-request-grid">
                {data.submission_requests.map(item => <RequestCard key={item.id} request={item} />)}
            </div> : <EmptyState
                title="No submission requests yet"
                description={data.can_manage ? 'Create a request when you are ready to collect documents from workspace members or external participants.' : 'Open requests created by workspace administrators will appear here.'}
                action={data.can_manage ? <a className="button button-secondary" href="#request-title">Create a request</a> : undefined}
            />}
        </section>
    </>;
}

export function SubmissionRequestDetailPage() {
    const data = useLoaderData() as SubmissionRequestDetailData;
    const actionData = useActionData() as ActionData | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const [copied, setCopied] = useState(false);
    const item = data.submission_request;
    const canManage = data.permissions.can_manage;
    const backPath = data.permissions.is_external_participant ? '/app/dashboard' : '/app/submission-requests';

    async function copyInvite() {
        if (!actionData?.inviteUrl) return;
        try {
            await navigator.clipboard.writeText(actionData.inviteUrl);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1800);
        } catch {
            setCopied(false);
        }
    }

    return <>
        <PageHeading
            eyebrow="SUBMISSION REQUEST"
            title={item.title}
            description={item.description || `A document collection request in ${item.workspace_name || 'a shared workspace'}.`}
            action={<Link viewTransition className="button button-secondary" to={backPath}><ArrowLeft size={15} /> Back</Link>}
        />
        <ActionFeedback data={actionData} />
        <div className="submission-request-overview">
            <div><span>Status</span><strong><StatusPill value={item.status} /></strong></div>
            <div><span>Opens</span><strong>{formatDateTime(item.opens_at)}</strong></div>
            <div><span>Deadline</span><strong>{formatDateTime(item.due_at)}</strong></div>
            <div><span>Accepted formats</span><strong>{item.accepted_file_types.map(type => type.toUpperCase()).join(', ')}</strong></div>
            <div><span>Maximum file size</span><strong>{item.max_file_size_mb} MB</strong></div>
            <div><span>Late submissions</span><strong>{item.allow_late_submissions ? 'Accepted' : 'Not accepted'}</strong></div>
            <div><span>Resubmissions</span><strong>{item.allow_resubmissions ? 'Allowed' : 'One per account'}</strong></div>
            {canManage && <>
                <div><span>Submissions</span><strong>{item.submission_count ?? data.submissions.length}</strong></div>
                <div><span>Participants</span><strong>{item.participant_count ?? '—'}</strong></div>
            </>}
        </div>

        {item.status === 'open' && !data.permissions.can_submit && !data.permissions.can_join && !data.permissions.can_review && <Notice tone="info">The submission window is not currently available to your account. Check the opening time and deadline, or contact the request organiser.</Notice>}

        {item.instructions && <section className="panel submission-instructions-panel">
            <div className="panel-heading"><div><h2>Instructions</h2><p>Requirements provided by the request creator.</p></div></div>
            <div className="submission-instructions-copy">{item.instructions}</div>
        </section>}

        {canManage && <section className="panel form-panel">
            <details className="submission-request-edit">
                <summary>Edit request details</summary>
                <Form method="post" className="form-stack">
                    <input type="hidden" name="_intent" value="edit" />
                    <label htmlFor="edit-request-title">Title</label>
                    <input id="edit-request-title" name="title" maxLength={180} defaultValue={item.title} required />
                    <label htmlFor="edit-request-description">Description</label>
                    <textarea id="edit-request-description" name="description" rows={2} maxLength={5000} defaultValue={item.description || ''} />
                    <label htmlFor="edit-request-instructions">Instructions</label>
                    <textarea id="edit-request-instructions" name="instructions" rows={4} maxLength={10000} defaultValue={item.instructions || ''} />
                    <div className="submission-request-form-grid">
                        <div><label htmlFor="edit-request-opens">Opens at</label><input id="edit-request-opens" name="opens_at" type="datetime-local" defaultValue={toDateTimeLocal(item.opens_at)} /></div>
                        <div><label htmlFor="edit-request-due">Deadline</label><input id="edit-request-due" name="due_at" type="datetime-local" defaultValue={toDateTimeLocal(item.due_at)} /></div>
                    </div>
                    <button className="button button-secondary" disabled={busy}>Save request details</button>
                </Form>
            </details>
        </section>}

        {canManage && <section className="panel form-panel">
            <div className="panel-heading"><div><h2>Manage request</h2><p>Control whether participants can submit documents.</p></div></div>
            <Form method="post" className="form-actions">
                <input type="hidden" name="_intent" value="status" />
                <label className="visually-hidden" htmlFor="request-status">Request status</label>
                <select id="request-status" name="status" defaultValue={item.status}>
                    <option value="draft">Draft</option>
                    <option value="open">Open</option>
                    <option value="closed">Closed</option>
                    <option value="archived">Archived</option>
                </select>
                <button className="button button-primary" disabled={busy}>Save status</button>
            </Form>
        </section>}

        {data.permissions.can_join && <section className="panel form-panel">
            <div className="panel-heading"><div><h2>Participate in this request</h2><p>Join the request to submit documents and receive your results.</p></div></div>
            <Form method="post"><input type="hidden" name="_intent" value="join" /><button className="button button-primary" disabled={busy}>Join request <ArrowRight size={15} /></button></Form>
        </section>}

        {data.permissions.can_submit && <section className="panel form-panel">
            <div className="panel-heading"><div><h2><Upload size={17} /> Submit a document</h2><p>Your document will be compared with other eligible submissions in this same request.</p></div></div>
            <Form method="post" encType="multipart/form-data" className="form-stack">
                <input type="hidden" name="_intent" value="submit" />
                <label htmlFor="submission-title">Document title <span>Optional</span></label>
                <input id="submission-title" name="title" maxLength={255} placeholder="Use the filename if left blank" />
                <label htmlFor="submission-file">Choose document</label>
                <input id="submission-file" type="file" name="document" accept={item.accepted_file_types.map(type => `.${type}`).join(',')} aria-describedby="submission-file-hint" required />
                <p className="form-hint" id="submission-file-hint">Accepted: {item.accepted_file_types.map(type => type.toUpperCase()).join(', ')} · Maximum size: {item.max_file_size_mb} MB. {item.allow_resubmissions ? 'Resubmissions are allowed.' : 'Only one submission is allowed per account.'}</p>
                <button className="button button-primary" disabled={busy}>{busy ? 'Submitting and analysing…' : 'Submit and analyse'} <ArrowRight size={15} /></button>
            </Form>
        </section>}

        {actionData?.inviteUrl && canManage && <section className="panel workspace-invite-created">
            <div className="panel-heading"><div><h2><Link2 size={17} /> External submission link created</h2><p>Share this link with people who are not members of the workspace.</p></div></div>
            <div className="form-stack">
                <input aria-label="External submission link" readOnly value={actionData.inviteUrl} onFocus={event => event.currentTarget.select()} />
                <button type="button" className="button button-primary" onClick={copyInvite}><Copy size={15} /> {copied ? 'Copied' : 'Copy submission link'}</button>
            </div>
            <p className="form-hint">The link grants access to this request only. It does not add recipients to the workspace.</p>
        </section>}

        {canManage && item.allow_external_participants && <section className="panel form-panel">
            <div className="panel-heading"><div><h2><Link2 size={17} /> External submission access</h2><p>Create a restricted link for authenticated people outside this workspace.</p></div></div>
            <Form method="post" className="form-stack">
                <input type="hidden" name="_intent" value="create-invite" />
                <label htmlFor="request-link-expiry">Link expiration <span>Optional</span></label>
                <input id="request-link-expiry" name="expires_at" type="datetime-local" />
                <label htmlFor="request-link-uses">Maximum uses <span>Optional</span></label>
                <input id="request-link-uses" name="max_uses" type="number" min="1" max="10000" placeholder="No limit" />
                <button className="button button-secondary" disabled={busy}>Create external submission link <Link2 size={15} /></button>
            </Form>
            {item.invites && item.invites.length > 0 && <div className="account-list submission-invite-list">
                {item.invites.map(invite => <div className="account-row" key={invite.id}>
                    <span className="account-row-copy"><strong>Submission link</strong><small>{invite.use_count}{invite.max_uses === null ? ' uses' : ` of ${invite.max_uses} uses`} · {invite.expires_at ? `Expires ${formatDateTime(invite.expires_at)}` : 'No expiration'}</small></span>
                    <StatusPill value={invite.status} />
                    {invite.status === 'active' && <Form method="post"><input type="hidden" name="_intent" value="revoke-invite" /><input type="hidden" name="invite_id" value={invite.id} /><button className="button button-secondary button-small" disabled={busy}>Revoke</button></Form>}
                </div>)}
            </div>}
        </section>}

        {canManage && <section className="panel form-panel">
            <div className="panel-heading"><div><h2><UserRoundCheck size={17} /> Assign reviewers</h2><p>Reviewers can inspect every submission in this request without becoming workspace administrators.</p></div></div>
            {item.reviewers && item.reviewers.length > 0 && <div className="account-list">
                {item.reviewers.map(reviewer => <div className="account-row" key={reviewer.id}>
                    <span className="account-row-copy"><strong>{reviewer.full_name}</strong><small>{reviewer.email}</small></span>
                    <Form method="post"><input type="hidden" name="_intent" value="remove-reviewer" /><input type="hidden" name="user_id" value={reviewer.id} /><button className="button button-secondary button-small" disabled={busy}>Remove</button></Form>
                </div>)}
            </div>}
            {data.workspace_members.length > 0 ? <Form method="post" className="form-actions">
                <input type="hidden" name="_intent" value="assign-reviewer" />
                <label className="visually-hidden" htmlFor="request-reviewer">Workspace member</label>
                <select id="request-reviewer" name="user_id" required defaultValue="">
                    <option value="" disabled>Select a workspace member</option>
                    {data.workspace_members.filter(member => !(item.reviewers || []).some(reviewer => reviewer.id === member.id)).map(member => <option key={member.id} value={member.id}>{member.full_name} · {member.email}</option>)}
                </select>
                <button className="button button-secondary" disabled={busy}>Assign reviewer</button>
            </Form> : <p className="muted-note">There are no other eligible workspace members to assign.</p>}
        </section>}

        <section className="panel">
            <div className="panel-heading"><div><h2><FileSearch size={17} /> Submissions</h2><p>{canManage || data.permissions.can_review ? 'Documents received for this request.' : 'Your submission receipts and reviewer feedback.'}</p></div><span className="result-count">{data.submissions.length} shown</span></div>
            {data.submissions.length ? <div className="submission-list">
                {data.submissions.map(submission => <article className="submission-row" key={submission.id}>
                    <div className="submission-row-heading">
                        <span className="submission-row-icon"><FileText size={18} /></span>
                        <div className="submission-row-copy"><strong>{submission.title}</strong><small>{submission.filename} · Attempt {submission.attempt_number} · {formatDateTime(submission.submitted_at)}</small>{submission.contributor && <small>Submitted by {submission.contributor.full_name} · {submission.contributor.email}</small>}</div>
                        <StatusPill value={submission.status} />
                    </div>
                    <div className="submission-row-actions">
                        {submission.is_late && <span className="category-tag">Late submission</span>}

                    </div>
                    {submission.review && <div className="submission-review-summary">
                        <strong>Review outcome: {reviewDecisionLabel(submission.review.decision)}</strong>
                        {submission.review.feedback && <p>{submission.review.feedback}</p>}
                        <small>{submission.review.reviewer ? `Reviewed by ${submission.review.reviewer}` : 'Review recorded'}{submission.review.reviewed_at ? ` · ${formatDateTime(submission.review.reviewed_at)}` : ''}</small>
                    </div>}
                    {data.permissions.can_review && <details className="submission-review-editor">
                        <summary>{submission.review ? 'Update review' : 'Add review and feedback'}</summary>
                        <Form method="post" className="form-stack">
                            <input type="hidden" name="_intent" value="review" />
                            <input type="hidden" name="submission_id" value={submission.id} />
                            <label htmlFor={`review-decision-${submission.id}`}>Review outcome</label>
                            <select id={`review-decision-${submission.id}`} name="decision" defaultValue={normaliseReviewDecision(submission.review?.decision)}>
                                <option value="no_action">No action required</option>
                                <option value="revision_requested">Revision requested</option>
                                <option value="further_review">Further review required</option>
                            </select>
                            <label htmlFor={`review-feedback-${submission.id}`}>Feedback <span>Optional</span></label>
                            <textarea id={`review-feedback-${submission.id}`} name="feedback" rows={3} maxLength={5000} defaultValue={submission.review?.feedback || ''} placeholder="Record findings or explain the next steps." />
                            <button className="button button-primary" disabled={busy}>Save review</button>
                        </Form>
                    </details>}
                </article>)}
            </div> : <EmptyState title="No submissions yet" description={data.permissions.can_submit ? 'Your document submissions will appear here after you upload them.' : 'Submissions will appear here when participants send their documents.'} />}
        </section>

        <Notice tone="info"><strong>Similarity results require human interpretation.</strong> Textual overlap is an indicator for review, not an automatic finding of plagiarism or misconduct.</Notice>
    </>;
}

function reviewDecisionLabel(decision: string) {
    if (decision === 'no_action') return 'No action required';
    if (decision === 'revision_requested') return 'Revision requested';
    return 'Further review required';
}

function normaliseReviewDecision(decision?: string) {
    if (decision === 'no_action' || decision === 'revision_requested' || decision === 'further_review') return decision;
    return 'further_review';
}
