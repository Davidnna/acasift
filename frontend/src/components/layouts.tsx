import { useFetcher, useLoaderData, useNavigation, Outlet, NavLink, Link, useLocation } from 'react-router-dom';
import {
    Activity, ArrowUpRight, BookOpen, ChevronDown, CircleHelp,
    FileSearch, Files, LayoutDashboard, LogOut, Menu,
    Settings2, ShieldCheck, Users, X, ArrowUp, Layers3, ClipboardList,
} from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { AppShellData, User } from '../types';

function Brand({ inverse = false }: { inverse?: boolean; }) {
    return (
        <Link viewTransition to="/" className={`brand ${inverse ? 'brand-inverse' : ''}`} aria-label="AcaSift home">
            <span className="brand-mark"><FileSearch size={22} strokeWidth={2.2} /></span>
            <span className="brand-word">AcaSift<span>Document similarity analysis</span></span>
        </Link>
    );
}

function animateWindowScroll(targetY: number): () => void {
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const scrollingElement = document.scrollingElement ?? document.documentElement;
    const startY = window.scrollY || scrollingElement.scrollTop;
    const maxY = Math.max(0, scrollingElement.scrollHeight - window.innerHeight);
    const endY = Math.max(0, Math.min(targetY, maxY));
    const distance = endY - startY;

    if (reducedMotion || Math.abs(distance) < 1) {
        scrollingElement.scrollTop = endY;
        return () => undefined;
    }

    // Longer journeys receive proportionally more time. The previous 560–1050ms
    // cap made a full-page return feel abrupt on tall pages.
    const duration = Math.min(2800, Math.max(1050, Math.abs(distance) * 0.78));
    let frameId = 0;
    let startTime: number | null = null;
    let cancelled = false;

    const cleanup = () => {
        if (frameId) cancelAnimationFrame(frameId);
        window.removeEventListener('wheel', cancel, true);
        window.removeEventListener('touchstart', cancel, true);
        window.removeEventListener('pointerdown', cancel, true);
        window.removeEventListener('keydown', cancelForKeyboard);
    };

    const cancel = () => {
        if (cancelled) return;
        cancelled = true;
        cleanup();
    };

    const cancelForKeyboard = (event: KeyboardEvent) => {
        if (['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) {
            cancel();
        }
    };

    window.addEventListener('wheel', cancel, { passive: true, capture: true });
    window.addEventListener('touchstart', cancel, { passive: true, capture: true });
    window.addEventListener('pointerdown', cancel, { passive: true, capture: true });
    window.addEventListener('keydown', cancelForKeyboard);

    const tick = (now: number) => {
        if (cancelled) return;
        if (startTime === null) startTime = now;

        const progress = Math.min(1, (now - startTime) / duration);
        // Sine ease-in-out gives the movement a gentle take-off and landing.
        const eased = -(Math.cos(Math.PI * progress) - 1) / 2;
        scrollingElement.scrollTop = startY + distance * eased;

        if (progress < 1) {
            frameId = requestAnimationFrame(tick);
        } else {
            scrollingElement.scrollTop = endY;
            cancelled = true;
            cleanup();
        }
    };

    frameId = requestAnimationFrame(tick);
    return cancel;
}
function ScrollToTopButton() {
    const [visible, setVisible] = useState(false);
    const cancelScroll = useRef<(() => void) | null>(null);

    useEffect(() => {
        const updateVisibility = () => setVisible(window.scrollY > 360);
        updateVisibility();
        window.addEventListener('scroll', updateVisibility, { passive: true });
        return () => {
            window.removeEventListener('scroll', updateVisibility);
            cancelScroll.current?.();
        };
    }, []);

    const scrollToTop = () => {
        cancelScroll.current?.();
        cancelScroll.current = animateWindowScroll(0);
    };

    return <button
        type="button"
        className={`scroll-top-button ${visible ? 'is-visible' : ''}`}
        onClick={scrollToTop}
        aria-label="Scroll to top"
        title="Scroll to top"
        aria-hidden={!visible}
        tabIndex={visible ? 0 : -1}
    >
        <ArrowUp size={19} strokeWidth={2.4} aria-hidden="true" />
    </button>;
}

export function RootLayout() {
    const navigation = useNavigation();
    const location = useLocation();
    const cancelScroll = useRef<(() => void) | null>(null);

    useLayoutEffect(() => {
        const previousRestoration = window.history.scrollRestoration;
        window.history.scrollRestoration = 'manual';
        return () => {
            window.history.scrollRestoration = previousRestoration;
        };
    }, []);

    useLayoutEffect(() => {
        cancelScroll.current?.();

        // Wait until the destination route has committed before measuring its
        // document height. This avoids racing route rendering and history updates.
        const frameId = requestAnimationFrame(() => {
            if (location.hash) {
                const targetId = decodeURIComponent(location.hash.slice(1));
                const target = document.getElementById(targetId);
                if (target) {
                    const targetY = target.getBoundingClientRect().top + window.scrollY;
                    cancelScroll.current = animateWindowScroll(targetY);
                    target.setAttribute('tabindex', '-1');
                    target.focus({ preventScroll: true });
                    return;
                }
            }

            cancelScroll.current = animateWindowScroll(0);
            const mainContent = document.getElementById('workspace-main')
                || document.getElementById('public-main');
            mainContent?.focus({ preventScroll: true });
        });

        return () => {
            cancelAnimationFrame(frameId);
            cancelScroll.current?.();
        };
    }, [location.key, location.hash]);

    return <>
        {navigation.state !== 'idle' && <div className="navigation-progress" role="status" aria-live="polite" aria-label="Loading page"><span /></div>}
        <div key={location.key} className="route-transition">
            <Outlet />
        </div>
        <ScrollToTopButton />
    </>;
}
export function PublicLayout() {
    const user = useLoaderData() as User | null;
    const [menuOpen, setMenuOpen] = useState(false);
    const menuToggleRef = useRef<HTMLButtonElement>(null);
    const publicNavRef = useRef<HTMLElement>(null);

    useEffect(() => {
        if (!menuOpen) return undefined;
        publicNavRef.current?.querySelector('a')?.focus();
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setMenuOpen(false);
                menuToggleRef.current?.focus();
            }
        };
        document.addEventListener('keydown', closeOnEscape);
        return () => document.removeEventListener('keydown', closeOnEscape);
    }, [menuOpen]);

    return <div className="public-shell">
        <a className="skip-link" href="#public-main">Skip to main content</a>
        <header className="public-header">
            <div className="public-header-inner">
                <Brand />
                <button
                    type="button"
                    className="mobile-menu-toggle"
                    ref={menuToggleRef}
                    onClick={() => setMenuOpen(!menuOpen)}
                    aria-label={menuOpen ? 'Close main navigation' : 'Open main navigation'}
                    aria-expanded={menuOpen}
                    aria-controls="public-navigation"
                >
                    {menuOpen ? <X size={21} aria-hidden="true" /> : <Menu size={21} aria-hidden="true" />}
                </button>
                <nav ref={publicNavRef} id="public-navigation" aria-label="Main navigation" className={`public-nav ${menuOpen ? 'is-open' : ''}`}>
                    <NavLink viewTransition end to="/" onClick={() => setMenuOpen(false)}>Home</NavLink>
                    <NavLink viewTransition to="/about" onClick={() => setMenuOpen(false)}>About</NavLink>
                    <NavLink viewTransition to="/features" onClick={() => setMenuOpen(false)}>Features</NavLink>
                    <NavLink viewTransition to="/how-it-works" onClick={() => setMenuOpen(false)}>How it works</NavLink>
                    <NavLink viewTransition to="/faq" onClick={() => setMenuOpen(false)}>FAQ</NavLink>
                </nav>
                <div className="public-actions">
                    {user ? <Link viewTransition className="button button-primary" to="/app/dashboard">Open workspace <ArrowUpRight size={15} /></Link> : <>
                        <Link viewTransition className="signin-link" to="/login">Sign in</Link>
                        <Link viewTransition className="button button-primary" to="/register">Create account <ArrowUpRight size={15} /></Link>
                    </>}
                </div>
            </div>
        </header>
        <main id="public-main" tabIndex={-1}><Outlet /></main>
        <PublicFooter />
    </div>;
}

function PublicFooter() {
    return <footer className="public-footer">
        <div className="footer-grid wrap">
            <div className="footer-about"><Brand inverse /><p>Document similarity analysis to support careful source review and informed decisions.</p></div>
            <div className="footer-links"><strong>Explore</strong><Link viewTransition to="/about">About AcaSift</Link><Link viewTransition to="/features">Features</Link><Link viewTransition to="/how-it-works">How it works</Link><Link viewTransition to="/faq">Frequently asked questions</Link></div>
            <div className="footer-links"><strong>Workspace</strong><Link viewTransition to="/login">Sign in</Link><Link viewTransition to="/register">Create an account</Link></div>
        </div>
        <div className="footer-bottom wrap"><span>© {new Date().getFullYear()} AcaSift. All rights reserved.</span><span>Similarity indicators support human review; they do not determine misconduct.</span></div>
    </footer>;
}

const baseWorkspaceLinks: { to: string; label: string; icon: LucideIcon; end?: boolean; }[] = [
    { to: '/app/dashboard', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: '/app/documents', label: 'My documents', icon: Files, end: true },
    { to: '/app/account', label: 'My account', icon: Settings2, end: true },
    { to: '/app/workspaces', label: 'Workspaces', icon: Layers3, end: true },
];
const sharedWorkspaceLinks: { to: string; label: string; icon: LucideIcon; end?: boolean; }[] = [
    { to: '/app/submission-requests', label: 'Submission Requests', icon: ClipboardList, end: true },
];
const adminLinks: { to: string; label: string; icon: LucideIcon; end?: boolean; }[] = [
    { to: '/app/admin/references', label: 'Reference repository', icon: BookOpen, end: true },
    { to: '/app/admin/users', label: 'Manage users', icon: Users, end: true },
];

export function AppLayout() {
    const { user, activeWorkspace } = useLoaderData() as AppShellData;
    const fetcher = useFetcher();
    const [mobileNav, setMobileNav] = useState(false);
    const menuToggleRef = useRef<HTMLButtonElement>(null);
    const workspaceNavRef = useRef<HTMLElement>(null);
    const signingOut = fetcher.state !== 'idle';

    useEffect(() => {
        if (!mobileNav) return undefined;
        workspaceNavRef.current?.querySelector('a')?.focus();
        const closeOnEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                setMobileNav(false);
                menuToggleRef.current?.focus();
            }
        };
        document.addEventListener('keydown', closeOnEscape);
        return () => document.removeEventListener('keydown', closeOnEscape);
    }, [mobileNav]);
    const canUseSharedFeatures = activeWorkspace?.type === 'shared';
    const visibleWorkspaceLinks = canUseSharedFeatures
        ? [baseWorkspaceLinks[0], ...sharedWorkspaceLinks, ...baseWorkspaceLinks.slice(1)]
        : baseWorkspaceLinks;
    return <div className="app-shell">
        <a className="skip-link" href="#workspace-main">Skip to main content</a>
        <header className="app-topbar">
            <div className="app-topbar-left">
                <button
                    type="button"
                    className="mobile-menu-toggle app-menu-toggle"
                    ref={menuToggleRef}
                    onClick={() => setMobileNav(!mobileNav)}
                    aria-label={mobileNav ? 'Close workspace navigation' : 'Open workspace navigation'}
                    aria-expanded={mobileNav}
                    aria-controls="workspace-navigation"
                >{mobileNav ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}</button>
                <Brand />
            </div>
            <div className="app-topbar-right">
                <Link viewTransition to="/app/account" className="account-chip" aria-label="Open account settings">
                    <span className="avatar">
                        {user.profile_image_url ? <img src={user.profile_image_url} alt="" /> : (user.first_name?.[0] || user.full_name.slice(0, 1)).toUpperCase()}
                    </span>
                    <span className="account-details"><strong>{user.full_name}</strong><small>{user.is_admin ? 'Platform administrator' : activeWorkspace?.type === 'shared' ? `${activeWorkspace.role === 'owner' ? 'Owner' : activeWorkspace.role === 'admin' ? 'Administrator' : 'Member'} · Shared workspace` : 'Personal workspace'}</small></span>
                    <ChevronDown size={15} aria-hidden="true" />
                </Link>
                <fetcher.Form method="post" action="/logout"><button className="icon-button signout-button" type="submit" disabled={signingOut} title="Sign out" aria-label="Sign out"><LogOut size={17} aria-hidden="true" /><span>Sign out</span></button></fetcher.Form>
            </div>
        </header>
        <div className="workspace-frame">
            <aside className={`workspace-sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
                <nav ref={workspaceNavRef} id="workspace-navigation" className="workspace-sidebar-nav" aria-label="Workspace navigation">
                    <div className="sidebar-label">WORKSPACE</div>
                    {visibleWorkspaceLinks.map(item => <NavLink viewTransition key={item.to} to={item.to} end={item.end} onClick={() => setMobileNav(false)} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}><item.icon size={17} aria-hidden="true" /><span>{item.label}</span></NavLink>)}
                    {user.is_admin && <>
                        <div className="sidebar-label sidebar-label-spaced">ADMINISTRATION</div>
                        {adminLinks.map(item => <NavLink viewTransition key={item.to} to={item.to} onClick={() => setMobileNav(false)} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}><item.icon size={17} aria-hidden="true" /><span>{item.label}</span></NavLink>)}
                    </>}
                </nav>
                <div className="sidebar-bottom-note"><ShieldCheck size={17} aria-hidden="true" /><p>Similarity results are indicators for review, not automatic findings of plagiarism.</p></div>
                <Link viewTransition to="/faq" className="sidebar-help"><CircleHelp size={16} aria-hidden="true" /> Help and guidance</Link>
            </aside>
            {mobileNav && <button type="button" className="sidebar-backdrop" onClick={() => { setMobileNav(false); menuToggleRef.current?.focus(); }} aria-label="Close workspace navigation" />}
            <main id="workspace-main" className="workspace-main" tabIndex={-1}><Outlet /></main>
        </div>
    </div>;
}

export function AdminLayout() {
    return <Outlet />;
}

export function RouteErrorBoundary() {
    return <div className="route-error"><div className="error-symbol"><Activity size={24} /></div><p className="eyebrow">SOMETHING WENT WRONG</p><h1>We couldn't load this page.</h1><p>Please try again. If the problem continues, contact your AcaSift administrator.</p><div className="button-row"><Link viewTransition className="button button-primary" to="/">Return home</Link><button className="button button-secondary" onClick={() => window.location.reload()}>Try again</button></div></div>;
}

export function NotFoundPage() {
    return <div className="route-error"><div className="eyebrow">404 · PAGE NOT FOUND</div><h1>This page isn't here.</h1><p>The address may be incorrect or the page may have moved.</p><Link viewTransition className="button button-primary" to="/">Go to AcaSift home</Link></div>;
}
