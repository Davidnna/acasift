import { useFetcher, useLoaderData, useNavigation, useRouteError, Outlet, NavLink, Link, useLocation } from 'react-router-dom';
import {
  Activity, ArrowUpRight, BookOpen, ChevronDown, CircleHelp, FileCheck2,
  FileSearch, Files, Gauge, HelpCircle, LayoutDashboard, LogOut, Menu,
  Settings2, ShieldCheck, Upload, Users, X, ArrowUp,
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { User } from '../types';

function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link viewTransition to="/" className={`brand ${inverse ? 'brand-inverse' : ''}`} aria-label="AcaSift home">
      <span className="brand-mark"><FileSearch size={22} strokeWidth={2.2} /></span>
      <span className="brand-word">AcaSift<span>Academic similarity analysis</span></span>
    </Link>
  );
}

function animateWindowScroll(targetY: number): () => void {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const startY = window.scrollY || document.documentElement.scrollTop;
  const maxY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
  const endY = Math.max(0, Math.min(targetY, maxY));
  const distance = endY - startY;

  if (reducedMotion || Math.abs(distance) < 1) {
    window.scrollTo({ top: endY, left: 0, behavior: 'auto' });
    return () => undefined;
  }

  // A controlled animation is more consistent than relying on browser-specific
  // native smooth-scroll timing, especially on long pages and mobile devices.
  const duration = Math.min(1050, Math.max(560, Math.abs(distance) * 0.42));
  let frameId = 0;
  let startTime = 0;
  let cancelled = false;

  const cleanup = () => {
    if (frameId) cancelAnimationFrame(frameId);
    window.removeEventListener('wheel', cancel, { capture: true });
    window.removeEventListener('touchstart', cancel, { capture: true });
    window.removeEventListener('pointerdown', cancel, { capture: true });
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
    if (!startTime) startTime = now;

    const progress = Math.min(1, (now - startTime) / duration);
    // Ease-in-out cubic: gradual acceleration and deceleration at both ends.
    const eased = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;

    window.scrollTo({ top: startY + distance * eased, left: 0, behavior: 'auto' });

    if (progress < 1) {
      frameId = requestAnimationFrame(tick);
    } else {
      window.scrollTo({ top: endY, left: 0, behavior: 'auto' });
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

  useEffect(() => {
    cancelScroll.current?.();

    if (location.hash) {
      const targetId = decodeURIComponent(location.hash.slice(1));
      const target = document.getElementById(targetId);
      if (target) {
        cancelScroll.current = animateWindowScroll(target.getBoundingClientRect().top + window.scrollY);
        return () => cancelScroll.current?.();
      }
    }

    cancelScroll.current = animateWindowScroll(0);
    return () => cancelScroll.current?.();
  }, [location.key, location.hash]);

  return <>
    {navigation.state !== 'idle' && <div className="navigation-progress"><span /></div>}
    <div key={location.key} className="route-transition">
      <Outlet />
    </div>
    <ScrollToTopButton />
  </>;
}

export function PublicLayout() {
  const user = useLoaderData() as User | null;
  const [menuOpen, setMenuOpen] = useState(false);
  return <div className="public-shell">
    <header className="public-header">
      <div className="public-header-inner">
        <Brand />
        <button className="mobile-menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle navigation">
          {menuOpen ? <X size={21} /> : <Menu size={21} />}
        </button>
        <nav className={`public-nav ${menuOpen ? 'is-open' : ''}`}>
          <NavLink viewTransition end to="/">Home</NavLink>
          <NavLink viewTransition to="/about">About</NavLink>
          <NavLink viewTransition to="/features">Features</NavLink>
          <NavLink viewTransition to="/how-it-works">How it works</NavLink>
          <NavLink viewTransition to="/faq">FAQ</NavLink>
        </nav>
        <div className="public-actions">
          {user ? <Link viewTransition className="button button-primary" to="/app/dashboard">Open workspace <ArrowUpRight size={15} /></Link> : <>
            <Link viewTransition className="signin-link" to="/login">Sign in</Link>
            <Link viewTransition className="button button-primary" to="/access">Get access <ArrowUpRight size={15} /></Link>
          </>}
        </div>
      </div>
    </header>
    <main><Outlet /></main>
    <PublicFooter />
  </div>;
}

function PublicFooter() {
  return <footer className="public-footer">
    <div className="footer-grid wrap">
      <div className="footer-about"><Brand inverse /><p>Academic document similarity analysis to support careful source review and academic integrity.</p></div>
      <div className="footer-links"><strong>Explore</strong><Link viewTransition to="/about">About AcaSift</Link><Link viewTransition to="/features">Features</Link><Link viewTransition to="/how-it-works">How it works</Link><Link viewTransition to="/faq">Frequently asked questions</Link></div>
      <div className="footer-links"><strong>Workspace</strong><Link viewTransition to="/login">Sign in</Link><Link viewTransition to="/access">How to get access</Link></div>
    </div>
    <div className="footer-bottom wrap"><span>© {new Date().getFullYear()} AcaSift. All rights reserved.</span><span>Similarity indicators support human review; they do not determine misconduct.</span></div>
  </footer>;
}

const workspaceLinks: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/app/dashboard', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/app/documents', label: 'My documents', icon: Files, end: true },
  { to: '/app/documents/new', label: 'Check a document', icon: Upload, end: true },
];
const adminLinks: { to: string; label: string; icon: LucideIcon; end?: boolean }[] = [
  { to: '/app/admin/references', label: 'Reference repository', icon: BookOpen, end: true },
  { to: '/app/admin/references/new', label: 'Add reference', icon: FileCheck2, end: true },
  { to: '/app/admin/users', label: 'Manage users', icon: Users, end: true },
];

export function AppLayout() {
  const user = useLoaderData() as User;
  const fetcher = useFetcher();
  const [mobileNav, setMobileNav] = useState(false);
  const signingOut = fetcher.state !== 'idle';
  return <div className="app-shell">
    <header className="app-topbar">
      <div className="app-topbar-left">
        <button className="mobile-menu-toggle app-menu-toggle" onClick={() => setMobileNav(!mobileNav)} aria-label="Toggle workspace navigation"><Menu size={20} /></button>
        <Brand />
      </div>
      <div className="app-topbar-right">
        <div className="account-chip"><span className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</span><span className="account-details"><strong>{user.full_name}</strong><small>{user.is_admin ? 'Administrator' : 'Registered user'}</small></span><ChevronDown size={15} /></div>
        <fetcher.Form viewTransition method="post" action="/logout"><button className="icon-button signout-button" type="submit" disabled={signingOut} title="Sign out"><LogOut size={17} /><span>Sign out</span></button></fetcher.Form>
      </div>
    </header>
    <div className="workspace-frame">
      <aside className={`workspace-sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="sidebar-label">WORKSPACE</div>
        {workspaceLinks.map(item => <NavLink viewTransition key={item.to} to={item.to} end={item.end} onClick={() => setMobileNav(false)} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}><item.icon size={17} /><span>{item.label}</span></NavLink>)}
        {user.is_admin && <>
          <div className="sidebar-label sidebar-label-spaced">ADMINISTRATION</div>
          {adminLinks.map(item => <NavLink viewTransition key={item.to} to={item.to} onClick={() => setMobileNav(false)} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}><item.icon size={17} /><span>{item.label}</span></NavLink>)}
        </>}
        <div className="sidebar-bottom-note"><ShieldCheck size={17} /><p>Similarity results are indicators for review, not automatic findings of academic misconduct.</p></div>
        <Link viewTransition to="/faq" className="sidebar-help"><CircleHelp size={16} /> Help and guidance</Link>
      </aside>
      {mobileNav && <button className="sidebar-backdrop" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
      <main className="workspace-main"><Outlet /></main>
    </div>
  </div>;
}

export function AdminLayout() {
  return <Outlet />;
}

export function RouteErrorBoundary() {
  const error = useRouteError();
  const message = error instanceof Error ? error.message : 'An unexpected error occurred.';
  return <div className="route-error"><div className="error-symbol"><Activity size={24} /></div><p className="eyebrow">SOMETHING WENT WRONG</p><h1>We couldn't load this page.</h1><p>{message}</p><div className="button-row"><Link viewTransition className="button button-primary" to="/">Return home</Link><button className="button button-secondary" onClick={() => window.location.reload()}>Try again</button></div></div>;
}

export function NotFoundPage() {
  return <div className="route-error"><div className="eyebrow">404 · PAGE NOT FOUND</div><h1>This page isn't here.</h1><p>The address may be incorrect or the page may have moved.</p><Link viewTransition className="button button-primary" to="/">Go to AcaSift home</Link></div>;
}
