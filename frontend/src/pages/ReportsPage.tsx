import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import {
  downloadCsv,
  fetchApplicationReportCsv,
  fetchPortfolioReportCsv,
  listApplicationReport,
  listPortfolioReport,
} from '../api/reports';
import type {
  ApplicationReportFilters,
  ApplicationReportRow,
  PortfolioReportFilters,
  PortfolioReportRow,
  ReportPage,
} from '../api/reports';

const PAGE_SIZE = 25;

/** Render two bounded, permission-scoped report tables and explicit CSV exports. */
export default function ReportsPage(): JSX.Element {
  const [search, setSearch] = useState('');
  const [searchDraft, setSearchDraft] = useState('');
  const [applicationRisk, setApplicationRisk] = useState('');
  const [portfolioStatus, setPortfolioStatus] = useState('');
  const [applicationPage, setApplicationPage] = useState(1);
  const [portfolioPage, setPortfolioPage] = useState(1);
  const [applications, setApplications] = useState<ReportPage<ApplicationReportRow> | null>(null);
  const [portfolios, setPortfolios] = useState<ReportPage<PortfolioReportRow> | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<'applications' | 'portfolios' | null>(null);
  const [error, setError] = useState('');
  const [exportError, setExportError] = useState('');

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError('');
    const applicationFilters: ApplicationReportFilters = {
      search: search || undefined,
      riskLevel: (applicationRisk || undefined) as ApplicationReportFilters['riskLevel'],
      page: applicationPage,
      pageSize: PAGE_SIZE,
    };
    const portfolioFilters: PortfolioReportFilters = {
      search: search || undefined,
      status: (portfolioStatus || undefined) as PortfolioReportFilters['status'],
      page: portfolioPage,
      pageSize: PAGE_SIZE,
    };
    try {
      const [applicationResult, portfolioResult] = await Promise.all([
        listApplicationReport(applicationFilters),
        listPortfolioReport(portfolioFilters),
      ]);
      setApplications(applicationResult);
      setPortfolios(portfolioResult);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Reports could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [applicationPage, applicationRisk, portfolioPage, portfolioStatus, search]);

  useEffect(() => {
    void load();
  }, [load]);

  function applySearch(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setSearch(searchDraft.trim());
    setApplicationPage(1);
    setPortfolioPage(1);
  }

  async function exportReport(kind: 'applications' | 'portfolios'): Promise<void> {
    setExporting(kind);
    setExportError('');
    try {
      const filters = kind === 'applications'
        ? await fetchApplicationReportCsv({
          search: search || undefined,
          riskLevel: (applicationRisk || undefined) as ApplicationReportFilters['riskLevel'],
        })
        : await fetchPortfolioReportCsv({
          search: search || undefined,
          status: (portfolioStatus || undefined) as PortfolioReportFilters['status'],
        });
      downloadCsv(filters);
    } catch (reason) {
      setExportError(reason instanceof Error ? reason.message : 'The CSV download could not be completed.');
    } finally {
      setExporting(null);
    }
  }

  function changeApplicationPage(nextPage: number): void {
    setApplicationPage(Math.max(1, nextPage));
  }

  function changePortfolioPage(nextPage: number): void {
    setPortfolioPage(Math.max(1, nextPage));
  }

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="reports-title">
      <header className="mb-8">
        <p className="mb-2 text-sm font-semibold tracking-wide text-foreground-muted">DATA EXPORTS</p>
        <h1 id="reports-title" className="mb-2">Reports</h1>
        <p className="text-foreground-muted">Review visible portfolio and application records, then export a CSV when needed.</p>
      </header>

      <form className="quiet-card mb-8 grid gap-4 p-5 sm:grid-cols-[minmax(12rem,1fr)_auto] sm:items-end" onSubmit={applySearch} aria-label="Search reports">
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="reports-search">Search reports</label>
          <input id="reports-search" type="search" value={searchDraft} onChange={(event) => setSearchDraft(event.currentTarget.value)} />
        </div>
        <button className="primary-button" type="submit">Apply search</button>
      </form>

      {loading && <p className="mb-4 text-foreground-muted" role="status" aria-live="polite">Loading reports…</p>}
      {error && (
        <div className="mb-6" role="alert">
          <p className="mb-3 text-error">{error}</p>
          <button className="secondary-button" type="button" onClick={() => void load()}>Retry</button>
        </div>
      )}
      {exportError && <p className="mb-6 text-error" role="alert">{exportError}</p>}

      <section className="mb-12" aria-labelledby="application-report-title">
        <header className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="application-report-title" className="mb-1">Applications</h2>
            <p className="text-sm text-foreground-muted">Application inventory fields from the authorized source records.</p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-sm font-semibold" htmlFor="application-risk-filter">Risk level</label>
              <select id="application-risk-filter" value={applicationRisk} onChange={(event) => { setApplicationRisk(event.currentTarget.value); setApplicationPage(1); }}>
                <option value="">All risk levels</option>
                <option>Low</option><option>Medium</option><option>High</option>
              </select>
            </div>
            <button className="secondary-button" type="button" disabled={loading || exporting !== null} onClick={() => void exportReport('applications')}>
              {exporting === 'applications' ? 'Preparing CSV…' : 'Export applications CSV'}
            </button>
          </div>
        </header>
        {!loading && !error && applications?.items.length === 0 && <p className="py-5 text-foreground-muted" role="status">No applications match these filters.</p>}
        {!error && applications && applications.items.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <caption className="mb-3 text-left text-sm text-foreground-muted">Application report ({applications.total})</caption>
                <thead><tr>
                  <th className="px-3 py-3" scope="col">Name</th>
                  <th className="px-3 py-3" scope="col">Portfolio</th>
                  <th className="px-3 py-3" scope="col">Product area</th>
                  <th className="px-3 py-3" scope="col">Criticality</th>
                  <th className="px-3 py-3" scope="col">Lifecycle status</th>
                  <th className="px-3 py-3" scope="col">Health score</th>
                  <th className="px-3 py-3" scope="col">Risk level</th>
                </tr></thead>
                <tbody>{applications.items.map((row) => (
                  <tr key={row.id}>
                    <td className="px-3 py-4">{row.name}</td>
                    <td className="px-3 py-4">{row.portfolioName}</td>
                    <td className="px-3 py-4">{row.productArea}</td>
                    <td className="px-3 py-4">{row.criticality}</td>
                    <td className="px-3 py-4">{row.lifecycleStatus}</td>
                    <td className="px-3 py-4 tabular-nums">{row.applicationHealthScore}</td>
                    <td className="px-3 py-4">{row.riskLevel}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <nav className="mt-4 flex items-center justify-between gap-4" aria-label="Application report pages">
              <span className="text-sm text-foreground-muted">Page {applications.page} of {Math.max(1, Math.ceil(applications.total / applications.pageSize))}</span>
              <div className="flex gap-2">
                <button className="secondary-button" type="button" disabled={loading || applications.page <= 1} onClick={() => changeApplicationPage(applications.page - 1)}>Previous</button>
                <button className="secondary-button" type="button" disabled={loading || applications.page * applications.pageSize >= applications.total} onClick={() => changeApplicationPage(applications.page + 1)}>Next</button>
              </div>
            </nav>
          </>
        )}
      </section>

      <section aria-labelledby="portfolio-report-title">
        <header className="mb-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 id="portfolio-report-title" className="mb-1">Portfolios</h2>
            <p className="text-sm text-foreground-muted">Portfolio ownership and source-derived application rollups.</p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="mb-1 block text-sm font-semibold" htmlFor="portfolio-status-filter">Status</label>
              <select id="portfolio-status-filter" value={portfolioStatus} onChange={(event) => { setPortfolioStatus(event.currentTarget.value); setPortfolioPage(1); }}>
                <option value="">All statuses</option>
                <option>Active</option><option>Archived</option>
              </select>
            </div>
            <button className="secondary-button" type="button" disabled={loading || exporting !== null} onClick={() => void exportReport('portfolios')}>
              {exporting === 'portfolios' ? 'Preparing CSV…' : 'Export portfolios CSV'}
            </button>
          </div>
        </header>
        {!loading && !error && portfolios?.items.length === 0 && <p className="py-5 text-foreground-muted" role="status">No portfolios match these filters.</p>}
        {!error && portfolios && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <caption className="mb-3 text-left text-sm text-foreground-muted">Portfolio report ({portfolios.total})</caption>
                <thead><tr>
                  <th className="px-3 py-3" scope="col">Name</th>
                  <th className="px-3 py-3" scope="col">Owner</th>
                  <th className="px-3 py-3" scope="col">Product area</th>
                  <th className="px-3 py-3 text-right" scope="col">Applications</th>
                  <th className="px-3 py-3" scope="col">Quality score</th>
                  <th className="px-3 py-3" scope="col">Status</th>
                </tr></thead>
                <tbody>{portfolios.items.map((row) => (
                  <tr key={row.id}>
                    <td className="px-3 py-4">{row.name}</td>
                    <td className="px-3 py-4">{row.owner}</td>
                    <td className="px-3 py-4">{row.productArea}</td>
                    <td className="px-3 py-4 text-right tabular-nums">{row.applicationCount}</td>
                    <td className="px-3 py-4">{row.qualityScore === null ? 'No quality score' : `${row.qualityScore.toFixed(1)} / 100`}</td>
                    <td className="px-3 py-4">{row.status}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <nav className="mt-4 flex items-center justify-between gap-4" aria-label="Portfolio report pages">
              <span className="text-sm text-foreground-muted">Page {portfolios.page} of {Math.max(1, Math.ceil(portfolios.total / portfolios.pageSize))}</span>
              <div className="flex gap-2">
                <button className="secondary-button" type="button" disabled={loading || portfolios.page <= 1} onClick={() => changePortfolioPage(portfolios.page - 1)}>Previous</button>
                <button className="secondary-button" type="button" disabled={loading || portfolios.page * portfolios.pageSize >= portfolios.total} onClick={() => changePortfolioPage(portfolios.page + 1)}>Next</button>
              </div>
            </nav>
          </>
        )}
      </section>
    </section>
  );
}
