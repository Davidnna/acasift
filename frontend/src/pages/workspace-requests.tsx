import { Form, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { Building2, CheckCircle2, XCircle } from 'lucide-react';
import { Notice, PageHeading, formatDateTime } from '../components/ui';
import type { WorkspaceRequestRecord } from '../types';

export function WorkspaceRequestsPage() {
  const requests = useLoaderData() as WorkspaceRequestRecord[];
  const actionData = useActionData() as { error?: string; success?: string } | undefined;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  return <>
    <PageHeading eyebrow="PLATFORM ADMINISTRATION" title="Workspace requests" description="Review requests for organisational AcaSift workspaces." />
    {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
    {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
    <section className="panel"><div className="panel-heading"><div><h2><Building2 size={17}/> Organisational workspace requests</h2><p>{requests.filter(item => item.status === 'pending').length} awaiting review · {requests.length} total</p></div></div>
      {!requests.length ? <p className="muted-note">There are no workspace requests yet.</p> : <div className="workspace-request-list">{requests.map(item => <article className="workspace-request-card" key={item.id}>
        <div className="workspace-request-head"><div><h3>{item.organization_name}</h3><p>{item.organization_type.replace('_',' ')} · Requested by {item.requester} ({item.requester_email})</p></div><span className={`category-tag status-${item.status}`}>{item.status}</span></div>
        {item.website && <p><a href={item.website} target="_blank" rel="noreferrer">{item.website}</a></p>}<p>{item.reason}</p><small className="muted-note">Submitted {formatDateTime(item.created_at)}</small>
        {item.status === 'pending' && <div className="form-actions"><Form method="post"><input type="hidden" name="request_id" value={item.id}/><input type="hidden" name="decision" value="approve"/><button className="button button-primary" disabled={busy}><CheckCircle2 size={15}/> Approve workspace</button></Form><Form method="post"><input type="hidden" name="request_id" value={item.id}/><input type="hidden" name="decision" value="reject"/><button className="button button-secondary" disabled={busy}><XCircle size={15}/> Reject</button></Form></div>}
        {item.review_notes && <p className="form-hint">Review note: {item.review_notes}</p>}
      </article>)}</div>}
    </section>
  </>;
}
