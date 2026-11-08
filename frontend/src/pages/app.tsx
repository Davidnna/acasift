import type { ReactNode } from 'react';
import { useActionData, useLoaderData, Form, Link, useNavigation } from 'react-router-dom';
import {
  ArrowLeft, ArrowRight, ArrowUpRight, BookOpen, CheckCircle2, FileCheck2,
  FileSearch, FileText, Filter, Plus, Search, ShieldCheck, Upload, Users,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { EmptyState, formatDate, formatDateTime, Notice, PageHeading, StatusPill } from '../components/ui';
import type { ComparisonDetail, DashboardData, DocumentRecord, User } from '../types';

export function DashboardPage() {
  const data = useLoaderData() as DashboardData;
  return <>
    <PageHeading eyebrow="WORKSPACE OVERVIEW" title="Dashboard" description="Review your documents and inspect academic text similarity results." action={<Link className="button button-primary" to="/app/documents/new"><Plus size={16} /> Check a document</Link>} />
    <div className="stats-grid">
      <StatCard label="Your documents" value={data.stats.document_count} foot="Uploaded documents" icon={<FileText />} />
      <StatCard label="Comparisons" value={data.stats.comparison_count} foot="Analysis records" icon={<FileSearch />} />
      <StatCard label="Reference repository" value={data.stats.reference_count} foot="Available reference documents" icon={<BookOpen />} />
    </div>
    <div className="dashboard-grid">
      <section className="panel"><div className="panel-heading"><div><h2>Recent documents</h2><p>Your latest uploaded files</p></div><Link to="/app/documents">View all <ArrowRight size={14} /></Link></div>
        {data.recent_documents.length ? <DocumentTable documents={data.recent_documents} compact /> : <EmptyState title="No documents yet" description="Upload a document to begin your first comparison." action={<Link className="button button-primary" to="/app/documents/new">Upload a document</Link>} />}
      </section>
      <section className="panel"><div className="panel-heading"><div><h2>Recent comparisons</h2><p>Your latest analysis activity</p></div></div>
        {data.recent_comparisons.length ? <div className="activity-list">{data.recent_comparisons.map(item => <Link className="activity-item" to={`/app/comparisons/${item.id}`} key={item.id}><span className="activity-icon"><FileSearch size={17} /></span><span className="activity-copy"><strong>{item.submitted_document.title}</strong><small>Comparison #{item.id} · {formatDate(item.started_at)}</small></span><StatusPill value={item.status} /><ArrowUpRight size={15} /></Link>)}</div> : <EmptyState title="No comparisons yet" description="Completed analyses will appear here." />}
      </section>
    </div>
    <Notice tone="info"><strong>Interpretation note:</strong> A similarity score measures textual overlap. It does not by itself establish plagiarism. Quotations, references and common technical language may also produce matches.</Notice>
  </>;
}

function StatCard({ label, value, foot, icon }: { label: string; value: number; foot: string; icon: ReactNode }) {
  return <div className="stat-card"><div className="stat-card-top"><span>{label}</span><span className="stat-icon">{icon}</span></div><strong>{value}</strong><small>{foot}</small></div>;
}

export function DocumentsPage() {
  const documents = useLoaderData() as DocumentRecord[];
  const [query, setQuery] = useState('');
  const [type, setType] = useState('all');
  const filtered = useMemo(() => documents.filter(doc => {
    const matchesQuery = `${doc.title} ${doc.original_filename}`.toLowerCase().includes(query.toLowerCase());
    const matchesType = type === 'all' || doc.document_type === type;
    return matchesQuery && matchesType;
  }), [documents, query, type]);
  return <>
    <PageHeading eyebrow="DOCUMENT LIBRARY" title="Documents" description="Browse documents available to your account." action={<Link className="button button-primary" to="/app/documents/new"><Plus size={16} /> Upload document</Link>} />
    <section className="panel">
      <div className="table-toolbar"><div className="search-field"><Search size={16} /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search documents" /></div><div className="filter-field"><Filter size={15} /><select value={type} onChange={e => setType(e.target.value)}><option value="all">All document types</option><option value="submission">Submissions</option><option value="reference">Reference documents</option></select></div><span className="result-count">{filtered.length} records</span></div>
      {filtered.length ? <DocumentTable documents={filtered} /> : <EmptyState title="No matching documents" description={documents.length ? 'Try changing your search or filter.' : 'Documents uploaded to your account will appear here.'} />}
    </section>
  </>;
}

function DocumentTable({ documents, compact = false }: { documents: DocumentRecord[]; compact?: boolean }) {
  return <div className="table-scroll"><table className="data-table"><thead><tr><th>Document</th><th>Category</th>{!compact && <th>Uploaded by</th>}<th>Date added</th><th>Status</th></tr></thead><tbody>{documents.map(doc => <tr key={doc.id}><td><div className="file-cell"><span className="file-type-icon">{doc.file_type.toUpperCase().slice(0, 4)}</span><span><strong>{doc.title}</strong><small>{doc.original_filename}</small></span></div></td><td><span className={`category-tag category-${doc.document_type}`}>{doc.document_type === 'reference' ? 'Reference' : 'Submission'}</span></td>{!compact && <td>{doc.uploader || '—'}</td>}<td>{formatDate(doc.uploaded_at)}</td><td><StatusPill value={doc.processing_status} /></td></tr>)}</tbody></table></div>;
}

export function UploadSubmissionPage() {
  const actionData = useActionData() as { error?: string } | undefined;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  return <>
    <PageHeading eyebrow="DOCUMENT ANALYSIS" title="Check a document" description="Upload an academic document for comparison against the internal reference repository." />
    <section className="panel form-panel"><div className="panel-heading"><div><h2>Submission details</h2><p>Choose a supported document format.</p></div><span className="panel-icon"><Upload size={18} /></span></div>
      {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
      <Form method="post" encType="multipart/form-data" className="form-stack">
        <label htmlFor="title">Document title <span>Optional</span></label><input id="title" name="title" maxLength={255} placeholder="e.g. Research project on database systems" />
        <label htmlFor="document">Select document</label><input id="document" type="file" name="document" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" required />
        <div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div>
        <div className="form-actions"><button className="button button-primary" type="submit" disabled={busy}>{busy ? 'Uploading and analysing…' : 'Upload and analyse'} <ArrowRight size={16} /></button><Link className="button button-secondary" to="/app/dashboard">Cancel</Link></div>
      </Form>
    </section>
    <Notice tone="info"><strong>Before uploading:</strong> AcaSift compares your document with administrator-curated reference documents already in the repository. Scanned image-only PDFs are not supported in this release.</Notice>
  </>;
}

export function ComparisonPage() {
  const comparison = useLoaderData() as ComparisonDetail;
  return <>
    <PageHeading eyebrow="SIMILARITY ANALYSIS" title="Comparison report" description={`${comparison.submitted_document.title} · Comparison #${comparison.id}`} action={<Link className="button button-secondary" to="/app/dashboard"><ArrowLeft size={15} /> Back to dashboard</Link>} />
    <div className="report-overview"><div><span>Status</span><strong><StatusPill value={comparison.status} /></strong></div><div><span>Reference documents compared</span><strong>{comparison.results.length}</strong></div><div><span>Started</span><strong>{formatDateTime(comparison.started_at)}</strong></div></div>
    <Notice tone="warning"><strong>Important:</strong> Similarity measurements indicate textual overlap, not a definitive plagiarism finding. Review matched passages, source context, quotations and citations before drawing conclusions.</Notice>
    {comparison.status === 'failed' ? <EmptyState title="Analysis did not complete" description="The application could not finish this comparison. Check the application log and try again." /> : comparison.results.length === 0 ? <EmptyState title="No reference documents were available" description="Ask an administrator to add documents to the reference repository, then upload your submission again." /> : <section className="panel"><div className="panel-heading"><div><h2>Compared sources</h2><p>Ranked by document-level similarity</p></div></div>
      {comparison.results.map(result => <article className="comparison-result" key={result.id}><div className="comparison-result-head"><div><h3>{result.reference_document.title}</h3><p>{result.reference_document.original_filename}</p></div><span className="match-count">{result.matched_ngram_count} matching N-grams</span></div>
        <div className="result-metrics"><Metric label="Cosine similarity" value={`${result.cosine_similarity.toFixed(2)}%`} /><Metric label="Matched N-gram coverage" value={`${result.matched_ngram_coverage.toFixed(2)}%`} /><Metric label="Unique query N-grams" value={String(result.total_query_ngrams)} /></div>
        {result.passages.length > 0 ? <div className="passage-section"><h4>Identified matching passages</h4>{result.passages.map((passage, i) => <div className="passage-card" key={passage.id}><div className="passage-heading">MATCH {i + 1} · SUBMITTED CHARACTERS {passage.submitted_start}–{passage.submitted_end}</div><p>{passage.matched_text}</p><div className="passage-heading reference-heading">REFERENCE SOURCE · CHARACTERS {passage.reference_start}–{passage.reference_end}</div><p>{passage.reference_text}</p></div>)}</div> : <p className="muted-note">No matching N-gram passages were identified for this source.</p>}
      </article>)}
    </section>}
  </>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="result-metric"><span>{label}</span><strong>{value}</strong></div>; }

export function AdminUsersPage() {
  const users = useLoaderData() as User[];
  const actionData = useActionData() as { error?: string; success?: string } | undefined;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  return <>
    <PageHeading eyebrow="ADMINISTRATION" title="Manage users" description="Create accounts and assign application roles." />
    <div className="admin-content-grid"><section className="panel form-panel"><div className="panel-heading"><div><h2>Create account</h2><p>Provide account details to a new user.</p></div><span className="panel-icon"><Users size={18} /></span></div>
      {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}{actionData?.success && <Notice tone="success">{actionData.success}</Notice>}
      <Form method="post" className="form-stack"><label htmlFor="full_name">Full name</label><input id="full_name" name="full_name" required maxLength={150} /><label htmlFor="email">Email address</label><input id="email" type="email" name="email" required maxLength={150} /><label htmlFor="password">Temporary password</label><input id="password" type="password" name="password" required minLength={10} /><label htmlFor="role">Role</label><select id="role" name="role"><option value="user">Registered user</option><option value="admin">Administrator</option></select><button className="button button-primary" disabled={busy}>{busy ? 'Creating account…' : 'Create account'} <ArrowRight size={15} /></button></Form>
    </section><section className="panel"><div className="panel-heading"><div><h2>Existing accounts</h2><p>{users.length} registered accounts</p></div></div><div className="account-list">{users.map(user => <div className="account-row" key={user.id}><span className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</span><span className="account-row-copy"><strong>{user.full_name}</strong><small>{user.email}</small></span><span className="category-tag">{user.role === 'admin' ? 'Administrator' : 'User'}</span></div>)}</div></section></div>
  </>;
}

export function AdminReferencesPage() {
  const documents = useLoaderData() as DocumentRecord[];
  return <>
    <PageHeading eyebrow="ADMINISTRATION" title="Reference repository" description="Manage the documents used as comparison sources." action={<Link className="button button-primary" to="/app/admin/references/new"><Plus size={16} /> Add reference</Link>} />
    <section className="panel">{documents.length ? <DocumentTable documents={documents} /> : <EmptyState title="The repository is empty" description="Add reference documents so submissions can be compared against them." action={<Link className="button button-primary" to="/app/admin/references/new">Add first reference</Link>} />}</section>
    <Notice tone="info">Only administrator-curated reference documents are used as comparison sources. Users' private submissions are not automatically added to the repository.</Notice>
  </>;
}

export function AdminUploadReferencePage() {
  const actionData = useActionData() as { error?: string } | undefined;
  const navigation = useNavigation();
  const busy = navigation.state === 'submitting';
  return <>
    <PageHeading eyebrow="REFERENCE REPOSITORY" title="Add reference document" description="Add a source document to the internal comparison repository." />
    <section className="panel form-panel"><div className="panel-heading"><div><h2>Reference document details</h2><p>Uploaded files become available as comparison sources.</p></div><span className="panel-icon"><BookOpen size={18} /></span></div>
      {actionData?.error && <Notice tone="danger">{actionData.error}</Notice>}
      <Form method="post" encType="multipart/form-data" className="form-stack"><label htmlFor="title">Document title <span>Optional</span></label><input id="title" name="title" maxLength={255} placeholder="e.g. Department research handbook" /><label htmlFor="document">Select reference document</label><input id="document" name="document" type="file" accept=".pdf,.docx,.txt" required /><div className="form-hint">Supported formats: PDF, DOCX and TXT. Maximum upload size: 15 MB.</div><div className="form-actions"><button className="button button-primary" disabled={busy}>{busy ? 'Adding document…' : 'Add to repository'} <ArrowRight size={15} /></button><Link className="button button-secondary" to="/app/admin/references">Cancel</Link></div></Form>
    </section>
  </>;
}
