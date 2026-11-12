import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import {
    Activity, ArrowRight, Camera, CheckCircle2, FileText,
    ImagePlus, LockKeyhole, Mail, ShieldCheck, Trash2, UserRound, KeyRound,
} from 'lucide-react';
import { Notice, PageHeading, StatusPill, formatDate, formatDateTime } from '../components/ui';
import type { AccountData } from '../types';

interface AccountActionData {
    intent?: string;
    error?: string;
    success?: string;
    pendingEmail?: string;
}

export function AccountPage() {
    const data = useLoaderData() as AccountData;
    const actionData = useActionData() as AccountActionData | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const user = data.user;
    const profileComplete = Boolean(user.first_name && user.last_name);
    const pendingEmail = actionData?.pendingEmail || data.pending_email;

    return <>
        <PageHeading
            eyebrow="ACCOUNT & PREFERENCES"
            title="My account"
            description="Manage your profile, email address, sign-in security and recent activity."
        />

        <section className="account-hero panel" aria-label="Account summary">
            {user.profile_image_url ? (
                <img className="account-avatar-large account-avatar-photo" src={user.profile_image_url} alt={`${user.full_name}'s profile`} />
            ) : (
                <div className="account-avatar-large" aria-hidden="true">{(user.first_name?.[0] || user.full_name[0] || 'A').toUpperCase()}</div>
            )}
            <div className="account-hero-copy">
                <span className="eyebrow">{user.is_admin ? 'PLATFORM ADMINISTRATOR ACCOUNT' : 'INDIVIDUAL ACCOUNT'}</span>
                <h2>{user.full_name}</h2>
                <p>{user.email}</p>
                <div className="account-hero-tags">
                    <span className={`category-tag ${user.is_active ? 'account-active' : 'account-inactive'}`}>{user.is_active ? 'Active account' : 'Inactive account'}</span>
                    <span className="category-tag">{user.is_admin ? 'Platform administrator' : 'Individual account'}</span>
                </div>
            </div>
            <div className="account-hero-meta"><span>Member since</span><strong>{user.created_at ? formatDate(user.created_at) : 'Date unavailable'}</strong></div>
        </section>

        {!profileComplete && <Notice tone="info">Your account was created before AcaSift introduced separate name fields. Please confirm your first name and last name below.</Notice>}

        <div className="account-layout-grid">
            <div className="account-main-column">
                <section className="panel account-panel">
                    <div className="panel-heading">
                        <div><h2><Camera size={18} aria-hidden="true" /> Profile picture</h2><p>Add a picture so your account is easier to recognise.</p></div>
                    </div>
                    {actionData?.intent === 'profile-picture' && actionData.error && <Notice tone="danger">{actionData.error}</Notice>}
                    {actionData?.intent === 'profile-picture' && actionData.success && <Notice tone="success">{actionData.success}</Notice>}
                    {actionData?.intent === 'remove-picture' && actionData.error && <Notice tone="danger">{actionData.error}</Notice>}
                    {actionData?.intent === 'remove-picture' && actionData.success && <Notice tone="success">{actionData.success}</Notice>}
                    <div className="profile-picture-editor">
                        {user.profile_image_url ? (
                            <img className="profile-picture-preview" src={user.profile_image_url} alt="Current profile picture" />
                        ) : (
                            <div className="profile-picture-placeholder" aria-hidden="true"><UserRound size={30} /></div>
                        )}
                        <div className="profile-picture-controls">
                            <Form method="post" encType="multipart/form-data" className="form-stack profile-picture-form">
                                <input type="hidden" name="_intent" value="profile-picture" />
                                <label htmlFor="profile-picture-file">Choose a picture</label>
                                <input
                                    id="profile-picture-file"
                                    name="image"
                                    type="file"
                                    accept="image/jpeg,image/png,image/webp"
                                    aria-describedby="profile-picture-help"
                                    required
                                />
                                <p className="form-hint" id="profile-picture-help">JPEG, PNG or WebP. Maximum file size: 5 MB. Your picture is resized automatically.</p>
                                <button className="button button-primary" type="submit" disabled={busy}>
                                    <ImagePlus size={16} aria-hidden="true" /> {busy ? 'Uploading picture…' : user.profile_image_url ? 'Change profile picture' : 'Upload profile picture'}
                                </button>
                            </Form>
                            {user.profile_image_url && <Form method="post" className="profile-picture-remove-form">
                                <input type="hidden" name="_intent" value="remove-picture" />
                                <button className="button button-secondary" type="submit" disabled={busy}>
                                    <Trash2 size={15} aria-hidden="true" /> Remove picture
                                </button>
                            </Form>}
                        </div>
                    </div>
                </section>

                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><UserRound size={18} aria-hidden="true" /> Personal information</h2><p>Keep your name details accurate and up to date.</p></div></div>
                    {actionData?.intent === 'profile' && actionData.error && <Notice tone="danger">{actionData.error}</Notice>}
                    {actionData?.intent === 'profile' && actionData.success && <Notice tone="success">{actionData.success}</Notice>}
                    <Form method="post" className="form-stack account-form">
                        <input type="hidden" name="_intent" value="profile" />
                        <div className="account-name-grid">
                            <div><label htmlFor="account-first-name">First name</label><input id="account-first-name" name="first_name" defaultValue={user.first_name || ''} maxLength={80} autoComplete="given-name" required /></div>
                            <div><label htmlFor="account-last-name">Last name</label><input id="account-last-name" name="last_name" defaultValue={user.last_name || ''} maxLength={80} autoComplete="family-name" required /></div>
                            <div className="account-other-names"><label htmlFor="account-other-names">Other names <span>Optional</span></label><input id="account-other-names" name="other_names" defaultValue={user.other_names || ''} maxLength={80} autoComplete="additional-name" /></div>
                        </div>
                        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save personal information'} <CheckCircle2 size={16} aria-hidden="true" /></button></div>
                    </Form>
                </section>

                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><Mail size={18} aria-hidden="true" /> Email address</h2><p>Change the email address used to sign in and receive account messages.</p></div></div>
                    {actionData?.intent === 'email-change' && actionData.error && <Notice tone="danger">{actionData.error}</Notice>}
                    {actionData?.intent === 'email-change' && actionData.success && <Notice tone="success">{actionData.success}</Notice>}
                    <div className="account-readonly-field">
                        <Mail size={17} aria-hidden="true" />
                        <div>
                            <span>Current email address</span>
                            <strong>{user.email}</strong>
                            <small>{user.email_verified ? 'Verified email address' : 'Email address not verified'}</small>
                        </div>
                    </div>
                    {pendingEmail && <Notice tone="info">A change is waiting for confirmation at <strong>{pendingEmail}</strong>. Your current email address remains active until the new address is confirmed. If the message does not arrive, submit the request again to send a fresh confirmation link.</Notice>}
                    <Form method="post" className="form-stack account-form email-change-form">
                        <input type="hidden" name="_intent" value="email-change" />
                        <label htmlFor="new-email-address">New email address</label>
                        <input id="new-email-address" name="new_email" type="email" autoComplete="email" maxLength={150} placeholder="name@example.com" required />
                        <label htmlFor="email-current-password">Confirm your current password</label>
                        <input id="email-current-password" name="email_current_password" type="password" autoComplete="current-password" required />
                        <p className="form-hint">We will send a confirmation link to the new address. Your sign-in email will only change after you confirm it.</p>
                        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Sending confirmation…' : 'Request email change'} <ArrowRight size={16} aria-hidden="true" /></button></div>
                    </Form>
                </section>

                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><LockKeyhole size={18} aria-hidden="true" /> Password & security</h2><p>Change your password using your current credentials.</p></div></div>
                    {actionData?.intent === 'password' && actionData.success && <Notice tone="success">{actionData.success}</Notice>}
                    {actionData?.intent === 'password' && actionData.error && <Notice tone="danger">{actionData.error}</Notice>}
                    <Form method="post" className="form-stack account-form" key={actionData?.intent === 'password' ? 'password-result' : 'password-entry'}>
                        <input type="hidden" name="_intent" value="password" />
                        <label htmlFor="current-password">Current password</label><input id="current-password" name="current_password" type="password" autoComplete="current-password" required />
                        <div className="account-name-grid">
                            <div><label htmlFor="new-password">New password</label><input id="new-password" name="new_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required /></div>
                            <div><label htmlFor="confirm-password">Confirm new password</label><input id="confirm-password" name="confirm_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required /></div>
                        </div>
                        <div className="form-hint">Use at least 10 characters. Choose a unique password that you do not use on another site.</div>
                        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Updating password…' : 'Change password'} <KeyRound size={16} aria-hidden="true" /></button></div>
                    </Form>
                </section>
            </div>

            <aside className="account-side-column" aria-label="Account information and activity">
                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><ShieldCheck size={18} aria-hidden="true" /> Account details</h2><p>Information about your access.</p></div></div>
                    <div className="account-detail-list">
                        <div><span>Account role</span><strong>{user.is_admin ? 'Platform administrator' : 'Individual account'}</strong></div>
                        <div><span>Account status</span><strong>{user.is_active ? 'Active' : 'Inactive'}</strong></div>
                        <div><span>Email verification</span><strong>{user.email_verified ? 'Verified' : 'Not verified'}</strong></div>
                        <div><span>Account ID</span><strong>#{user.id}</strong></div>
                        <div><span>Created</span><strong>{user.created_at ? formatDateTime(user.created_at) : 'Unavailable'}</strong></div>
                    </div>
                    <p className="account-security-note"><ShieldCheck size={16} aria-hidden="true" /> Your role and account status are managed by an authorised administrator and cannot be changed from this page.</p>
                </section>

                <section className="panel account-panel">
                    <div className="panel-heading"><div><h2><Activity size={18} aria-hidden="true" /> Submission activity</h2><p>Your recent document submissions.</p></div></div>
                    <div className="account-activity-stats">
                        <div><FileText size={18} aria-hidden="true" /><strong>{data.activity.submission_count}</strong><span>Submissions</span></div>
                    </div>
                    <div className="account-activity-list">
                        <h3>Recent submissions</h3>
                        {data.activity.recent_submissions.length ? data.activity.recent_submissions.map(item => <div className="account-activity-item" key={item.id}><span><strong>{item.title}</strong><small>{item.original_filename} · {formatDate(item.uploaded_at)}</small></span><StatusPill value={item.processing_status} /></div>) : <p className="account-empty">No submissions yet.</p>}
                    </div>
                </section>
            </aside>
        </div>
    </>;
}

