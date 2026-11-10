import { useMemo, useState } from 'react';
import { Form, Link, useActionData, useLoaderData, useNavigation, useRouteLoaderData } from 'react-router-dom';
import { ArrowLeft, ArrowRight, Search, Upload } from 'lucide-react';
import { EmptyState, formatDateTime, Notice, PageHeading, StatusPill } from '../components/ui';
import { DocumentTable } from '../components/document-table';
import type { AppShellData, ComparisonDetail, DocumentRecord } from '../types';

export function DocumentsPage() {
    const documents = useLoaderData() as DocumentRecord[];
    const appData = useRouteLoaderData('app') as AppShellData | undefined;
    const actionData = useActionData() as { error?: string; success?: string; } | undefined;
    const navigation = useNavigation();
    const busy = navigation.state === 'submitting';
    const isPersonalWorkspace = appData?.activeWorkspace?.type === 'personal';
    const [query, setQuery] = useState('');
    const filtered = useMemo(() => documents.filter(doc => {
        return `${doc.title} ${doc.original_filename}`.toLowerCase().includes(query.toLowerCase());
    }), [documents, query]);
    return <>
        <PageHeading eyebrow="DOCUMENT LIBRARY" title="My documents" description={isPersonalWorkspace
            ? 'Upload documents for private similarity checks against the AcaSift Reference Bank.'
            : 'Review your own documents submitted to this workspace’s Submission Requests.'} />
        {isPersonalWorkspace ? <section className="panel form-panel document-upload-panel">
            <div className="panel-heading"><div><h2>Upload a document</h2><p>Choose a document to run a similarity check.</p></div><span className="panel-icon"><Upload size={18} /></span></div>
            {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
            {actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
            <Form method="post" encType="multipart/form-data" className="form-stack">
                <label htmlFor="document-title">Document title <span>Optional</span></label>
                <input id="document-title" name="title" maxLength={255} placeholder="e.g. Research project on database systems" />
                <label htmlFor="document-file">Select document</label>
                <input id="document-file" type="file" name="document" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" required />
                <div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div>
                <button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Uploading and analysing…' : 'Upload and analyse'} <ArrowRight size={16} /></button>
            </Form>
        </section> : <Notice tone="info">In a shared workspace, documents are submitted through a Submission Request. AcaSift compares each submission with other eligible submissions in that same request.</Notice>}
        <section className="panel">
            <div className="table-toolbar"><div className="search-field"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search documents" /></div><span className="result-count">{filtered.length} records</span></div>
            {filtered.length ? <DocumentTable documents={filtered} /> : <EmptyState title="No matching documents" description={documents.length
                ? 'Try changing your search.'
                : isPersonalWorkspace
                    ? 'Documents you upload for private analysis will appear here.'
                    : 'Your documents submitted through this workspace’s requests will appear here.'} />}
        </section>
    </>;
}

export function ComparisonPage() {
    const comparison = useLoaderData() as ComparisonDetail;
    return <>
        <PageHeading eyebrow="SIMILARITY ANALYSIS" title="Comparison report" description={`${comparison.submitted_document.title} · Comparison #${comparison.id}`} action={<Link viewTransition className="button button-secondary" to="/app/dashboard"><ArrowLeft size={15} /> Back to dashboard</Link>} />
        <div className="report-overview"><div><span>Status</span><strong><StatusPill value={comparison.status} /></strong></div><div><span>Sources compared</span><strong>{comparison.results.length}</strong></div><div><span>Started</span><strong>{formatDateTime(comparison.started_at)}</strong></div></div>
        <Notice tone="warning"><strong>Important:</strong> Similarity measurements indicate textual overlap, not a definitive plagiarism finding. Review matched passages, source context, quotations and citations before drawing conclusions.</Notice>
        <section className="methodology-note"><h3>How to interpret these measurements</h3><ul><li><strong>TF-IDF cosine similarity</strong> compares weighted term patterns across the full documents. It is not the percentage of copied content.</li><li><strong>N-gram occurrence coverage</strong> is the proportion of word-sequence windows in the submission that also occur in this reference source.</li><li><strong>Matching passages</strong> show exact normalized word-sequence overlap. Matching ignores letter case, punctuation and spacing differences, but it does not detect paraphrasing by itself.</li><li>Reports created before version 0.4.0 retain the earlier unique-N-gram coverage definition; new reports use occurrence-based coverage.</li></ul></section>
        {comparison.status === 'failed' ? <EmptyState title="Analysis did not complete" description="The analysis could not be completed. Please try again. If the problem continues, contact your AcaSift administrator." /> : comparison.results.length === 0 ? <EmptyState title="No comparison sources were available" description="For a private check, the AcaSift Reference Bank may not yet contain eligible documents. For a shared request, another participant must submit a document to the same request." /> : <section className="panel"><div className="panel-heading"><div><h2>Compared sources</h2><p>Ranked by document-level similarity</p></div></div>
            {comparison.results.map(result => {
                const occurrenceBased = result.coverage_method === 'ngram_windows';
                const sourceLabel = result.source_scope === 'request' ? 'Another submission in this request' : result.source_scope === 'global' ? 'AcaSift Reference Bank' : 'Historical reference source';
                return <article className="comparison-result" key={result.id}><div className="comparison-result-head"><div><span className="source-scope-tag">{sourceLabel}</span><h3>{result.reference_document.title}</h3><p>{result.reference_document.original_filename}</p></div><span className="match-count">{result.matched_ngram_count} {occurrenceBased ? 'matching N-gram windows' : 'matching unique N-grams'}</span></div>
                    <div className="result-metrics"><Metric label="TF-IDF cosine similarity" value={`${result.cosine_similarity.toFixed(2)}%`} /><Metric label={occurrenceBased ? 'N-gram occurrence coverage' : 'Legacy unique N-gram coverage'} value={`${result.matched_ngram_coverage.toFixed(2)}%`} /><Metric label={occurrenceBased ? 'Matched / total N-gram windows' : 'Matched / total unique N-grams'} value={`${result.matched_ngram_count} / ${result.total_query_ngrams}`} /></div>
                    {result.passages.length > 0 ? <div className="passage-section"><h4>Identified matching passages</h4>{result.passages.map((passage, i) => <div className="passage-card" key={passage.id}><div className="passage-heading">MATCH {i + 1} · SUBMITTED CHARACTERS {passage.submitted_start}–{passage.submitted_end}</div><p>{passage.matched_text}</p><div className="passage-heading reference-heading">MATCHED SOURCE · CHARACTERS {passage.reference_start}–{passage.reference_end}</div><p>{passage.reference_text}</p></div>)}</div> : <p className="muted-note">No matching N-gram passages were identified for this source.</p>}
                </article>;
            })}
        </section>}
    </>;
}

function Metric({ label, value }: { label: string; value: string; }) { return <div className="result-metric"><span>{label}</span><strong>{value}</strong></div>; }

