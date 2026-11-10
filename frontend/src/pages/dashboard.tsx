import type { ReactNode } from 'react';
import { Link, useLoaderData } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, BookOpen, FileSearch, FileText, Plus, ClipboardList } from 'lucide-react';
import { EmptyState, formatDate, Notice, PageHeading, StatusPill } from '../components/ui';
import { DocumentTable } from '../components/document-table';
import type { DashboardData } from '../types';

export function DashboardPage() {
    const data = useLoaderData() as DashboardData;
    return <>
        <PageHeading eyebrow="WORKSPACE OVERVIEW" title="Dashboard" description="Review your documents and inspect text similarity results." action={<Link viewTransition className="button button-primary" to="/app/documents"><Plus size={16} /> Check a document</Link>} />
        <div className="stats-grid">
            <StatCard label="Your documents" value={data.stats.document_count} foot="Uploaded documents" icon={<FileText />} />
            <StatCard label="Comparisons" value={data.stats.comparison_count} foot="Analysis records" icon={<FileSearch />} />
            <StatCard label="Reference repository" value={data.stats.reference_count} foot="Available reference documents" icon={<BookOpen />} />
        </div>
        {data.my_submission_requests && data.my_submission_requests.length > 0 && <section className="panel dashboard-submission-requests">
            <div className="panel-heading"><div><h2>My submission requests</h2><p>Requests you have joined, including invitations from outside your workspaces.</p></div><span className="result-count">{data.my_submission_requests.length} requests</span></div>
            <div className="activity-list">{data.my_submission_requests.map(item => <Link viewTransition className="activity-item" to={`/app/submission-requests/${item.id}`} key={item.id}>
                <span className="activity-icon"><ClipboardList size={17} /></span>
                <span className="activity-copy"><strong>{item.title}</strong><small>{item.workspace_name || 'Shared workspace'} · {item.submission_count} of your submissions{item.last_submitted_at ? ` · Last submitted ${formatDate(item.last_submitted_at)}` : ''}</small></span>
                <StatusPill value={item.status} />
                <ArrowUpRight size={15} />
            </Link>)}</div>
        </section>}
        <div className="dashboard-grid">
            <section className="panel"><div className="panel-heading"><div><h2>Recent documents</h2><p>Your latest uploaded files</p></div><Link viewTransition to="/app/documents">View all <ArrowRight size={14} /></Link></div>
                {data.recent_documents.length ? <DocumentTable documents={data.recent_documents} compact /> : <EmptyState title="No documents yet" description="Upload a document to begin your first comparison." action={<Link viewTransition className="button button-primary" to="/app/documents">Upload a document</Link>} />}
            </section>
            <section className="panel"><div className="panel-heading"><div><h2>Recent comparisons</h2><p>Your latest analysis activity</p></div></div>
                {data.recent_comparisons.length ? <div className="activity-list">{data.recent_comparisons.map(item => <Link viewTransition className="activity-item" to={`/app/comparisons/${item.id}`} key={item.id}><span className="activity-icon"><FileSearch size={17} /></span><span className="activity-copy"><strong>{item.submitted_document.title}</strong><small>Comparison #{item.id} · {formatDate(item.started_at)}</small></span><StatusPill value={item.status} /><ArrowUpRight size={15} /></Link>)}</div> : <EmptyState title="No comparisons yet" description="Completed analyses will appear here." />}
            </section>
        </div>
        <Notice tone="info"><strong>Interpretation note:</strong> A similarity score measures textual overlap. It does not by itself establish plagiarism. Quotations, references and common technical language may also produce matches.</Notice>
    </>;
}

function StatCard({ label, value, foot, icon }: { label: string; value: number; foot: string; icon: ReactNode; }) {
    return <div className="stat-card"><div className="stat-card-top"><span>{label}</span><span className="stat-icon">{icon}</span></div><strong>{value}</strong><small>{foot}</small></div>;
}

