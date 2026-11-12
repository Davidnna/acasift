import { useState } from 'react';
import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import {
    Users, Copy, Link2, ShieldCheck,
    Clock3, Ban, UserPlus, Plus,
} from 'lucide-react';
import { Notice, PageHeading } from '../components/ui';
import type { WorkspaceData } from '../types';

type WorkspaceActionData = {
    error?: string;
    success?: string;
    inviteUrl?: string;
};

function displayDate(value: string | null) {
    return value ? new Date(value).toLocaleString() : 'No expiration';
}

function formatWorkspaceRole(role: string | null) {
    if (role === 'owner') return 'Owner';
    if (role === 'admin') return 'Administrator';
    return 'Member';
}

export function WorkspacesPage() {
    const data = useLoaderData() as WorkspaceData;
    const actionData = useActionData() as WorkspaceActionData | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const [copied, setCopied] = useState(false);
    const active = data.workspaces.find(item => item.id === data.active_workspace_id);

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
            eyebrow="WORKSPACE MANAGEMENT"
            title="Shared workspaces"
            description="Create a workspace for your group or join one using an invitation link."
        />
        {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
        {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
        {actionData?.inviteUrl && data.can_manage_members && <section className="panel workspace-invite-created">
            <div className="panel-heading">
                <div><h2><Link2 size={17} /> Invitation link created</h2><p>Copy and share this link. It will only work while it remains active.</p></div>
            </div>
            <div className="form-stack">
                <input aria-label="Workspace invitation URL" readOnly value={actionData.inviteUrl} onFocus={event => event.currentTarget.select()} />
                <button type="button" className="button button-primary" onClick={copyInvite}>
                    <Copy size={15} /> {copied ? 'Copied' : 'Copy invitation link'}
                </button>
            </div>
            <p className="form-hint">Copy this link now. If you lose it, create a new invitation link.</p>
        </section>}

        <section className="panel">
            <div className="panel-heading">
                <div><h2><Users size={17} /> Your workspaces</h2><p>Choose the shared workspace you want to work in.</p></div>
            </div>
            <div className="workspace-card-list">
                {data.workspaces.map(workspace => <div className={`workspace-choice ${workspace.id === data.active_workspace_id ? 'workspace-choice-active' : ''}`} key={workspace.id}>
                    <div className="workspace-choice-icon"><Users size={19} /></div>
                    <div className="workspace-choice-copy">
                        <strong>{workspace.name}</strong>
                        <span>{workspace.member_count} members · {formatWorkspaceRole(workspace.role)}</span>
                        {workspace.description && <span>{workspace.description}</span>}
                    </div>
                    {workspace.id === data.active_workspace_id ? <span className="category-tag">Current workspace</span> : <Form method="post"><input type="hidden" name="_intent" value="switch" /><input type="hidden" name="workspace_id" value={workspace.id} /><button className="button button-secondary button-small" disabled={busy}>Switch workspace</button></Form>}
                </div>)}
            </div>
            {!data.workspaces.length && <p className="muted-note">You have not joined a shared workspace yet. Create one below or open an invitation link.</p>}
            {active && <p className="form-hint"><strong>{active.name}</strong> is your current shared workspace. Documents are submitted through its Submission Requests.</p>}
            {active && <section className="workspace-settings">
                {data.can_manage_members && <>
                    <div className="panel-divider" />
                    <div className="panel-heading"><div><h2>Workspace details</h2><p>Update the name and description shown to members.</p></div></div>
                    <Form method="post" className="form-stack">
                        <input type="hidden" name="_intent" value="manage" />
                        <label htmlFor="edit-workspace-name">Workspace name</label>
                        <input id="edit-workspace-name" name="name" defaultValue={active.name} maxLength={180} required />
                        <label htmlFor="edit-workspace-description">Description <span>Optional</span></label>
                        <textarea id="edit-workspace-description" name="description" defaultValue={active.description || ''} rows={2} maxLength={2000} />
                        <button className="button button-secondary" disabled={busy}>Save workspace details</button>
                    </Form>
                </>}
                <div className="panel-divider" />
                <div className="workspace-danger-zone">
                    <div><strong>Leave this workspace</strong><p>You will lose access to its shared documents and submission requests. You can rejoin with a new invitation.</p></div>
                    <Form method="post" onSubmit={event => { if (!window.confirm('Leave this workspace?')) event.preventDefault(); }}>
                        <input type="hidden" name="_intent" value="leave" />
                        <button className="button button-secondary" disabled={busy}>Leave workspace</button>
                    </Form>
                </div>
                {data.is_workspace_owner && <div className="workspace-danger-zone workspace-delete-zone">
                    <div><strong>Delete this workspace</strong><p>Close the workspace for everyone. Members will lose access and all active invitations will be disabled.</p></div>
                    <Form method="post" onSubmit={event => { if (!window.confirm('Delete this workspace for all members? This action cannot be undone.')) event.preventDefault(); }}>
                        <input type="hidden" name="_intent" value="delete" />
                        <button className="button button-danger" disabled={busy}>Delete workspace</button>
                    </Form>
                </div>}
            </section>}
            {data.can_manage_members && <div className="form-actions"><Link className="button button-primary" to="/app/submission-requests"><Plus size={15} /> Manage submission requests</Link></div>}
        </section>

        <div className="admin-content-grid">
            <section className="panel form-panel">
                <div className="panel-heading">
                    <div><h2><Plus size={17} /> Create a shared workspace</h2><p>Start a shared space for a team, research group, organisation or any collaboration.</p></div>
                </div>
                <Form method="post" className="form-stack">
                    <input type="hidden" name="_intent" value="create" />
                    <label htmlFor="workspace-name">Workspace name</label>
                    <input id="workspace-name" name="name" maxLength={180} required placeholder="e.g. Product Research Team" />
                    <label htmlFor="workspace-description">Description <span>Optional</span></label>
                    <textarea id="workspace-description" name="description" rows={3} maxLength={2000} placeholder="What will this workspace be used for?" />
                    <div className="form-hint">You will become the workspace owner. You can appoint administrators and invite collaborators.</div>
                    <button className="button button-primary" disabled={busy}>{busy ? 'Creating workspace…' : 'Create shared workspace'} <Plus size={15} /></button>
                </Form>
            </section>

            {data.can_manage_members && <>
                <section className="panel form-panel">
                    <div className="panel-heading">
                        <div><h2><Link2 size={17} /> Invite people with a link</h2><p>Anyone with the link can join as a workspace member while it remains active.</p></div>
                    </div>
                    <Form method="post" className="form-stack">
                        <input type="hidden" name="_intent" value="create-invite" />
                        <label htmlFor="invite-expiry">Expiration date and time <span>Optional</span></label>
                        <input id="invite-expiry" name="expires_at" type="datetime-local" />
                        <label htmlFor="invite-max-uses">Maximum number of uses <span>Optional</span></label>
                        <input id="invite-max-uses" name="max_uses" type="number" min="1" max="10000" placeholder="Leave blank for unlimited uses" />
                        <div className="form-hint">Invitation links grant ordinary Member access. Only the workspace owner can appoint administrators. Request reviewers are assigned separately within each Submission Request.</div>
                        <button className="button button-primary" disabled={busy}>{busy ? 'Creating link…' : 'Create invitation link'} <Link2 size={15} /></button>
                    </Form>
                </section>

                <section className="panel">
                    <div className="panel-heading">
                        <div><h2><Clock3 size={17} /> Invitation links</h2><p>{data.invites.length} links created for this workspace.</p></div>
                    </div>
                    {data.invites.length ? <div className="account-list">
                        {data.invites.map(invite => <div className="account-row workspace-invite-row" key={invite.id}>
                            <span className="workspace-invite-icon"><Link2 size={17} /></span>
                            <span className="account-row-copy">
                                <strong>Member invitation</strong>
                                <small>{invite.use_count}{invite.max_uses === null ? ' uses' : ` of ${invite.max_uses} uses`} · Expires: {displayDate(invite.expires_at)}</small>
                            </span>
                            <span className={`category-tag ${invite.status === 'active' ? 'status-active' : ''}`}>{invite.status.replace('_', ' ')}</span>
                            {invite.status === 'active' && <Form method="post">
                                <input type="hidden" name="_intent" value="revoke-invite" />
                                <input type="hidden" name="invite_id" value={invite.id} />
                                <button className="button button-secondary button-small" disabled={busy}><Ban size={14} /> Revoke</button>
                            </Form>}
                        </div>)}
                    </div> : <p className="muted-note">No invitation links have been created yet.</p>}
                </section>

                <section className="panel">
                    <div className="panel-heading">
                        <div><h2><Users size={17} /> Workspace members</h2><p>{data.members.length} active members.</p></div>
                    </div>
                    <div className="account-list">
                        {data.members.map(member => <div className="account-row workspace-member-row" key={member.id}>
                            <span className="avatar">{member.full_name.slice(0, 1).toUpperCase()}</span>
                            <span className="account-row-copy"><strong>{member.full_name}</strong><small>{member.email}</small></span>
                            <span className="category-tag">{formatWorkspaceRole(member.role)}</span>
                            {member.role !== 'owner' && (data.is_workspace_owner || member.role !== 'admin') && <>
                                <Form method="post" className="workspace-member-role-form">
                                    <input type="hidden" name="_intent" value="update-role" />
                                    <input type="hidden" name="user_id" value={member.id} />
                                    <select name="role" aria-label={`Role for ${member.full_name}`} defaultValue={member.role}>
                                        <option value="member">Member</option>
                                        {data.is_workspace_owner && <option value="admin">Administrator</option>}
                                    </select>
                                    <button className="button button-secondary button-small" disabled={busy}>Save</button>
                                </Form>
                                <Form method="post">
                                    <input type="hidden" name="_intent" value="remove-member" />
                                    <input type="hidden" name="user_id" value={member.id} />
                                    <button className="button button-secondary button-small" disabled={busy} title={`Remove ${member.full_name}`} aria-label={`Remove ${member.full_name} from this workspace`}><Ban size={14} aria-hidden="true" /></button>
                                </Form>
                            </>}
                        </div>)}
                    </div>
                    <div className="form-actions"><ShieldCheck size={16} /><span className="form-hint">Only the workspace owner can appoint or remove administrators. Workspace administrators can manage ordinary members.</span></div>
                    <div className="panel-divider" />
                    <div className="panel-heading"><div><h3><UserPlus size={16} /> Add an existing AcaSift user</h3><p>For people who already have an account.</p></div></div>
                    <Form method="post" className="form-stack">
                        <input type="hidden" name="_intent" value="add-member" />
                        <label htmlFor="member-email">Email address</label><input id="member-email" name="email" type="email" required placeholder="person@example.com" />
                        <label htmlFor="member-role">Workspace role</label>
                        <select id="member-role" name="role" defaultValue="member">
                            <option value="member">Member</option>{data.is_workspace_owner && <option value="admin">Administrator</option>}
                        </select>
                        <button className="button button-secondary" disabled={busy}>Add member</button>
                    </Form>
                </section>
            </>}
        </div>
    </>;
}
