import { Form, Link, useActionData, useNavigation, useSearchParams } from 'react-router-dom';
import { ArrowRight, MailCheck, ShieldCheck } from 'lucide-react';
import { Notice, PageHeading } from '../components/ui';

type ConfirmationActionData = {
    error?: string;
    success?: string;
    email?: string;
};

export function EmailChangeConfirmationPage() {
    const actionData = useActionData() as ConfirmationActionData | undefined;
    const navigation = useNavigation();
    const [searchParams] = useSearchParams();
    const token = searchParams.get('token') || '';
    const busy = navigation.state === 'submitting';
    const confirmed = Boolean(actionData?.success);

    return <div className="auth-page">
        <div className="auth-card email-confirmation-card">
            <div className="auth-card-icon"><MailCheck size={24} /></div>
            <PageHeading
                eyebrow="ACCOUNT EMAIL"
                title={confirmed ? 'Email address updated' : 'Confirm your new email'}
                description={confirmed
                    ? 'Your new email address is now verified and ready to use.'
                    : 'Confirm that you have access to the new email address you requested for your AcaSift account.'}
            />
            {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
            {confirmed && <Notice tone="success">{actionData.success} {actionData.email}</Notice>}
            {!confirmed && <>
                {!token && <Notice tone="danger">This confirmation link is incomplete. Request an email change again from your account page.</Notice>}
                <Form method="post" className="form-stack">
                    <input type="hidden" name="token" value={token} />
                    <button className="button button-primary button-block" type="submit" disabled={busy || !token}>
                        {busy ? 'Confirming email…' : 'Confirm new email address'} <ArrowRight size={15} />
                    </button>
                </Form>
                <p className="form-hint"><ShieldCheck size={14} /> Your existing email remains active until this confirmation is completed.</p>
            </>}
            <Link className="button button-secondary button-block" to={confirmed ? '/login' : '/app/account'}>
                {confirmed ? 'Continue to sign in' : 'Return to account'}
            </Link>
        </div>
    </div>;
}
