import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { ArrowRight, FileSearch, ShieldCheck, Users } from 'lucide-react';
import { Notice, PageHeading } from '../components/ui';
import type { WorkspaceInvitePreviewData } from '../types';

function formatExpiry(value: string | null) {
  return value ? new Date(value).toLocaleString() : 'This invitation does not have an expiration date.';
}

export function WorkspaceInvitePage() {
  const data = useLoaderData() as WorkspaceInvitePreviewData;
  const actionData = useActionData() as { error?: string } | undefined;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  const token = new URLSearchParams(window.location.search).get('token') || '';

  return <div className="login-page">
    <div className="login-aside">
      <Link viewTransition to="/" className="login-brand"><span className="brand-mark"><FileSearch size={22}/></span><span>AcaSift<small>Academic similarity analysis</small></span></Link>
      <div className="login-aside-copy"><div className="eyebrow">SHARED WORKSPACE</div><h1>Work together.<br/><span>Review with clarity.</span></h1><p>Join a shared space for a class, project, research group or team.</p><div className="login-assurance"><ShieldCheck size={17}/> Access is controlled by workspace roles.</div></div>
      <div className="login-aside-bottom">AcaSift · Academic similarity analysis</div>
    </div>
    <div className="login-main">
      <div className="login-card">
      <PageHeading eyebrow="WORKSPACE INVITATION" title="Join a shared workspace" description="You have been invited to collaborate on AcaSift." />
      {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
      <div className="panel workspace-invite-preview">
        <div className="workspace-invite-preview-icon"><Users size={24}/></div>
        <h2>{data.workspace.name}</h2>
        {data.workspace.description && <p>{data.workspace.description}</p>}
        <div className="academic-fact-list">
          <div><span>Invited by</span><strong>{data.invited_by}</strong></div>
          <div><span>Your workspace role</span><strong>{data.role.charAt(0).toUpperCase() + data.role.slice(1)}</strong></div>
          {data.course && <div><span>Course enrolment</span><strong>{data.course.code} — {data.course.title}</strong></div>}
          <div><span>Invitation expires</span><strong>{formatExpiry(data.expires_at)}</strong></div>
        </div>
        {data.is_member && <Notice tone="info">{data.course && !data.is_course_member
          ? `You already belong to this workspace. Accepting this invitation will also enrol you in ${data.course.code}.`
          : 'You are already a member of this workspace. Continue to open it.'}</Notice>}
        <Form method="post">
          <input type="hidden" name="token" value={token}/>
          <button className="button button-primary button-block" disabled={busy}>{busy ? 'Processing invitation…' : data.is_member ? (data.course && !data.is_course_member ? 'Join course and open workspace' : 'Open this workspace') : 'Accept invitation and join'} <ArrowRight size={15}/></button>
        </Form>
        <p className="form-hint"><ShieldCheck size={14}/> Your access is limited to the role shown above. Workspace administrators control membership and permissions.</p>
      </div>
      </div>
    </div>
  </div>;
}
