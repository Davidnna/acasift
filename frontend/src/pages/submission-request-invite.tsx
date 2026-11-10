import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { ArrowRight, FileSearch, ShieldCheck, Upload } from 'lucide-react';
import { Notice, PageHeading, StatusPill, formatDateTime } from '../components/ui';
import type { SubmissionRequestInvitePreviewData } from '../types';

export function SubmissionRequestInvitePage() {
    const data = useLoaderData() as SubmissionRequestInvitePreviewData;
    const actionData = useActionData() as { error?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const token = new URLSearchParams(window.location.search).get('token') || '';
    const item = data.submission_request;

    return <div className="login-page">
        <div className="login-aside">
            <Link viewTransition to="/" className="login-brand"><span className="brand-mark"><FileSearch size={22} /></span><span>AcaSift<small>Document similarity analysis</small></span></Link>
            <div className="login-aside-copy"><div className="eyebrow">DOCUMENT SUBMISSION</div><h1>Submit securely.<br /><span>Review with clarity.</span></h1><p>This link provides access to one document submission request. It does not add you to the shared workspace.</p><div className="login-assurance"><ShieldCheck size={17} /> Your access is restricted to this request.</div></div>
            <div className="login-aside-bottom">AcaSift · Document similarity analysis</div>
        </div>
        <div className="login-main">
            <div className="login-card">
                <PageHeading eyebrow="SUBMISSION LINK" title={item.title} description={item.description || 'You have been invited to submit a document for review.'} />
                {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
                <div className="panel workspace-invite-preview">
                    <div className="workspace-invite-preview-icon"><Upload size={24} /></div>
                    <div className="submission-request-invite-meta"><StatusPill value={item.status} /><span>{item.workspace_name}</span></div>
                    {item.instructions && <div className="submission-instructions-copy">{item.instructions}</div>}
                    <div className="fact-list">
                        <div><span>Link shared by</span><strong>{data.invited_by}</strong></div>
                        <div><span>Opens</span><strong>{formatDateTime(item.opens_at)}</strong></div>
                        <div><span>Deadline</span><strong>{formatDateTime(item.due_at)}</strong></div>
                        <div><span>Accepted formats</span><strong>{item.accepted_file_types.map(type => type.toUpperCase()).join(', ')}</strong></div>
                        <div><span>Maximum file size</span><strong>{item.max_file_size_mb} MB</strong></div>
                    </div>
                    {data.already_joined && <Notice tone="info">You already have access to this request. Continue to open it.</Notice>}
                    <Form method="post">
                        <input type="hidden" name="token" value={token} />
                        <button className="button button-primary button-block" disabled={busy}>{busy ? 'Opening request…' : data.already_joined ? 'Open submission request' : 'Accept link and continue'} <ArrowRight size={15} /></button>
                    </Form>
                    <p className="form-hint"><ShieldCheck size={14} /> You must be signed in with a verified AcaSift account. Other workspace documents and submissions remain private.</p>
                </div>
            </div>
        </div>
    </div>;
}
