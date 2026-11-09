import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import {
    Activity, CheckCircle2, FileSearch, FileText,
    LockKeyhole, Mail, ShieldCheck, UserRound, KeyRound,
} from 'lucide-react';
import { Notice, PageHeading, StatusPill, formatDate, formatDateTime } from '../components/ui';
import type { AccountData } from '../types';

interface AccountActionData {
    intent?: string;
    error?: string;
    success?: string;
}

export function AccountPage() {
    const data = useLoaderData() as AccountData;
    const actionData = useActionData() as AccountActionData | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const user = data.user;
    const profileSaved = actionData?.intent === 'profile';
    const passwordSaved = actionData?.intent === 'password';
    const profileComplete = Boolean(user.first_name && user.last_name);

    return <>
        <PageHeading eyebrow="ACCOUNT & PREFERENCES" title="My account" description="Manage your personal information, sign-in security and review your AcaSift activity." />

        <section className="account-hero panel">
            <div className="account-avatar-large">{(user.first_name?.[0] || user.full_name[0] || 'A').toUpperCase()}</div>
            <div className="account-hero-copy">
                <span className="eyebrow">{user.is_admin ? 'PLATFORM ADMINISTRATOR ACCOUNT' : 'INDIVIDUAL ACCOUNT'}</span>
                <h2>{user.full_name}</h2>
                <p>{user.email}</p>
                <div className="account-hero-tags"><span className={`category-tag ${user.is_active ? 'account-active' : 'account-inactive'}`}>{user.is_active ? 'Active account' : 'Inactive account'}</span><span className="category-tag">{user.is_admin ? 'Platform administrator' : 'Individual account'}</span></div>
            </div>
            <div className="account-hero-meta"><span>Member since</span><strong>{user.created_at ? formatDate(user.created_at) : 'Date unavailable'}</strong></div>
        </section>

        {!profileComplete && <Notice tone="info">Your account was created before AcaSift introduced separate name fields. Please confirm your first name and last name below. Your existing display name will remain unchanged until you save the updated details.</Notice>}

        <div className="account-layout-grid">
            <div className="account-main-column">
                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><UserRound size={17} /> Personal information</h2><p>Keep your name details accurate and up to date.</p></div></div>
                    {profileSaved && actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
                    {profileSaved && actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
                    <Form method="post" className="form-stack account-form">
                        <input type="hidden" name="_intent" value="profile" />
                        <div className="account-name-grid">
                            <div><label htmlFor="account-first-name">First name</label><input id="account-first-name" name="first_name" defaultValue={user.first_name || ''} maxLength={80} autoComplete="given-name" required /></div>
                            <div><label htmlFor="account-last-name">Last name</label><input id="account-last-name" name="last_name" defaultValue={user.last_name || ''} maxLength={80} autoComplete="family-name" required /></div>
                            <div className="account-other-names"><label htmlFor="account-other-names">Other names <span>Optional</span></label><input id="account-other-names" name="other_names" defaultValue={user.other_names || ''} maxLength={80} autoComplete="additional-name" /></div>
                        </div>
                        <div className="account-readonly-field"><Mail size={16} /><div><span>Email address</span><strong>{user.email}</strong><small>{user.email_verified ? 'This email address has been verified. Email changes require a separate verification-protected update.' : 'This email address has not yet been verified.'}</small></div></div>
                        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save personal information'} <CheckCircle2 size={15} /></button></div>
                    </Form>
                </section>

                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><LockKeyhole size={17} /> Password & security</h2><p>Change your password using your current credentials.</p></div></div>
                    {passwordSaved && actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
                    {passwordSaved && actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
                    <Form method="post" className="form-stack account-form" key={passwordSaved ? 'password-result' : 'password-entry'}>
                        <input type="hidden" name="_intent" value="password" />
                        <label htmlFor="current-password">Current password</label><input id="current-password" name="current_password" type="password" autoComplete="current-password" required />
                        <div className="account-name-grid">
                            <div><label htmlFor="new-password">New password</label><input id="new-password" name="new_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required /></div>
                            <div><label htmlFor="confirm-password">Confirm new password</label><input id="confirm-password" name="confirm_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required /></div>
                        </div>
                        <div className="form-hint">Use at least 10 characters. Choose a unique password that you do not use on another site.</div>
                        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Updating password…' : 'Change password'} <KeyRound size={15} /></button></div>
                    </Form>
                </section>
            </div>

            <aside className="account-side-column">
                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><ShieldCheck size={17} /> Account details</h2><p>Information about your access.</p></div></div>
                    <div className="account-detail-list">
                        <div><span>Account role</span><strong>{user.is_admin ? 'Platform administrator' : 'Individual account'}</strong></div>
                        <div><span>Account status</span><strong>{user.is_active ? 'Active' : 'Inactive'}</strong></div>
                        <div><span>Email verification</span><strong>{user.email_verified ? 'Verified' : 'Not verified'}</strong></div>
                        <div><span>Account ID</span><strong>#{user.id}</strong></div>
                        <div><span>Created</span><strong>{user.created_at ? formatDateTime(user.created_at) : 'Unavailable'}</strong></div>
                    </div>
                    <p className="account-security-note"><ShieldCheck size={15} /> Your role and account status are managed by an authorised administrator and cannot be changed from this page.</p>
                </section>

                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><Activity size={17} /> Your activity</h2><p>Recent work in AcaSift.</p></div></div>
                    <div className="account-activity-stats"><div><FileText size={17} /><strong>{data.activity.document_count}</strong><span>Documents</span></div><div><FileSearch size={17} /><strong>{data.activity.comparison_count}</strong><span>Comparisons</span></div></div>
                    <div className="account-activity-list">
                        <h3>Recent comparisons</h3>
                        {data.activity.recent_comparisons.length ? data.activity.recent_comparisons.map(item => <Link to={`/app/comparisons/${item.id}`} className="account-activity-item" key={item.id}><span><strong>{item.submitted_document.title}</strong><small>{formatDate(item.started_at)}</small></span><StatusPill value={item.status} /></Link>) : <p className="account-empty">No comparisons yet.</p>}
                        <h3>Recent documents</h3>
                        {data.activity.recent_documents.length ? data.activity.recent_documents.map(item => <div className="account-activity-item" key={item.id}><span><strong>{item.title}</strong><small>{item.original_filename} · {formatDate(item.uploaded_at)}</small></span><StatusPill value={item.processing_status} /></div>) : <p className="account-empty">No documents uploaded yet.</p>}
                    </div>
                </section>
            </aside>
        </div>
    </>;
}
