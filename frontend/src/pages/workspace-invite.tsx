import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { ArrowRight, FileSearch, ShieldCheck, Users } from 'lucide-react';
import { Notice, PageHeading } from '../components/ui';
import type { WorkspaceInvitePreviewData } from '../types';

export function WorkspaceInvitePage() {
    const data = useLoaderData() as WorkspaceInvitePreviewData;
    const actionData = useActionData() as { error?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const token = new URLSearchParams(window.location.search).get('token') || '';

    return <div className="login-page">
        <div className="login-aside">
            <Link viewTransition to="/" className="login-brand"><span className="brand-mark"><FileSearch size={22} /></span><span>AcaSift<small>Document similarity analysis</small></span></Link>
            <div className="login-aside-copy"><div className="eyebrow">SHARED WORKSPACE</div><h1>Work together.<br /><span>Review with clarity.</span></h1><p>Join a shared space for a team, research group, organisation or collaborative project.</p><div className="login-assurance"><ShieldCheck size={17} /> Your access is limited to this workspace.</div></div>
            <div className="login-aside-bottom">AcaSift · Document similarity analysis</div>
        </div>
        <div className="login-main">
            <div className="login-card">
                <PageHeading eyebrow="WORKSPACE INVITATION" title="Join a shared workspace" description="You have been invited to collaborate on AcaSift." />
                {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
                <div className="panel workspace-invite-preview">
                    <div className="workspace-invite-preview-icon"><Users size={24} /></div>
                    <h2>{data.workspace.name}</h2>
                    {data.workspace.description && <p>{data.workspace.description}</p>}
                    <div className="fact-list">
                        <div><span>Invited by</span><strong>{data.invited_by}</strong></div>
                        <div><span>Access granted</span><strong>Workspace member</strong></div>
                    </div>
                    {data.is_member && <Notice tone="info">You already belong to this workspace. Continue to open it.</Notice>}
                    <Form method="post">
                        <input type="hidden" name="token" value={token} />
                        <button className="button button-primary button-block" disabled={busy}>{busy ? 'Processing invitation…' : data.is_member ? 'Open this workspace' : 'Accept invitation and join'} <ArrowRight size={15} /></button>
                    </Form>
                    <p className="form-hint"><ShieldCheck size={14} /> Workspace administrators manage membership and permissions. Submission Request reviewers are assigned separately.</p>
                </div>
            </div>
        </div>
    </div>;
}
