import { Form, Link, useActionData, useNavigation, useSearchParams } from 'react-router-dom';
import { ArrowLeft, ArrowRight, FileSearch, LockKeyhole, ShieldCheck } from 'lucide-react';

export function LoginPage() {
    const actionData = useActionData() as { error?: string; } | undefined;
    const [searchParams] = useSearchParams();
    const next = searchParams.get('next');
    const safeNext = next && next.startsWith('/') && !next.startsWith('//') ? next : null;
    const registerPath = safeNext ? `/register?next=${encodeURIComponent(safeNext)}` : '/register';
    const resendPath = safeNext ? `/resend-verification?next=${encodeURIComponent(safeNext)}` : '/resend-verification';
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <div className="login-page">
        <div className="login-aside"><Link viewTransition to="/" className="login-brand"><span className="brand-mark"><FileSearch size={22} /></span><span>AcaSift<small>Document similarity analysis</small></span></Link><div className="login-aside-copy"><div className="eyebrow">DOCUMENT REVIEW</div><h1>Find the overlap.<br /><span>Follow the source.</span></h1><p>Sign in to your shared AcaSift workspaces and submission requests.</p><div className="login-assurance"><ShieldCheck size={17} /> Similarity indicators support human review.</div></div><div className="login-aside-bottom">AcaSift · Document similarity analysis</div></div>
        <div className="login-main"><div className="login-card"><Link viewTransition to="/" className="back-home"><ArrowLeft size={15} /> Back to AcaSift</Link><div className="login-icon"><LockKeyhole size={22} /></div><div className="eyebrow">WELCOME BACK</div><h2>Sign in to your account</h2><p className="login-description">Enter the email address and password associated with your AcaSift account.</p>
            {actionData?.error && <div className="form-error">{actionData.error}</div>}
            <Form viewTransition method="post" className="form-stack"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" placeholder="you@example.com" autoComplete="username" required /><div className="auth-password-label"><label htmlFor="password">Password</label><Link viewTransition to="/forgot-password">Forgot password?</Link></div><input id="password" name="password" type="password" placeholder="Enter your password" autoComplete="current-password" required /><button className="button button-primary login-submit" type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <ArrowRight size={16} /></button></Form>
            <div className="login-footnote">Don't have an account? <Link viewTransition to={registerPath}>Create an account</Link>.</div><div className="login-footnote">Need another verification link? <Link viewTransition to={resendPath}>Resend verification email</Link>.</div>
        </div><div className="login-legal">By signing in, you agree to use AcaSift responsibly and respect the privacy of other users.</div></div>
    </div>;
}
