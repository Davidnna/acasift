import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { Building2, Layers3, Users, BookOpen } from 'lucide-react';
import { Notice, PageHeading } from '../components/ui';
import type { WorkspaceData } from '../types';

export function WorkspacesPage() {
  const data = useLoaderData() as WorkspaceData;
  const actionData = useActionData() as { error?: string; success?: string } | undefined;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  const active = data.workspaces.find(item => item.id === data.active_workspace_id);
  return <>
    <PageHeading eyebrow="WORKSPACE MANAGEMENT" title="Your workspaces" description="Keep individual work private and collaborate through approved organisational workspaces." />
    {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
    {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
    <section className="panel">
      <div className="panel-heading"><div><h2><Layers3 size={17}/> Available workspaces</h2><p>Choose where new documents and comparisons should be stored.</p></div></div>
      <div className="workspace-card-list">
        {data.workspaces.map(workspace => <div className={`workspace-choice ${workspace.id === data.active_workspace_id ? 'workspace-choice-active' : ''}`} key={workspace.id}>
          <div className="workspace-choice-icon">{workspace.type === 'organization' ? <Building2 size={19}/> : <Layers3 size={19}/>}</div>
          <div className="workspace-choice-copy"><strong>{workspace.name}</strong><span>{workspace.type === 'personal' ? 'Private individual workspace' : 'Approved organisational workspace'} · {workspace.role}</span></div>
          {workspace.id === data.active_workspace_id ? <span className="category-tag">Current workspace</span> : <Form method="post"><input type="hidden" name="_intent" value="switch"/><input type="hidden" name="workspace_id" value={workspace.id}/><button className="button button-secondary button-small" disabled={busy}>Switch workspace</button></Form>}
        </div>)}
      </div>
      {active && <p className="form-hint">New submissions will be associated with <strong>{active.name}</strong>.</p>}
      {data.can_manage_members && <div className="form-actions"><Link className="button button-secondary" to="/app/references/new"><BookOpen size={15}/> Add workspace reference</Link></div>}
    </section>
    <div className="admin-content-grid">
      <section className="panel form-panel">
        <div className="panel-heading"><div><h2><Building2 size={17}/> Request an organisational workspace</h2><p>For a university, school, research group, company or other organisation.</p></div></div>
        {data.pending_request ? <Notice tone="info">Your request for <strong>{data.pending_request.organization_name}</strong> is awaiting review. You can submit another request after it has been reviewed.</Notice> : <Form method="post" className="form-stack">
          <input type="hidden" name="_intent" value="request"/>
          <label htmlFor="organization_name">Organisation name</label><input id="organization_name" name="organization_name" maxLength={180} required/>
          <label htmlFor="organization_type">Organisation type</label><select id="organization_type" name="organization_type"><option value="university">University</option><option value="college">College</option><option value="school">School</option><option value="research_group">Research group</option><option value="company">Company</option><option value="other">Other</option></select>
          <label htmlFor="website">Official website <span>Optional</span></label><input id="website" name="website" type="url" placeholder="https://example.org"/>
          <label htmlFor="reason">How will the organisation use AcaSift?</label><textarea id="reason" name="reason" minLength={20} maxLength={2000} rows={4} required/>
          <div className="form-hint">Requests are reviewed before an organisational workspace is activated.</div>
          <button className="button button-primary" disabled={busy}>{busy ? 'Submitting…' : 'Submit workspace request'}</button>
        </Form>}
      </section>
      {data.can_manage_members && active?.type === 'organization' && <section className="panel form-panel">
        <div className="panel-heading"><div><h2><Users size={17}/> Workspace members</h2><p>{data.members.length} active members.</p></div></div>
        <div className="account-list">{data.members.map(member => <div className="account-row" key={member.id}><span className="avatar">{member.full_name.slice(0,1)}</span><span className="account-row-copy"><strong>{member.full_name}</strong><small>{member.email}</small></span><span className="category-tag">{member.role}</span></div>)}</div>
        <Form method="post" className="form-stack"><input type="hidden" name="_intent" value="add-member"/><label htmlFor="member_email">Existing AcaSift account email</label><input id="member_email" name="email" type="email" required/><label htmlFor="member_role">Workspace role</label><select id="member_role" name="role"><option value="student">Student</option><option value="lecturer">Lecturer</option><option value="member">Member</option><option value="admin">Workspace administrator</option></select><button className="button button-secondary" disabled={busy}>Add member</button></Form>
      </section>}
    </div>
  </>;
}
