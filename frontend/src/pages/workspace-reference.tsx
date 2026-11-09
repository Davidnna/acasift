import { Form, Link, useActionData, useNavigation } from 'react-router-dom';
import { ArrowLeft, BookOpen, Upload } from 'lucide-react';
import { Notice, PageHeading } from '../components/ui';

export function WorkspaceReferenceUploadPage() {
    const actionData = useActionData() as { error?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    return <>
        <PageHeading eyebrow="WORKSPACE REFERENCE COLLECTION" title="Add reference documents" description="Add sources that can be used when analysing submissions in your active workspace." action={<Link className="button button-secondary" to="/app/workspaces"><ArrowLeft size={15} /> Back to workspaces</Link>} />
        <section className="panel form-panel">
            <div className="panel-heading"><div><h2><BookOpen size={18} /> Reference document details</h2><p>These references are available to authorised members of this shared workspace.</p></div></div>
            {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
            <Form method="post" encType="multipart/form-data" className="form-stack">
                <label htmlFor="title">Document title <span>Optional</span></label><input id="title" name="title" maxLength={255} placeholder="e.g. Research methodology handbook" />
                <label htmlFor="document">Select reference document</label><input id="document" name="document" type="file" accept=".pdf,.docx,.txt" required />
                <div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div>
                <div className="form-actions"><button className="button button-primary" disabled={busy}>{busy ? 'Adding reference…' : 'Add reference document'} <Upload size={15} /></button><Link className="button button-secondary" to="/app/documents">View documents</Link></div>
            </Form>
        </section>
        <Notice tone="info">AcaSift compares submissions with platform references and references available within this shared workspace.</Notice>
    </>;
}
