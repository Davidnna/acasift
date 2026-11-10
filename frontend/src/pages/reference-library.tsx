import { Form, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { Archive, ArrowRight, BookOpen, CheckCircle2, ShieldCheck, Upload } from 'lucide-react';
import { EmptyState, Notice, PageHeading, StatusPill, formatDate } from '../components/ui';
import type { ReferenceLibraryData, ReferenceEntryRecord } from '../types';

export function ReferenceLibraryPage() {
    const data = useLoaderData() as ReferenceLibraryData;
    const actionData = useActionData() as { error?: string; success?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const personal = data.scope === 'personal';

    return <>
        <PageHeading
            eyebrow={personal ? 'PERSONAL REFERENCES' : 'WORKSPACE REFERENCES'}
            title="Reference library"
            description={personal
                ? 'Manage private source documents used in your own similarity checks.'
                : `Manage source documents available to authorised members of ${data.workspace.name}.`}
        />
        {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
        {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}

        {personal || data.can_manage ? <section className="panel form-panel">
            <div className="panel-heading">
                <div>
                    <h2><BookOpen size={18} /> Add a reference document</h2>
                    <p>{personal
                        ? 'These documents remain private to your account and are used only in your personal comparisons.'
                        : 'Add a source that this workspace is authorised to use for similarity comparisons.'}</p>
                </div>
                <span className="panel-icon"><Upload size={18} /></span>
            </div>
            <Form method="post" encType="multipart/form-data" className="form-stack">
                <input type="hidden" name="_intent" value="upload" />
                <label htmlFor="reference-title">Document title <span>Optional</span></label>
                <input id="reference-title" name="title" maxLength={255} placeholder="Enter a descriptive title" />
                <label htmlFor="reference-source-url">Original source URL <span>Optional</span></label>
                <input id="reference-source-url" name="source_url" type="url" maxLength={1000} placeholder="https://example.org/source" />
                <label htmlFor="reference-file">Select document</label>
                <input id="reference-file" name="document" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" required />
                <div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div>
                {!personal && <label className="checkbox-row">
                    <input type="checkbox" name="permission_confirmed" value="yes" required />
                    <span>I confirm that I have the necessary rights or permission to make this document available as a reference within this workspace.</span>
                </label>}
                <button className="button button-primary" type="submit" disabled={busy}>
                    {busy ? 'Adding reference…' : 'Add to reference library'} <ArrowRight size={15} />
                </button>
            </Form>
        </section> : <Notice tone="info">You can view the references available in this workspace. Only its owner or an administrator can add, verify or remove shared references.</Notice>}

        <section className="panel">
            <div className="panel-heading">
                <div>
                    <h2>Reference documents</h2>
                    <p>{data.entries.length} document{data.entries.length === 1 ? '' : 's'} in this collection</p>
                </div>
            </div>
            {data.entries.length ? <div className="reference-entry-list">
                {data.entries.map(entry => <ReferenceEntryCard key={entry.id} entry={entry} canManage={data.can_manage} personal={personal} />)}
            </div> : <EmptyState
                title="No reference documents yet"
                description={personal
                    ? 'Add documents that you want to use as private comparison sources.'
                    : 'When an authorised workspace manager adds references, they will appear here.'}
            />}
        </section>
        <Notice tone="info">
            <strong>Collection boundaries:</strong> {personal
                ? 'Your personal references are not visible to other users and are not added to AcaSift’s global collection.'
                : 'Workspace references are available only to authorised members of this workspace. They are not automatically added to the global collection.'}
        </Notice>
    </>;
}

function ReferenceEntryCard({ entry, canManage, personal }: {
    entry: ReferenceEntryRecord;
    canManage: boolean;
    personal: boolean;
}) {
    const needsReview = entry.status === 'review_required';
    return <article className="reference-entry-card">
        <div className="reference-entry-main">
            <div className="reference-entry-icon"><BookOpen size={19} /></div>
            <div className="reference-entry-copy">
                <strong>{entry.document.title}</strong>
                <span>{entry.document.original_filename}</span>
                <small>Added {entry.document.uploaded_at ? formatDate(entry.document.uploaded_at) : '—'}</small>
                {entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer">Original source</a>}
            </div>
            <StatusPill value={needsReview ? 'review_required' : entry.status} />
        </div>
        {needsReview && canManage && !personal && <div className="reference-review-box">
            <Notice tone="warning">This older reference is not being used for comparisons until workspace permission is confirmed.</Notice>
            <Form method="post" className="form-stack compact-form">
                <input type="hidden" name="_intent" value="verify" />
                <input type="hidden" name="entry_id" value={entry.id} />
                <label className="checkbox-row">
                    <input type="checkbox" name="permission_confirmed" value="yes" required />
                    <span>I confirm that this workspace has permission to use this document as a reference.</span>
                </label>
                <button className="button button-secondary" type="submit"><ShieldCheck size={15} /> Confirm permission</button>
            </Form>
        </div>}
        {canManage && !needsReview && <div className="reference-entry-actions">
            <Form method="post">
                <input type="hidden" name="_intent" value="archive" />
                <input type="hidden" name="entry_id" value={entry.id} />
                <button className="button button-quiet" type="submit" aria-label={`Remove ${entry.document.title} from this reference library`}>
                    <Archive size={15} /> Remove from library
                </button>
            </Form>
        </div>}
        {entry.rights_verified && <div className="reference-entry-meta"><CheckCircle2 size={13} /> Permission recorded</div>}
    </article>;
}
