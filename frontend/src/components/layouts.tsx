import { useFetcher, useLoaderData, useNavigation, useRouteError, Outlet, NavLink, Link, useLocation } from 'react-router-dom';
import {
  Activity, ArrowUpRight, BookOpen, ChevronDown, CircleHelp, FileCheck2,
  FileSearch, Files, Gauge, HelpCircle, LayoutDashboard, LogOut, Menu,
  Settings2, ShieldCheck, Upload, Users, X, ArrowUp,
} from 'lucide-react';
import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import type { User } from '../types';

function Brand({ inverse = false }: { inverse?: boolean }) {
  return (
    <Link to="/" className={`brand ${inverse ? 'brand-inverse' : ''}`} aria-label="AcaSift home">
      <span className="brand-mark"><FileSearch size={22} strokeWidth={2.2} /></span>
      <span className="brand-word">AcaSift<span>Academic similarity analysis</span></span>
    </Link>
  );
}

function ScrollToTopButton() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const updateVisibility = () => setVisible(window.scrollY > 360);
    updateVisibility();
    window.addEventListener('scroll', updateVisibility, { passive: true });
    return () => window.removeEventListener('scroll', updateVisibility);
  }, []);

  const scrollToTop = () => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    window.scrollTo({ top: 0, left: 0, behavior: reduceMotion ? 'auto' : 'smooth' });
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

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (location.hash) {
      const targetId = decodeURIComponent(location.hash.slice(1));
      const target = document.getElementById(targetId);
      if (target) {
        target.scrollIntoView({
          behavior: reduceMotion ? 'auto' : 'smooth',
          block: 'start',
        });
        return;
      }
    }
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: reduceMotion ? 'auto' : 'smooth',
    });
  }, [location.pathname, location.search, location.hash]);

  return <>
    {navigation.state !== 'idle' && <div className="navigation-progress"><span /></div>}
    <div key={location.pathname} className="route-transition">
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
          <NavLink end to="/">Home</NavLink>
          <NavLink to="/about">About</NavLink>
          <NavLink to="/features">Features</NavLink>
          <NavLink to="/how-it-works">How it works</NavLink>
          <NavLink to="/faq">FAQ</NavLink>
        </nav>
        <div className="public-actions">
          {user ? <Link className="button button-primary" to="/app/dashboard">Open workspace <ArrowUpRight size={15} /></Link> : <>
            <Link className="signin-link" to="/login">Sign in</Link>
            <Link className="button button-primary" to="/access">Get access <ArrowUpRight size={15} /></Link>
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
      <div className="footer-links"><strong>Explore</strong><Link to="/about">About AcaSift</Link><Link to="/features">Features</Link><Link to="/how-it-works">How it works</Link><Link to="/faq">Frequently asked questions</Link></div>
      <div className="footer-links"><strong>Workspace</strong><Link to="/login">Sign in</Link><Link to="/access">How to get access</Link><a href="/health">System status</a></div>
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
        <fetcher.Form method="post" action="/logout"><button className="icon-button signout-button" type="submit" disabled={signingOut} title="Sign out"><LogOut size={17} /><span>Sign out</span></button></fetcher.Form>
      </div>
    </header>
    <div className="workspace-frame">
      <aside className={`workspace-sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
        <div className="sidebar-label">WORKSPACE</div>
        {workspaceLinks.map(item => <NavLink key={item.to} to={item.to} end={item.end} onClick={() => setMobileNav(false)} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}><item.icon size={17} /><span>{item.label}</span></NavLink>)}
        {user.is_admin && <>
          <div className="sidebar-label sidebar-label-spaced">ADMINISTRATION</div>
          {adminLinks.map(item => <NavLink key={item.to} to={item.to} onClick={() => setMobileNav(false)} className={({ isActive }) => `sidebar-link ${isActive ? 'active' : ''}`}><item.icon size={17} /><span>{item.label}</span></NavLink>)}
        </>}
        <div className="sidebar-bottom-note"><ShieldCheck size={17} /><p>Similarity results are indicators for review, not automatic findings of academic misconduct.</p></div>
        <Link to="/faq" className="sidebar-help"><CircleHelp size={16} /> Help and guidance</Link>
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
  return <div className="route-error"><div className="error-symbol"><Activity size={24} /></div><p className="eyebrow">SOMETHING WENT WRONG</p><h1>We couldn't load this page.</h1><p>{message}</p><div className="button-row"><Link className="button button-primary" to="/">Return home</Link><button className="button button-secondary" onClick={() => window.location.reload()}>Try again</button></div></div>;
}

export function NotFoundPage() {
  return <div className="route-error"><div className="eyebrow">404 · PAGE NOT FOUND</div><h1>This page isn't here.</h1><p>The address may be incorrect or the page may have moved.</p><Link className="button button-primary" to="/">Go to AcaSift home</Link></div>;
}
