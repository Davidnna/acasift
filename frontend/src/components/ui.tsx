import type { ReactNode } from 'react';
import { AlertCircle, CheckCircle2, Info, LoaderCircle } from 'lucide-react';

export function Eyebrow({ children }: { children: ReactNode; }) {
    return <div className="eyebrow">{children}</div>;
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description?: string; action?: ReactNode; }) {
    return <div className="page-heading"><div><Eyebrow>{eyebrow}</Eyebrow><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className="page-heading-action">{action}</div>}</div>;
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'warning' | 'success' | 'danger'; }) {
    const Icon = tone === 'success' ? CheckCircle2 : tone === 'warning' || tone === 'danger' ? AlertCircle : Info;
    return <div className={`notice notice-${tone}`}><Icon size={18} /><div>{children}</div></div>;
}

export function StatusPill({ value }: { value: string; }) {
    const normal = value.toLowerCase();
    const tone = normal === 'completed' || normal === 'processed' || normal === 'active' || normal === 'analysed' || normal === 'published' ? 'success' : normal.includes('failed') ? 'danger' : 'neutral';
    return <span className={`status-pill status-${tone}`}>{value}</span>;
}

export function LoadingState({ label = 'Loading your workspace…' }: { label?: string; }) {
    return <div className="loading-state"><LoaderCircle className="spin" size={22} /><span>{label}</span></div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode; }) {
    return <div className="empty-state"><div className="empty-icon"><Info size={22} /></div><h3>{title}</h3><p>{description}</p>{action}</div>;
}

export function formatDate(value?: string | null) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric' }).format(date);
}

export function formatDateTime(value?: string | null) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '—';
    return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date);
}
