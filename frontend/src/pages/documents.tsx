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
    const peerSources = comparison.results || [];
    const externalSources = comparison.external_results || [];
    const providerSummary = comparison.external_provider_summary || {};
    const externalSearchRun = Boolean(comparison.external_search_status && comparison.external_search_status !== 'pending');
    const semanticEnabled = peerSources.some((item) => item.semantic_status === 'completed')
        || externalSources.some((item) => item.semantic_status === 'completed');
    const semanticUnavailable = peerSources.some((item) => item.semantic_status === 'unavailable')
        || externalSources.some((item) => item.semantic_status === 'unavailable');
    const semanticStateLabel = semanticEnabled ? 'available' : (semanticUnavailable ? 'configured but unavailable' : 'not enabled');

    return <>
        <PageHeading
            eyebrow="SIMILARITY ANALYSIS"
            title="Comparison report"
            description={`${comparison.submitted_document.title} · Comparison #${comparison.id}`}
            action={<Link viewTransition className="button button-secondary" to="/app/submission-requests"><ArrowLeft size={15} /> Back to requests</Link>}
        />
        <div className="report-overview">
            <div><span>Status</span><strong><StatusPill value={comparison.status} /></strong></div>
            <div><span>Peer submissions compared</span><strong>{peerSources.length}</strong></div>
            <div><span>External records discovered</span><strong>{comparison.external_sources_discovered || 0}</strong></div>
            <div><span>External full texts checked</span><strong>{comparison.external_sources_compared || 0}</strong></div>
            <div><span>External sources with matches</span><strong>{comparison.external_sources_with_matches || 0}</strong></div>
            <div><span>Started</span><strong>{formatDateTime(comparison.started_at)}</strong></div>
        </div>

        <Notice tone="warning">
            <strong>Important:</strong> Similarity measurements indicate textual overlap or sentence-level resemblance.
            They are not a definitive plagiarism finding. Review source context, quotations, citations, licensing and
            the original document before drawing conclusions.
        </Notice>

        <section className="methodology-note">
            <h3>How the measurements work</h3>
            <ul>
                <li><strong>TF-IDF cosine similarity</strong> measures lexical similarity across document content; it is not a copied-content percentage.</li>
                <li><strong>Exact N-gram coverage</strong> measures the proportion of submission word-sequence windows found in the source.</li>
                <li><strong>Fuzzy sentence matching</strong> identifies near-identical sentences with limited wording changes. Its coverage credits only submitted words not already attributed to exact N-gram matches.</li>
                <li><strong>Semantic matching</strong> compares sentence embeddings using a local model when one is installed and enabled. Its coverage credits only words not already attributed to exact or fuzzy matches. {`Semantic analysis was ${semanticStateLabel} for this report.`}</li>
                <li><strong>Unique matched-word coverage</strong> measures the proportion of submitted words covered by at least one matching method. Each submitted word is credited once, using exact, fuzzy or semantic evidence in that order. It is a reviewer aid, not a probability of plagiarism.</li>
                <li>External full text is retrieved only from publicly accessible sources with a recognised reuse licence (or where eligible Europe PMC article XML declares one), processed temporarily and discarded. The default run is bounded to 40 metadata records and 8 permitted full-text downloads. A metadata record is not itself a document comparison; only successfully retrieved, permitted full texts are compared.</li>
                <li>Provider searches are bounded and concurrent. Recent metadata responses may be cached briefly to reduce repeated API traffic; full-text documents are never cached. A missing external match does not establish that no overlap exists because not every scholarly work is openly accessible or licensed for retrieval.</li>
            </ul>
        </section>

        {comparison.status === 'failed' ? (
            <EmptyState title="Analysis did not complete" description="The analysis could not be completed. Please try again. If the problem continues, contact your AcaSift administrator." />
        ) : <>
            <section className="panel">
                <div className="panel-heading">
                    <div>
                        <h2>Shared-workspace submissions</h2>
                        <p>All eligible submissions from this same Submission Request, excluding the current contributor's own attempts.</p>
                    </div>
                </div>
                {peerSources.length === 0 ? (
                    <p className="muted-note">No other eligible submission was available in this request when this comparison ran.</p>
                ) : peerSources.map((result) => {
                    const occurrenceBased = result.coverage_method === 'ngram_windows';
                    return <article className="comparison-result" key={result.id}>
                        <div className="comparison-result-head">
                            <div>
                                <span className="source-scope-tag">Another submission in this request</span>
                                <h3>{result.reference_document.title}</h3>
                                <p>{result.reference_document.original_filename}</p>
                            </div>
                            <span className="match-count">{result.matched_ngram_count} {occurrenceBased ? "matching N-gram windows" : "matching unique N-grams"}</span>
                        </div>
                        <div className="result-metrics">
                            <Metric label="Unique matched-word coverage" value={externalSearchRun ? `${result.composite_similarity.toFixed(2)}%` : "Not calculated"} />
                            <Metric label="TF-IDF lexical similarity" value={`${result.cosine_similarity.toFixed(2)}%`} />
                            <Metric label={occurrenceBased ? "Exact N-gram occurrence coverage" : "Legacy unique N-gram coverage"} value={`${result.matched_ngram_coverage.toFixed(2)}%`} />
                            <Metric label="Fuzzy sentence coverage" value={externalSearchRun ? `${result.fuzzy_coverage.toFixed(2)}%` : "Not calculated"} />
                            <Metric label="Semantic sentence coverage" value={result.semantic_coverage === null ? (result.semantic_status === "unavailable" ? "Unavailable" : "Not enabled") : `${result.semantic_coverage.toFixed(2)}%`} />
                        </div>
                        {result.passages.length > 0 ? (
                            <div className="passage-section">
                                <h4>Identified matching passages</h4>
                                {result.passages.map((passage, index) => (
                                    <div className="passage-card" key={passage.id}>
                                        <div className="passage-heading">
                                            {String(passage.match_method || 'exact_ngram').replace(/_/g, ' ').toUpperCase()}
                                            {' · '}MATCH {index + 1}
                                            {passage.match_score !== undefined ? ` · ${passage.match_score.toFixed(2)}%` : ''}
                                        </div>
                                        <p>{passage.matched_text}</p>
                                        <div className="passage-heading reference-heading">MATCHED PEER-SUBMISSION EXCERPT</div>
                                        <p>{passage.reference_text}</p>
                                    </div>
                                ))}
                            </div>
                        ) : <p className="muted-note">No exact, fuzzy or semantic passage matches were identified for this peer source.</p>}
                    </article>;
                })}
            </section>

            <section className="panel external-scholarly-panel">
                <div className="panel-heading">
                    <div>
                        <h2>External scholarly sources</h2>
                        <p>Live discovery across OpenAlex, Crossref, Europe PMC, DOAJ, Zenodo, Semantic Scholar, arXiv and OpenAIRE. Unpaywall resolves DOI-based open-access locations and licence details.</p>
                    </div>
                    <StatusPill value={externalSearchRun ? (comparison.external_search_status || 'completed') : 'Not run'} />
                </div>

                {!externalSearchRun && <p className="muted-note">External scholarly search was not run for this historical report.</p>}
                {comparison.external_search_status === 'failed' && (
                    <Notice tone="warning">
                        External scholarly discovery could not complete. The internal peer-submission comparison remains available.
                        {comparison.external_search_error ? ` ${comparison.external_search_error}` : ''}
                    </Notice>
                )}
                {comparison.external_search_status === 'unavailable' && (
                    <Notice tone="warning">The scholarly providers did not return usable search results for this run. The internal peer-submission comparison remains available.</Notice>
                )}
                {Object.keys(providerSummary).length > 0 && (
                    <p className="muted-note">
                        Provider queries: {Object.entries(providerSummary).map(([provider, summary]) =>
                            provider === 'unpaywall' && !summary.configured
                                ? 'Unpaywall not configured'
                                : `${provider.replace(/_/g, ' ')} ${summary.queries_succeeded}/${summary.queries_attempted}`
                        ).join(' · ')}
                    </p>
                )}
                {externalSearchRun && externalSources.length === 0 && (comparison.external_sources_compared || 0) > 0 && (
                    <p className="muted-note">
                        {comparison.external_sources_compared} permitted open-access full text source(s) were checked.
                        No qualifying exact, fuzzy or semantic overlap was identified.
                    </p>
                )}
                {externalSearchRun && !['failed', 'unavailable'].includes(comparison.external_search_status || '') && externalSources.length === 0 && (comparison.external_sources_compared || 0) === 0 && (
                    <p className="muted-note">
                        {comparison.external_sources_discovered || 0} scholarly record(s) were discovered, but no full text with a recognised reuse licence was available for comparison.
                    </p>
                )}

                {externalSources.map((source) => (
                    <article className="comparison-result external-source-result" key={source.id}>
                        <div className="comparison-result-head">
                            <div>
                                <span className="source-scope-tag">External scholarly source · {source.provider.replace(/_/g, ' ')}</span>
                                <h3>{source.title}</h3>
                                <p>
                                    {source.authors.slice(0, 5).join(', ')}
                                    {source.authors.length > 5 ? ' et al.' : ''}
                                    {source.year ? ` · ${source.year}` : ''}
                                    {source.journal ? ` · ${source.journal}` : ''}
                                </p>
                                {source.doi && <p>DOI: {source.doi}</p>}
                        {source.evidence_method_counts && <p className="muted-note">Evidence methods: {Object.entries(source.evidence_method_counts).map(([method, count]) => `${method.replace(/_/g, ' ')} (${count})`).join(' · ')}</p>}
                                {source.license_name && <p>Reuse licence identified: {source.license_name}</p>}
                            </div>
                            <span className="match-count">{source.composite_similarity.toFixed(2)}% combined</span>
                        </div>
                        <div className="result-metrics">
                            <Metric label="Unique matched-word coverage" value={`${source.composite_similarity.toFixed(2)}%`} />
                            <Metric label="TF-IDF lexical similarity" value={`${source.cosine_similarity.toFixed(2)}%`} />
                            <Metric label="Exact N-gram coverage" value={`${source.exact_ngram_coverage.toFixed(2)}%`} />
                            <Metric label="Fuzzy sentence coverage" value={`${source.fuzzy_coverage.toFixed(2)}%`} />
                            <Metric label="Semantic sentence coverage" value={source.semantic_coverage === null ? (source.semantic_status === "unavailable" ? "Unavailable" : "Not enabled") : `${source.semantic_coverage.toFixed(2)}%`} />
                        </div>
                        <p className="external-source-links">
                            {source.source_url && <a href={source.source_url} target="_blank" rel="noreferrer">Open source record</a>}
                            {source.full_text_url && <a href={source.full_text_url} target="_blank" rel="noreferrer">Open retrieved full text</a>}
                            {source.doi && <a href={`https://doi.org/${encodeURIComponent(source.doi)}`} target="_blank" rel="noreferrer">Resolve DOI</a>}
                        </p>
                        {source.passages.length > 0 && (
                            <div className="passage-section">
                                <h4>Matched evidence excerpts</h4>
                                {source.passages.map((passage, index) => (
                                    <div className="passage-card" key={passage.id}>
                                        <div className="passage-heading">
                                            {passage.match_method.replace(/_/g, ' ').toUpperCase()}
                                            {' · '}MATCH {index + 1} · {passage.match_score.toFixed(2)}%
                                        </div>
                                        <p>{passage.matched_text}</p>
                                        <div className="passage-heading reference-heading">EXTERNAL SOURCE EXCERPT</div>
                                        <p>{passage.source_excerpt}</p>
                                    </div>
                                ))}
                            </div>
                        )}
                    </article>
                ))}
            </section>
        </>}
    </>;
}

function Metric({ label, value }: { label: string; value: string; }) { return <div className="result-metric"><span>{label}</span><strong>{value}</strong></div>; }
