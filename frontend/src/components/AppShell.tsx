import { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../auth/AuthProvider';

function normalizeRole(role: string | undefined): string {
  return (role ?? '').toLowerCase().replace(/[^a-z]/g, '');
}

/** Provide shared account links and role-aware platform navigation. */
export default function AppShell(): JSX.Element {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, signOut: signOutFromAuth } = useAuth();
  const role = normalizeRole(user?.role);
  const signedIn = Boolean(user);
  const isAdministrator = Boolean(user?.permissions.includes('administer'));
  const canViewAudit = isAdministrator || role.includes('auditor');
  const canViewReports = Boolean(user?.permissions.includes('export'));
  const links = [
    { label: 'Dashboard', to: '/dashboard' },
    { label: 'Portfolios', to: '/portfolios' },
    { label: 'Applications', to: '/applications' },
    ...(canViewReports ? [{ label: 'Reports', to: '/reports' }] : []),
    ...(isAdministrator ? [{ label: 'Administration', to: '/administration' }] : []),
    ...(canViewAudit ? [{ label: 'Audit history', to: '/audit' }] : []),
  ];

  async function signOut(): Promise<void> {
    await signOutFromAuth();
    navigate('/login');
    setMobileMenuOpen(false);
  }

  function navigationLinks(mobile = false): JSX.Element[] {
    return links.map(({ label, to }) => (
      <Link
        key={to}
        aria-current={location.pathname === to || location.pathname.startsWith(`${to}/`) ? 'page' : undefined}
        className="rounded-sm px-2 py-2 text-sm text-foreground hover:bg-surface-container-low"
        onClick={() => mobile && setMobileMenuOpen(false)}
        to={to}
      >
        {label}
      </Link>
    ));
  }

  return (
    <div className="min-h-screen bg-surface text-foreground">
      <header className="border-b border-border bg-surface-container-lowest">
        <div className="mx-auto flex min-h-16 max-w-shell items-center gap-3 px-4 sm:px-6 lg:px-12">
          <Link className="shrink-0 font-semibold tracking-tight text-foreground no-underline" to="/">
            KP ETSIP
          </Link>
          <span className="border-l border-border pl-3 text-sm text-foreground-muted">
            Platform
          </span>
          {signedIn && (
            <>
              <nav aria-label="Main navigation" className="ml-auto hidden items-center gap-1 md:flex">
                {navigationLinks()}
              </nav>
              <nav aria-label="Account navigation" className="hidden items-center gap-1 md:flex">
                <Link className="rounded-sm px-2 py-2 text-sm text-foreground hover:bg-surface-container-low" to="/profile">Profile</Link>
                <button className="rounded-sm px-2 py-2 text-sm text-foreground hover:bg-surface-container-low" onClick={signOut} type="button">Sign out</button>
              </nav>
              <button
                aria-expanded={mobileMenuOpen}
                aria-label={mobileMenuOpen ? 'Close navigation menu' : 'Open navigation menu'}
                className="ml-auto rounded-sm border border-border px-3 py-2 text-sm md:hidden"
                onClick={() => setMobileMenuOpen((open) => !open)}
                type="button"
              >
                Menu
              </button>
            </>
          )}
        </div>
        {signedIn && mobileMenuOpen && (
          <nav aria-label="Mobile navigation" className="grid gap-1 border-t border-border px-4 py-3 md:hidden">
            {navigationLinks(true)}
            <Link className="rounded-sm px-2 py-2 text-sm text-foreground hover:bg-surface-container-low" onClick={() => setMobileMenuOpen(false)} to="/profile">Profile</Link>
            <button className="rounded-sm px-2 py-2 text-left text-sm text-foreground hover:bg-surface-container-low" onClick={signOut} type="button">Sign out</button>
          </nav>
        )}
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
