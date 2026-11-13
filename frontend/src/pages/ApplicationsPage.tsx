import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { listApplications } from '../api/applications';
import type { ApplicationCriticality, ApplicationFilters, ApplicationLifecycleStatus, ApplicationPage, ApplicationRiskLevel } from '../api/applications';

const PAGE_SIZE = 25;

/** Render role-scoped applications with URL-shareable search and filter state. */
export default function ApplicationsPage(): JSX.Element {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const portfolioId = searchParams.get('portfolioId') ?? '';
  const criticality = searchParams.get('criticality') ?? '';
  const riskLevel = searchParams.get('riskLevel') ?? '';
  const lifecycleStatus = searchParams.get('lifecycleStatus') ?? '';
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1);
  const [searchDraft, setSearchDraft] = useState(search);
  const [result, setResult] = useState<ApplicationPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const canCreate = Boolean(user?.permissions.includes('create') && ['Administrator', 'Engineer', 'Portfolio Leader'].includes(user.role));

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError('');
    const filters: ApplicationFilters = {
      search: search || undefined,
      portfolioId: portfolioId || undefined,
      criticality: (criticality || undefined) as ApplicationCriticality | undefined,
      riskLevel: (riskLevel || undefined) as ApplicationRiskLevel | undefined,
      lifecycleStatus: (lifecycleStatus || undefined) as ApplicationLifecycleStatus | undefined,
      page,
      pageSize: PAGE_SIZE,
    };
    try {
      setResult(await listApplications(filters));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Application inventory could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [criticality, lifecycleStatus, page, portfolioId, riskLevel, search]);

  useEffect(() => {
    setSearchDraft(search);
    void load();
  }, [load, search]);

  function applyFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const next = new URLSearchParams(searchParams);
    if (searchDraft.trim()) next.set('search', searchDraft.trim());
    else next.delete('search');
    next.delete('page');
    setSearchParams(next);
  }

  function changeFilter(key: string, value: string): void {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    next.delete('page');
    setSearchParams(next);
  }

  function goToPage(nextPage: number): void {
    const next = new URLSearchParams(searchParams);
    if (nextPage > 1) next.set('page', String(nextPage));
    else next.delete('page');
    setSearchParams(next);
  }

  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 1;

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="applications-title">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-sm font-semibold tracking-wide text-foreground-muted">INVENTORY</p>
          <h1 id="applications-title" className="mb-2">Applications</h1>
          <p className="text-foreground-muted">Search and review permission-scoped application records.</p>
        </div>
        {canCreate && <Link className="primary-button inline-flex items-center no-underline" to="/applications/new">Create application</Link>}
      </header>

      <form className="quiet-card mb-6 grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-[minmax(12rem,2fr)_repeat(3,minmax(9rem,1fr))_auto] lg:items-end" onSubmit={applyFilters} aria-label="Filter applications">
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="application-search">Search applications</label>
          <input id="application-search" type="search" value={searchDraft} onChange={(event) => setSearchDraft(event.currentTarget.value)} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="application-criticality">Criticality</label>
          <select id="application-criticality" value={criticality} onChange={(event) => changeFilter('criticality', event.currentTarget.value)}>
            <option value="">All criticality</option>
            <option>Low</option><option>Medium</option><option>High</option><option>Critical</option>
          </select>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="application-lifecycle">Lifecycle status</label>
          <select id="application-lifecycle" value={lifecycleStatus} onChange={(event) => changeFilter('lifecycleStatus', event.currentTarget.value)}>
            <option value="">All statuses</option>
            <option>Active</option><option>Deprecated</option><option>Retired</option>
          </select>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="application-risk">Risk level</label>
          <select id="application-risk" value={riskLevel} onChange={(event) => changeFilter('riskLevel', event.currentTarget.value)}>
            <option value="">All risk levels</option>
            <option>Low</option><option>Medium</option><option>High</option>
          </select>
        </div>
        <button className="primary-button" type="submit">Apply search</button>
      </form>

      {loading && <p className="mb-4 text-foreground-muted" role="status" aria-live="polite">Loading applications…</p>}
      {error && <div className="mb-5" role="alert"><p className="mb-3 text-error">{error}</p><button className="secondary-button" type="button" onClick={() => void load()}>Retry</button></div>}
      {!loading && !error && result?.items.length === 0 && <p className="py-8 text-foreground-muted" role="status">No applications match these filters.</p>}

      {!error && result && result.items.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <caption className="mb-3 text-left text-lg font-semibold">Application inventory ({result.total})</caption>
              <thead>
                <tr>
                  <th className="px-3 py-3" scope="col">Name</th>
                  <th className="px-3 py-3" scope="col">Portfolio</th>
                  <th className="px-3 py-3" scope="col">Criticality</th>
                  <th className="px-3 py-3" scope="col">Tier</th>
                  <th className="px-3 py-3" scope="col">Lifecycle status</th>
                  <th className="px-3 py-3" scope="col">Health Score</th>
                  <th className="px-3 py-3" scope="col">Automation Coverage</th>
                  <th className="px-3 py-3" scope="col">Open Critical Defects</th>
                  <th className="px-3 py-3" scope="col">Risk Level</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((application) => (
                  <tr key={application.id}>
                    <td className="px-3 py-4"><Link to={`/applications/${encodeURIComponent(application.id)}`}>{application.name}</Link></td>
                    <td className="px-3 py-4">{application.portfolioName}</td>
                    <td className="px-3 py-4">{application.criticality}</td>
                    <td className="px-3 py-4 tabular-nums">{application.tier}</td>
                    <td className="px-3 py-4">{application.lifecycleStatus}</td>
                    <td className="px-3 py-4 tabular-nums">{application.applicationHealthScore}</td>
                    <td className="px-3 py-4 tabular-nums">{application.automationCoverage}%</td>
                    <td className="px-3 py-4 tabular-nums">{application.openCriticalDefects}</td>
                    <td className="px-3 py-4">{application.riskLevel}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="mt-6 flex items-center justify-between gap-4" aria-label="Application pages">
            <span className="text-sm text-foreground-muted">Page {result.page} of {totalPages}</span>
            <div className="flex gap-2">
              <button className="secondary-button" type="button" disabled={loading || result.page <= 1} onClick={() => goToPage(result.page - 1)}>Previous</button>
              <button className="secondary-button" type="button" disabled={loading || result.page >= totalPages} onClick={() => goToPage(result.page + 1)}>Next</button>
            </div>
          </nav>
        </>
      )}
    </section>
  );
}
