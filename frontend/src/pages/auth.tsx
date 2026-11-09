import { Form, Link, useActionData, useNavigation, useSearchParams } from 'react-router-dom';
import type { ReactNode } from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, FileSearch, KeyRound, MailCheck, ShieldCheck, UserPlus } from 'lucide-react';

type AuthActionData = { error?: string; success?: string; email?: string } | undefined;

function AuthShell({ eyebrow, title, description, icon, children }: {
  eyebrow: string;
  title: string;
  description: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return <div className="login-page">
    <div className="login-aside">
      <Link viewTransition to="/" className="login-brand"><span className="brand-mark"><FileSearch size={22} /></span><span>AcaSift<small>Academic similarity analysis</small></span></Link>
      <div className="login-aside-copy"><div className="eyebrow">INDEPENDENT ACADEMIC WORKSPACE</div><h1>Academic review,<br /><span>on your terms.</span></h1><p>A private workspace for document similarity analysis. No institutional affiliation or institutional email address is required.</p><div className="login-assurance"><ShieldCheck size={17} /> Similarity indicators support human review.</div></div>
      <div className="login-aside-bottom">AcaSift · Academic similarity analysis</div>
    </div>
    <div className="login-main"><div className="login-card">
      <Link viewTransition to="/" className="back-home"><ArrowLeft size={15} /> Back to AcaSift</Link>
      <div className="login-icon">{icon}</div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2><p className="login-description">{description}</p>
      {children}
    </div></div>
  </div>;
}

export function RegisterPage() {
  const actionData = useActionData() as AuthActionData;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  return <AuthShell eyebrow="CREATE AN ACCOUNT" title="Your workspace starts here." description="Create an individual account using any valid email address. Verify it to activate your AcaSift workspace." icon={<UserPlus size={22} />}>
    {actionData?.error && <div className="form-error" role="alert">{actionData.error}</div>}
    {actionData?.success ? <div className="auth-success-panel" role="status"><CheckCircle2 size={24} /><strong>Check your inbox</strong><p>{actionData.success}</p><p>We sent a verification email to <strong>{actionData.email}</strong>.</p><Link viewTransition className="button button-primary login-submit" to={`/resend-verification?email=${encodeURIComponent(actionData.email || '')}`}>Resend verification email <ArrowRight size={16} /></Link></div> :
      <Form viewTransition method="post" className="form-stack auth-form">
        <div className="auth-name-grid">
          <div><label htmlFor="first_name">First name</label><input id="first_name" name="first_name" maxLength={80} autoComplete="given-name" required /></div>
          <div><label htmlFor="last_name">Last name</label><input id="last_name" name="last_name" maxLength={80} autoComplete="family-name" required /></div>
        </div>
        <label htmlFor="other_names">Other names <span>Optional</span></label><input id="other_names" name="other_names" maxLength={80} autoComplete="additional-name" />
        <label htmlFor="email">Email address</label><input id="email" name="email" type="email" maxLength={150} autoComplete="email" placeholder="you@example.com" required />
        <label htmlFor="password">Password</label><input id="password" name="password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required />
        <label htmlFor="confirm_password">Confirm password</label><input id="confirm_password" name="confirm_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required />
        <p className="auth-form-hint">Use at least 10 characters. Your account becomes active after you verify your email address.</p>
        <button className="button button-primary login-submit" type="submit" disabled={busy}>{busy ? 'Creating account…' : 'Create account'} <ArrowRight size={16} /></button>
      </Form>}
    <div className="login-footnote">Already have an account? <Link viewTransition to="/login">Sign in</Link>.</div>
  </AuthShell>;
}

export function VerifyEmailPage() {
  const actionData = useActionData() as AuthActionData;
  const navigation = useNavigation();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const busy = navigation.state === 'submitting';
  return <AuthShell eyebrow="EMAIL VERIFICATION" title="Activate your account." description="Confirm that you own the email address used to create your AcaSift account." icon={<MailCheck size={22} />}>
    {actionData?.error && <div className="form-error" role="alert">{actionData.error}</div>}
    {token ? <Form viewTransition method="post" className="form-stack"><input type="hidden" name="token" value={token} /><button className="button button-primary login-submit" type="submit" disabled={busy}>{busy ? 'Verifying…' : 'Verify email address'} <ArrowRight size={16} /></button></Form> : <div className="form-error">This verification link is incomplete. Open the full link from your email or request another verification message.</div>}
    <div className="login-footnote">Need another link? <Link viewTransition to="/resend-verification">Resend verification email</Link>.</div>
    <div className="login-footnote"><Link viewTransition to="/login">Return to sign in</Link></div>
  </AuthShell>;
}

export function ResendVerificationPage() {
  const actionData = useActionData() as AuthActionData;
  const navigation = useNavigation();
  const [params] = useSearchParams();
  const busy = navigation.state === 'submitting';
  return <AuthShell eyebrow="EMAIL VERIFICATION" title="Request another link." description="If your account is awaiting email verification, we will send a new one-time verification link." icon={<MailCheck size={22} />}>
    {actionData?.error && <div className="form-error" role="alert">{actionData.error}</div>}
    {actionData?.success && <div className="auth-success-panel" role="status"><CheckCircle2 size={22} /><p>{actionData.success}</p></div>}
    <Form viewTransition method="post" className="form-stack auth-form">
      <label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" defaultValue={params.get('email') || ''} placeholder="you@example.com" required />
      <button className="button button-primary login-submit" type="submit" disabled={busy}>{busy ? 'Sending…' : 'Request verification email'} <ArrowRight size={16} /></button>
    </Form>
    <div className="login-footnote"><Link viewTransition to="/login">Return to sign in</Link></div>
  </AuthShell>;
}

export function ForgotPasswordPage() {
  const actionData = useActionData() as AuthActionData;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  return <AuthShell eyebrow="ACCOUNT RECOVERY" title="Reset your password." description="Enter the email address associated with your AcaSift account. If an active verified account exists, we will send reset instructions." icon={<KeyRound size={22} />}>
    {actionData?.error && <div className="form-error" role="alert">{actionData.error}</div>}
    {actionData?.success && <div className="auth-success-panel" role="status"><CheckCircle2 size={22} /><p>{actionData.success}</p></div>}
    <Form viewTransition method="post" className="form-stack auth-form">
      <label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" placeholder="you@example.com" required />
      <button className="button button-primary login-submit" type="submit" disabled={busy}>{busy ? 'Sending…' : 'Send reset instructions'} <ArrowRight size={16} /></button>
    </Form>
    <div className="login-footnote"><Link viewTransition to="/login">Return to sign in</Link></div>
  </AuthShell>;
}

export function ResetPasswordPage() {
  const actionData = useActionData() as AuthActionData;
  const navigation = useNavigation();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const busy = navigation.state === 'submitting';
  return <AuthShell eyebrow="ACCOUNT RECOVERY" title="Choose a new password." description="Use a new password that you have not used for this AcaSift account before." icon={<KeyRound size={22} />}>
    {actionData?.error && <div className="form-error" role="alert">{actionData.error}</div>}
    {actionData?.success ? <div className="auth-success-panel" role="status"><CheckCircle2 size={22} /><p>{actionData.success}</p><Link viewTransition className="button button-primary login-submit" to="/login">Continue to sign in <ArrowRight size={16} /></Link></div> : token ?
      <Form viewTransition method="post" className="form-stack auth-form">
        <input type="hidden" name="token" value={token} />
        <label htmlFor="new_password">New password</label><input id="new_password" name="new_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required />
        <label htmlFor="confirm_password">Confirm new password</label><input id="confirm_password" name="confirm_password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required />
        <p className="auth-form-hint">Use at least 10 characters. Reset links are one-time and expire after a short period.</p>
        <button className="button button-primary login-submit" type="submit" disabled={busy}>{busy ? 'Updating password…' : 'Reset password'} <ArrowRight size={16} /></button>
      </Form> : <div className="form-error">This password reset link is incomplete. Request a new password reset email.</div>}
    <div className="login-footnote"><Link viewTransition to="/forgot-password">Request another reset link</Link></div>
  </AuthShell>;
}
