import { Form, Link, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { ArrowLeft, ArrowRight, FileSearch, ShieldCheck, LockKeyhole } from 'lucide-react';

interface SetupLoaderData {
    available: boolean;
}

export function FirstAdminSetupPage() {
    const { available } = useLoaderData() as SetupLoaderData;
    const actionData = useActionData() as { error?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';

    return <div className="bootstrap-page">
        <div className="bootstrap-card">
            <Link to="/" className="bootstrap-brand">
                <span className="brand-mark"><FileSearch size={22} /></span>
                <span>AcaSift<small>Document similarity analysis</small></span>
            </Link>

            {!available ? <>
                <div className="bootstrap-icon"><ShieldCheck size={24} /></div>
                <div className="eyebrow">INITIAL SETUP</div>
                <h1>Administrator setup is unavailable</h1>
                <p className="bootstrap-description">
                    Initial administrator setup is either disabled or has already been completed.
                    If you already have an account, sign in. If you need help recovering access,
                    contact your AcaSift administrator.
                </p>
                <Link className="button button-primary bootstrap-submit" to="/login">
                    Go to sign in <ArrowRight size={16} />
                </Link>
            </> : <>
                <div className="bootstrap-icon"><LockKeyhole size={23} /></div>
                <div className="eyebrow">SECURE FIRST-TIME CONFIGURATION</div>
                <h1>Create the first administrator</h1>
                <p className="bootstrap-description">
                    This one-time setup is available only while AcaSift has no administrator account.
                    Obtain the setup code from your AcaSift administrator.
                </p>

                {actionData?.error && <div className="form-error" role="alert">{actionData.error}</div>}

                <Form method="post" className="form-stack bootstrap-form">
                    <label htmlFor="first_name">First name</label>
                    <input id="first_name" name="first_name" type="text" maxLength={80} autoComplete="given-name" required />

                    <label htmlFor="last_name">Last name</label>
                    <input id="last_name" name="last_name" type="text" maxLength={80} autoComplete="family-name" required />

                    <label htmlFor="other_names">Other names <span>(optional)</span></label>
                    <input id="other_names" name="other_names" type="text" maxLength={80} autoComplete="additional-name" />

                    <label htmlFor="email">Administrator email</label>
                    <input id="email" name="email" type="email" maxLength={150} autoComplete="email" required />

                    <label htmlFor="password">Create password</label>
                    <input id="password" name="password" type="password" minLength={10} maxLength={256} autoComplete="new-password" required />
                    <small className="bootstrap-hint">Use at least 10 characters. A longer, unique password is recommended.</small>

                    <label htmlFor="setup_token">Setup code</label>
                    <input id="setup_token" name="setup_token" type="password" autoComplete="off" spellCheck={false} required />
                    <small className="bootstrap-hint">Enter the setup code provided to you. Do not share it.</small>

                    <button className="button button-primary bootstrap-submit" type="submit" disabled={busy}>
                        {busy ? 'Creating administrator…' : 'Create administrator'} <ArrowRight size={16} />
                    </button>
                </Form>
                <div className="bootstrap-security"><ShieldCheck size={16} /> This endpoint closes automatically after the first administrator is created.</div>
            </>}
            <Link to="/" className="bootstrap-back"><ArrowLeft size={14} /> Return to AcaSift</Link>
        </div>
    </div>;
}
