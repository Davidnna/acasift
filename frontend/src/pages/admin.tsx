import { Form, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { Archive, ArrowRight, BookOpen, CheckCircle2, ShieldCheck, Users } from 'lucide-react';
import { EmptyState, Notice, PageHeading, StatusPill } from '../components/ui';
import type { ReferenceEntryRecord, User } from '../types';

export function AdminUsersPage() {
    const users = useLoaderData() as User[];
    const actionData = useActionData() as { error?: string; success?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow="ADMINISTRATION" title="Manage users" description="Create accounts and assign application roles." />
        <div className="admin-content-grid"><section className="panel form-panel"><div className="panel-heading"><div><h2>Create account</h2><p>Provide account details to a new user.</p></div><span className="panel-icon"><Users size={18} /></span></div>
            {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}{actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
            <Form viewTransition method="post" className="form-stack"><label htmlFor="first_name">First name</label><input id="first_name" name="first_name" required maxLength={80} autoComplete="given-name" /><label htmlFor="last_name">Last name</label><input id="last_name" name="last_name" required maxLength={80} autoComplete="family-name" /><label htmlFor="other_names">Other names <span>Optional</span></label><input id="other_names" name="other_names" maxLength={80} autoComplete="additional-name" /><label htmlFor="email">Email address</label><input id="email" type="email" name="email" required maxLength={150} autoComplete="email" /><label htmlFor="password">Initial password</label><input id="password" type="password" name="password" required minLength={10} autoComplete="new-password" /><div className="form-hint">Share this password securely. Users can change it from My account after signing in.</div><label htmlFor="role">Role</label><select id="role" name="role"><option value="user">Registered user</option><option value="admin">Administrator</option></select><button className="button button-primary" disabled={busy}>{busy ? 'Creating account…' : 'Create account'} <ArrowRight size={15} /></button></Form>
        </section><section className="panel"><div className="panel-heading"><div><h2>Existing accounts</h2><p>{users.length} registered accounts</p></div></div><div className="account-list">{users.map(user => <div className="account-row" key={user.id}><span className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</span><span className="account-row-copy"><strong>{user.full_name}</strong><small>{user.email}</small></span><span className="category-tag">{user.role === 'admin' ? 'Administrator' : 'User'}</span></div>)}</div></section></div>
    </>;
}

export function AdminReferencesPage() {
    const entries = useLoaderData() as ReferenceEntryRecord[];
    const actionData = useActionData() as { error?: string; success?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow="ADMINISTRATION" title="Global reference collection" description="Manage source documents that have a recorded basis for use in comparisons across AcaSift." />
        {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
        {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
        <section className="panel form-panel">
            <div className="panel-heading"><div><h2><BookOpen size={18} /> Add a global reference</h2><p>Record the source and the permission basis before making a document available platform-wide.</p></div><span className="panel-icon"><ShieldCheck size={18} /></span></div>
            <Form method="post" encType="multipart/form-data" className="form-stack">
                <input type="hidden" name="_intent" value="upload" />
                <label htmlFor="reference-title">Document title <span>Optional</span></label>
                <input id="reference-title" name="title" maxLength={255} placeholder="Publication or document title" />
                <label htmlFor="reference-source-url">Original source URL <span>Optional</span></label>
                <input id="reference-source-url" name="source_url" type="url" maxLength={1000} placeholder="https://repository.example.org/document" />
                <label htmlFor="reference-doi">DOI <span>Optional</span></label>
                <input id="reference-doi" name="doi" maxLength={255} placeholder="10.xxxx/example" />
                <label htmlFor="rights-basis">Permission basis</label>
                <select id="rights-basis" name="rights_basis" required defaultValue="">
                    <option value="" disabled>Select the basis for global use</option>
                    <option value="open_license">Open licence permitting this use</option>
                    <option value="public_domain">Public domain</option>
                    <option value="author_permission">Author or rights-holder permission</option>
                    <option value="publisher_agreement">Publisher or repository agreement</option>
                    <option value="owned_content">AcaSift-owned or commissioned content</option>
                    <option value="other_authorization">Other documented authorisation</option>
                </select>
                <div className="form-grid-two">
                    <div className="form-stack">
                        <label htmlFor="license-name">Licence name <span>Where applicable</span></label>
                        <input id="license-name" name="license_name" maxLength={160} placeholder="e.g. CC BY 4.0" />
                    </div>
                    <div className="form-stack">
                        <label htmlFor="license-url">Official licence URL <span>Where applicable</span></label>
                        <input id="license-url" name="license_url" type="url" maxLength={1000} placeholder="https://creativecommons.org/licenses/by/4.0/" />
                    </div>
                </div>
                <label htmlFor="rights-notes">Permission notes <span>Required when no source URL is provided for permission-based use</span></label>
                <textarea id="rights-notes" name="rights_notes" rows={3} maxLength={2000} placeholder="Record the permission, agreement or other relevant details." />
                <label htmlFor="reference-file">Select reference document</label>
                <input id="reference-file" name="document" type="file" accept=".pdf,.docx,.txt" required />
                <div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div>
                <label className="checkbox-row"><input type="checkbox" name="rights_confirmed" value="yes" required /><span>I confirm that AcaSift has the necessary rights to retain and use this document for global similarity comparisons.</span></label>
                <button className="button button-primary" disabled={busy}>{busy ? 'Adding reference…' : 'Add verified global reference'} <ArrowRight size={15} /></button>
            </Form>
        </section>
        <section className="panel">
            <div className="panel-heading"><div><h2>Global reference records</h2><p>{entries.length} reference records, including records awaiting rights review</p></div></div>
            {entries.length ? <div className="reference-entry-list">{entries.map(entry => <article className="reference-entry-card" key={entry.id}>
                <div className="reference-entry-main">
                    <div className="reference-entry-icon"><BookOpen size={19} /></div>
                    <div className="reference-entry-copy">
                        <strong>{entry.document.title}</strong>
                        <span>{entry.document.original_filename}</span>
                        <small>{entry.provenance_type.replace(/_/g, ' ')} · {entry.rights_basis?.replace(/_/g, ' ') || 'No permission basis recorded'}</small>
                        {entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer">Original source</a>}
                        {entry.license_name && <small>{entry.license_name}{entry.license_url ? ` · ${entry.license_url}` : ''}</small>}
                        {entry.rights_notes && <small>Permission notes: {entry.rights_notes}</small>}
                    </div>
                    <StatusPill value={entry.status} />
                </div>
                {entry.status === 'review_required' && <div className="reference-review-box">
                    <Notice tone="warning">This legacy document is excluded from comparisons until its global-use permission is recorded.</Notice>
                    <Form method="post" className="form-stack compact-form">
                        <input type="hidden" name="_intent" value="verify" />
                        <input type="hidden" name="entry_id" value={entry.id} />
                        <label>Permission basis</label>
                        <select name="rights_basis" required defaultValue=""><option value="" disabled>Select permission basis</option><option value="open_license">Open licence</option><option value="public_domain">Public domain</option><option value="author_permission">Author permission</option><option value="publisher_agreement">Publisher agreement</option><option value="owned_content">AcaSift-owned content</option><option value="other_authorization">Other authorisation</option></select>
                        <label>Licence name <span>Where applicable</span></label><input name="license_name" maxLength={160} />
                        <label>Official licence URL <span>Where applicable</span></label><input name="license_url" type="url" maxLength={1000} />
                        <label>Original source URL <span>Optional</span></label><input name="source_url" type="url" maxLength={1000} />
                        <label>Permission notes <span>Required when no source URL is provided for permission-based use</span></label><textarea name="rights_notes" rows={2} maxLength={2000} />
                        <label className="checkbox-row"><input type="checkbox" name="rights_confirmed" value="yes" required /><span>I confirm that the stated permission permits AcaSift's global retention and similarity-check use.</span></label>
                        <button className="button button-secondary" type="submit"><ShieldCheck size={15} /> Record permission</button>
                    </Form>
                </div>}
                {entry.status === 'active' && <div className="reference-entry-meta"><CheckCircle2 size={13} /> Rights basis recorded{entry.verified_at ? ` · verified ${new Date(entry.verified_at).toLocaleDateString()}` : ''}</div>}
                {entry.status !== 'archived' && <div className="reference-entry-actions"><Form method="post"><input type="hidden" name="_intent" value="archive" /><input type="hidden" name="entry_id" value={entry.id} /><button className="button button-quiet" type="submit"><Archive size={15} /> Remove from global comparisons</button></Form></div>}
            </article>)}</div> : <EmptyState title="The global collection is empty" description="Add legitimate reference documents with their source and permission information." />}
        </section>
        <Notice tone="info">Documents awaiting rights review are retained for administrative review but are not used in global similarity comparisons. Public availability alone does not establish permission to reuse a document.</Notice>
    </>;
}
