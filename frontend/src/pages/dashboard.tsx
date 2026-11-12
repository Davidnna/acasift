import type { ReactNode } from 'react';
import { Link, useLoaderData, useRouteLoaderData } from 'react-router-dom';
import { ArrowRight, ArrowUpRight, ClipboardList, FileText, Layers3 } from 'lucide-react';
import { EmptyState, formatDate, Notice, PageHeading, StatusPill } from '../components/ui';
import { DocumentTable } from '../components/document-table';
import type { AppShellData, DashboardData } from '../types';

export function DashboardPage() {
    const data = useLoaderData() as DashboardData;
    const appData = useRouteLoaderData('app') as AppShellData | undefined;
    const activeWorkspace = appData?.activeWorkspace;

    return <>
        <PageHeading
            eyebrow="WORKSPACE OVERVIEW"
            title="Dashboard"
            description={activeWorkspace
                ? 'Track your submissions and requests across the shared workspaces you belong to.'
                : data.my_submission_requests.length
                    ? 'Track submissions and feedback from the requests you have joined.'
                    : 'Join or create a shared workspace to begin collaborating.'}
            action={activeWorkspace
                ? <Link viewTransition className="button button-primary" to="/app/submission-requests"><ClipboardList size={16} /> View requests</Link>
                : data.my_submission_requests.length
                    ? <Link viewTransition className="button button-primary" to="/app/documents"><FileText size={16} /> My submissions</Link>
                    : <Link viewTransition className="button button-primary" to="/app/workspaces"><Layers3 size={16} /> Find a workspace</Link>}
        />

        {!activeWorkspace && !data.my_submission_requests.length && <section className="panel dashboard-workspace-prompt">
            <EmptyState
                title="You are not in a shared workspace yet"
                description="Create a workspace for your group or join one using an invitation link. Documents are submitted through a Submission Request inside a shared workspace."
                action={<Link viewTransition className="button button-primary" to="/app/workspaces">Create or join a workspace</Link>}
            />
        </section>}

        <div className="stats-grid">
            <StatCard label="Your submissions" value={data.stats.submission_count} foot="Documents submitted" icon={<FileText />} />
            <StatCard label="Submission requests" value={data.stats.request_count} foot="Requests you have joined" icon={<ClipboardList />} />
        </div>

        {data.my_submission_requests.length > 0 && <section className="panel dashboard-submission-requests">
            <div className="panel-heading">
                <div><h2>Your submission requests</h2><p>Requests you have joined, including invitations from outside your workspaces.</p></div>
                <span className="result-count">{data.my_submission_requests.length} requests</span>
            </div>
            <div className="activity-list">{data.my_submission_requests.map(item => <Link viewTransition className="activity-item" to={`/app/submission-requests/${item.id}`} key={item.id}>
                <span className="activity-icon"><ClipboardList size={17} /></span>
                <span className="activity-copy"><strong>{item.title}</strong><small>{item.workspace_name || 'Shared workspace'} · {item.submission_count} of your submissions{item.last_submitted_at ? ` · Last submitted ${formatDate(item.last_submitted_at)}` : ''}</small></span>
                <StatusPill value={item.status} />
                <ArrowUpRight size={15} />
            </Link>)}</div>
        </section>}

        <section className="panel">
            <div className="panel-heading">
                <div><h2>Recent submissions</h2><p>Your latest documents submitted through shared requests.</p></div>
                <Link viewTransition to="/app/documents">View all <ArrowRight size={14} /></Link>
            </div>
            {data.recent_submissions.length
                ? <DocumentTable documents={data.recent_submissions} compact />
                : <EmptyState title="No submissions yet" description="When you submit a document through a Submission Request, it will appear here." />}
        </section>

        <Notice tone="info"><strong>Interpretation note:</strong> Similarity results are available only to authorised workspace administrators and assigned reviewers. Members receive submission confirmation and reviewer feedback.</Notice>
    </>;
}

function StatCard({ label, value, foot, icon }: { label: string; value: number; foot: string; icon: ReactNode; }) {
    return <div className="stat-card"><div className="stat-card-top"><span>{label}</span><span className="stat-icon">{icon}</span></div><strong>{value}</strong><small>{foot}</small></div>;
}
