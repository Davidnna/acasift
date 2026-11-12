import { Form, useActionData, useLoaderData, useNavigation } from 'react-router-dom';
import { Archive, ArrowRight, BookOpen, CheckCircle2, ShieldCheck, Users, Database, CloudDownload, Search, FileText, Clock3, AlertCircle } from 'lucide-react';
import { EmptyState, Notice, PageHeading, StatusPill, formatDateTime } from '../components/ui';
import type { AcquisitionDashboardData, ReferenceEntryRecord, User } from '../types';

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
        <PageHeading eyebrow="ADMINISTRATION" title="AcaSift Reference Bank" description="Manage platform-held source documents and their reuse permissions." />
        <Notice tone="info">The current shared-workspace comparison workflow compares submissions within the same Submission Request. This platform-managed collection is administered separately and is not included in those request reports.</Notice>
        {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
        {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
        <section className="panel form-panel">
            <div className="panel-heading"><div><h2><BookOpen size={18} /> Add a reference document</h2><p>Record the source and permission basis before adding a document to the Reference Bank.</p></div><span className="panel-icon"><ShieldCheck size={18} /></span></div>
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
                <button className="button button-primary" disabled={busy}>{busy ? 'Adding reference…' : 'Add to Reference Bank'} <ArrowRight size={15} /></button>
            </Form>
        </section>
        <section className="panel">
            <div className="panel-heading"><div><h2>Reference Bank records</h2><p>{entries.filter(entry => entry.status === 'active').length} active platform sources · {entries.length} total records</p></div></div>
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
                {entry.status !== 'archived' && <div className="reference-entry-actions"><Form method="post"><input type="hidden" name="_intent" value="archive" /><input type="hidden" name="entry_id" value={entry.id} /><button className="button button-quiet" type="submit"><Archive size={15} /> Remove from future comparisons</button></Form></div>}
            </article>)}</div> : <EmptyState title="The Reference Bank is empty" description="Add legitimate reference documents with their source and permission information." />}
        </section>
        <Notice tone="info">Documents awaiting rights review are retained for administrative review but are not used in global similarity comparisons. Public availability alone does not establish permission to reuse a document.</Notice>
    </>;
}


export function AdminAcquisitionPage() {
    const data = useLoaderData() as AcquisitionDashboardData;
    const actionData = useActionData() as {
        error?: string;
        success?: string;
        job?: {
            id: number;
            status: string;
            discovered_count: number;
            indexed_count: number;
            metadata_only_count: number;
            failed_count: number;
            duplicate_count: number;
            error_message: string | null;
        };
    } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';

    return <>
        <PageHeading
            eyebrow="ADMINISTRATION"
            title="Reference Acquisition"
            description="Discover scholarly publications from trusted research services and add eligible full texts to the AcaSift Reference Bank."
        />
        <Notice tone="info">The current shared-workspace comparison workflow compares submissions within the same Submission Request. Acquired reference records are managed separately and are not currently included in those request reports.</Notice>
        {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
        {actionData?.success && actionData.job && <Notice tone="success">
            {actionData.success} Job #{actionData.job.id}: {actionData.job.discovered_count} records discovered, {actionData.job.indexed_count} full texts indexed, {actionData.job.metadata_only_count} metadata-only records and {actionData.job.failed_count} failed records. {actionData.job.error_message || ''}
        </Notice>}

        <div className="stats-grid">
            <div className="stat-card"><div className="stat-card-top"><span>Metadata records</span><span className="stat-icon"><Database size={17} /></span></div><strong>{data.counts.total.toLocaleString()}</strong><small>Unique scholarly records discovered</small></div>
            <div className="stat-card"><div className="stat-card-top"><span>Indexed full texts</span><span className="stat-icon"><FileText size={17} /></span></div><strong>{data.counts.indexed.toLocaleString()}</strong><small>Indexed in the platform Reference Bank</small></div>
            <div className="stat-card"><div className="stat-card-top"><span>Metadata only</span><span className="stat-icon"><Search size={17} /></span></div><strong>{data.counts.metadata_only.toLocaleString()}</strong><small>Full text or reusable licence not confirmed</small></div>
            <div className="stat-card"><div className="stat-card-top"><span>Eligible pending</span><span className="stat-icon"><Clock3 size={17} /></span></div><strong>{data.counts.eligible.toLocaleString()}</strong><small>Full-text imports awaiting processing</small></div>
            <div className="stat-card"><div className="stat-card-top"><span>Active global references</span><span className="stat-icon"><CheckCircle2 size={17} /></span></div><strong>{data.counts.reference_bank_count.toLocaleString()}</strong><small>Permission-verified platform sources</small></div>
        </div>

        <section className="panel form-panel">
            <div className="panel-heading">
                <div><h2><CloudDownload size={18} /> Discover publications</h2><p>Run a bounded search against one scholarly source. Each run retrieves up to 25 metadata records and attempts a maximum of two eligible full-text imports.</p></div>
                <span className="panel-icon"><Database size={18} /></span>
            </div>
            <Form method="post" className="form-stack">
                <label htmlFor="acquisition-provider">Scholarly source</label>
                <select id="acquisition-provider" name="provider" defaultValue="openalex" required>
                    {data.providers.map(provider => <option value={provider.id} key={provider.id}>{provider.name}{provider.kind === 'full_text' ? ' · full-text capable' : ' · discovery'}</option>)}
                </select>
                <label htmlFor="acquisition-query">Search topic or keywords</label>
                <input id="acquisition-query" name="query" required minLength={3} maxLength={500} placeholder="e.g. machine learning in software engineering" />
                <label htmlFor="acquisition-limit">Maximum records to retrieve</label>
                <select id="acquisition-limit" name="limit" defaultValue="10">
                    <option value="5">5 records</option>
                    <option value="10">10 records</option>
                    <option value="20">20 records</option>
                    <option value="25">25 records</option>
                </select>
                <div className="form-hint">Repeated searches with the same source and query continue from the saved page. Change the query to start a separate search. OpenAlex requires an API key to continue cursor paging beyond its first page.</div>
                <div className="form-hint">Only documents with a recognised reuse licence are eligible for automatic full-text indexing. Other records are retained as metadata and are not used for similarity comparisons.</div>
                <button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Searching scholarly sources…' : 'Discover and acquire'} <ArrowRight size={15} /></button>
            </Form>
        </section>

        <section className="panel">
            <div className="panel-heading"><div><h2>Connected scholarly sources</h2><p>Public discovery integrations. Optional API credentials can improve access limits.</p></div></div>
            <div className="reference-entry-list">
                {data.providers.map(provider => <article className="reference-entry-card" key={provider.id}>
                    <div className="reference-entry-main">
                        <div className="reference-entry-icon"><Database size={19} /></div>
                        <div className="reference-entry-copy">
                            <strong>{provider.name}</strong>
                            <span>{provider.kind === 'full_text' ? 'Metadata discovery and eligible full-text retrieval' : 'Scholarly metadata discovery and open-access location resolution'}</span>
                            <small>Provider: {provider.id.replace(/_/g, ' ')}</small>
                        </div>
                        <StatusPill value="available" />
                    </div>
                </article>)}
            </div>
            <Notice tone="info">CORE is not enabled in this release. Its commercial API terms require a separate licence arrangement before AcaSift can use it as a product data source.</Notice>
        </section>

        <section className="panel">
            <div className="panel-heading"><div><h2><Clock3 size={18} /> Recent acquisition runs</h2><p>{data.jobs.length} most recent jobs</p></div></div>
            {data.jobs.length ? <div className="reference-entry-list">{data.jobs.map(job => <article className="reference-entry-card" key={job.id}>
                <div className="reference-entry-main">
                    <div className="reference-entry-icon"><CloudDownload size={19} /></div>
                    <div className="reference-entry-copy">
                        <strong>#{job.id} · {job.provider.replace(/_/g, ' ')} · {job.query}</strong>
                        <span>{job.discovered_count} discovered · {job.indexed_count} indexed · {job.metadata_only_count} metadata only · {job.duplicate_count} duplicates · {job.failed_count} failed</span>
                        <small>{formatDateTime(job.created_at)}</small>
                        {job.error_message && <small>{job.error_message}</small>}
                    </div>
                    <StatusPill value={job.status} />
                </div>
            </article>)}</div> : <EmptyState title="No acquisition runs yet" description="Choose a scholarly source and run your first search to begin building the Reference Bank." />}
        </section>

        <section className="panel">
            <div className="panel-heading"><div><h2>Saved searches</h2><p>Run the same provider and query again to continue from the saved page or cursor.</p></div></div>
            {data.searches.length ? <div className="reference-entry-list">{data.searches.map((search, index) => <article className="reference-entry-card" key={`${search.provider}-${search.query}-${index}`}>
                <div className="reference-entry-main">
                    <div className="reference-entry-icon"><Search size={19} /></div>
                    <div className="reference-entry-copy">
                        <strong>{search.provider.replace(/_/g, ' ')} · {search.query}</strong>
                        <span>{search.total_available === null ? 'Total result count unavailable' : `${search.total_available.toLocaleString()} results reported by source`}</span>
                        <small>{search.exhausted ? 'Search completed' : `More results may be available${search.next_page ? ` · next page ${search.next_page}` : ''}${search.next_offset !== null ? ` · next offset ${search.next_offset}` : ''}`} · Updated {formatDateTime(search.updated_at)}</small>
                    </div>
                    <StatusPill value={search.exhausted ? 'completed' : 'continuable'} />
                </div>
            </article>)}</div> : <EmptyState title="No saved searches" description="Your searches and pagination progress will appear here." />}
        </section>

        <section className="panel">
            <div className="panel-heading"><div><h2>Recently discovered publications</h2><p>Latest metadata records from connected sources.</p></div></div>
            {data.records.length ? <div className="reference-entry-list">{data.records.map(record => <article className="reference-entry-card" key={record.id}>
                <div className="reference-entry-main">
                    <div className="reference-entry-icon"><FileText size={19} /></div>
                    <div className="reference-entry-copy">
                        <strong>{record.title}</strong>
                        <span>{record.year || 'Year unavailable'} · {record.provider.replace(/_/g, ' ')}{record.doi ? ` · DOI: ${record.doi}` : ''}</span>
                        <small>Rights: {record.rights_status.replace(/_/g, ' ')} · Record: {record.status.replace(/_/g, ' ')}</small>
                    </div>
                    <StatusPill value={record.status} />
                </div>
            </article>)}</div> : <EmptyState title="No scholarly records yet" description="Run a discovery search to start collecting publication metadata." />}
        </section>
        <Notice tone="warning"><AlertCircle size={16} /> This first release is a controlled acquisition pilot, not yet a million-document bulk-ingestion service. It discovers up to 25 records per run and imports up to two full texts, with saved pagination and an import backlog. Bulk snapshot ingestion, a dedicated scheduled worker and a scalable comparison index are subsequent scaling work.</Notice>
    </>;
}
