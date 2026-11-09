import { Form, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { ArrowRight, BookOpen, Users } from 'lucide-react';
import { EmptyState, Notice, PageHeading } from '../components/ui';
import { DocumentTable } from '../components/document-table';
import type { DocumentRecord, User } from '../types';

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
    const documents = useLoaderData() as DocumentRecord[];
    const actionData = useActionData() as { error?: string; success?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow="ADMINISTRATION" title="Reference repository" description="Manage and add the documents used as comparison sources." />
        <section className="panel form-panel">
            <div className="panel-heading"><div><h2>Add a reference document</h2><p>Upload a source document to the comparison repository.</p></div><span className="panel-icon"><BookOpen size={18} /></span></div>
            {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
            {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
            <Form method="post" encType="multipart/form-data" className="form-stack">
                <label htmlFor="reference-title">Document title <span>Optional</span></label>
                <input id="reference-title" name="title" maxLength={255} placeholder="e.g. Department research handbook" />
                <label htmlFor="reference-file">Select reference document</label>
                <input id="reference-file" name="document" type="file" accept=".pdf,.docx,.txt" required />
                <div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div>
                <button className="button button-primary" disabled={busy}>{busy ? 'Adding document…' : 'Add to repository'} <ArrowRight size={15} /></button>
            </Form>
        </section>
        <section className="panel">
            <div className="panel-heading"><div><h2>Available reference documents</h2><p>{documents.length} reference documents</p></div></div>
            {documents.length ? <DocumentTable documents={documents} /> : <EmptyState title="The repository is empty" description="Add reference documents so submissions can be compared against them." />}
        </section>
        <Notice tone="info">Only administrator-curated reference documents are used as comparison sources. Users' private submissions are not automatically added to the repository.</Notice>
    </>;
}
