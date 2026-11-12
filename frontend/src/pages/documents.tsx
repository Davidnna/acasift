import { Link, useLoaderData } from 'react-router-dom';
import { ArrowLeft, LayoutDashboard } from 'lucide-react';
import { EmptyState, Notice, PageHeading, StatusPill, formatDateTime } from '../components/ui';
import { DocumentTable } from '../components/document-table';
import type { ComparisonDetail, DocumentRecord } from '../types';

export function DocumentsPage() {
    const documents = useLoaderData() as DocumentRecord[];
    return <>
        <PageHeading
            eyebrow="DOCUMENT ACTIVITY"
            title="My submissions"
            description="View the documents you have submitted through shared Submission Requests."
        />
        <Notice tone="info">This page lists your own submissions. Similarity reports are available from a Submission Request only when you have workspace administrator or assigned reviewer permissions.</Notice>
        {documents.length
            ? <section className="panel"><DocumentTable documents={documents} /></section>
            : <section className="panel"><EmptyState title="No submissions yet" description="Documents you submit through a shared Submission Request will appear here." action={<Link viewTransition className="button button-primary" to="/app/dashboard"><LayoutDashboard size={16} /> Return to overview</Link>} /></section>}
    </>;
}

export function ComparisonPage() {
    const comparison = useLoaderData() as ComparisonDetail;
    return <>
        <PageHeading eyebrow="SIMILARITY ANALYSIS" title="Comparison report" description={`${comparison.submitted_document.title} · Comparison #${comparison.id}`} action={<Link viewTransition className="button button-secondary" to="/app/submission-requests"><ArrowLeft size={15} /> Back to requests</Link>} />
        <div className="report-overview"><div><span>Status</span><strong><StatusPill value={comparison.status} /></strong></div><div><span>Sources compared</span><strong>{comparison.results.length}</strong></div><div><span>Started</span><strong>{formatDateTime(comparison.started_at)}</strong></div></div>
        <Notice tone="warning"><strong>Important:</strong> Similarity measurements indicate textual overlap, not a definitive plagiarism finding. Review matched passages, source context, quotations and citations before drawing conclusions.</Notice>
        <section className="methodology-note"><h3>How to interpret these measurements</h3><ul><li><strong>TF-IDF cosine similarity</strong> compares weighted term patterns across the full documents. It is not the percentage of copied content.</li><li><strong>N-gram occurrence coverage</strong> is the proportion of word-sequence windows in the submission that also occur in this reference source. Repeated windows are counted.</li><li><strong>Matching passages</strong> show exact normalised word-sequence overlap. Matching ignores letter case, punctuation and spacing differences, but it does not detect paraphrasing by itself.</li><li>Reports created before version 0.4.0 retain the earlier unique-N-gram coverage definition; new reports use occurrence-based coverage.</li></ul></section>
        {comparison.status === 'failed' ? <EmptyState title="Analysis did not complete" description="The analysis could not be completed. Please try again. If the problem continues, contact your AcaSift administrator." /> : comparison.results.length === 0 ? <EmptyState title="No comparison sources were available" description="Another participant must submit a document to the same request before peer comparison is possible." /> : <section className="panel"><div className="panel-heading"><div><h2>Compared submissions</h2><p>Ranked by document-level similarity</p></div></div>
            {comparison.results.map(result => {
                const occurrenceBased = result.coverage_method === 'ngram_windows';
                return <article className="comparison-result" key={result.id}><div className="comparison-result-head"><div><span className="source-scope-tag">Another submission in this request</span><h3>{result.reference_document.title}</h3><p>{result.reference_document.original_filename}</p></div><span className="match-count">{result.matched_ngram_count} {occurrenceBased ? 'matching N-gram windows' : 'matching unique N-grams'}</span></div>
                    <div className="result-metrics"><Metric label="TF-IDF cosine similarity" value={`${result.cosine_similarity.toFixed(2)}%`} /><Metric label={occurrenceBased ? 'N-gram occurrence coverage' : 'Legacy unique N-gram coverage'} value={`${result.matched_ngram_coverage.toFixed(2)}%`} /><Metric label={occurrenceBased ? 'Matched / total N-gram windows' : 'Matched / total unique N-grams'} value={`${result.matched_ngram_count} / ${result.total_query_ngrams}`} /></div>
                    {result.passages.length > 0 ? <div className="passage-section"><h4>Identified matching passages</h4>{result.passages.map((passage, i) => <div className="passage-card" key={passage.id}><div className="passage-heading">MATCH {i + 1} · SUBMITTED CHARACTERS {passage.submitted_start}–{passage.submitted_end}</div><p>{passage.matched_text}</p><div className="passage-heading reference-heading">MATCHED SOURCE · CHARACTERS {passage.reference_start}–{passage.reference_end}</div><p>{passage.reference_text}</p></div>)}</div> : <p className="muted-note">No matching N-gram passages were identified for this source.</p>}
                </article>;
            })}
        </section>}
    </>;
}

function Metric({ label, value }: { label: string; value: string; }) { return <div className="result-metric"><span>{label}</span><strong>{value}</strong></div>; }
