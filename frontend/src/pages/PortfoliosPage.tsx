import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { listPortfolios } from '../api/portfolios';
import type { Portfolio, PortfolioPage as PortfolioPageResponse, PortfolioStatus } from '../api/portfolios';
import { formatQualityScore } from '../api/portfolios';

const PAGE_SIZE = 25;

/** Render a shareable, permission-scoped portfolio inventory table. */
export default function PortfoliosPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const search = searchParams.get('search') ?? '';
  const status = searchParams.get('status') ?? '';
  const productArea = searchParams.get('productArea') ?? '';
  const page = Number(searchParams.get('page') ?? '1');
  const [searchDraft, setSearchDraft] = useState(search);
  const [areaDraft, setAreaDraft] = useState(productArea);
  const [result, setResult] = useState<PortfolioPageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError('');
    try {
      setResult(await listPortfolios({
        search: search || undefined,
        status: (status || undefined) as PortfolioStatus | undefined,
        productArea: productArea || undefined,
        page,
        pageSize: PAGE_SIZE,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Portfolio inventory could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [page, productArea, search, status]);

  useEffect(() => {
    setSearchDraft(search);
    setAreaDraft(productArea);
    void load();
  }, [load, productArea, search]);

  function applyFilters(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const next = new URLSearchParams();
    if (searchDraft.trim()) next.set('search', searchDraft.trim());
    if (status) next.set('status', status);
    if (areaDraft.trim()) next.set('productArea', areaDraft.trim());
    setSearchParams(next);
  }

  function changeStatus(value: string): void {
    const next = new URLSearchParams(searchParams);
    if (value) next.set('status', value);
    else next.delete('status');
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
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="portfolios-title">
      <header className="mb-8">
        <p className="mb-2 text-sm font-semibold tracking-wide text-foreground-muted">INVENTORY</p>
        <h1 id="portfolios-title" className="mb-2">Portfolios</h1>
        <p className="text-foreground-muted">Review portfolio ownership and application quality rollups.</p>
      </header>

      <form className="quiet-card mb-6 grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-[minmax(12rem,2fr)_minmax(10rem,1fr)_minmax(10rem,1fr)_auto] lg:items-end" onSubmit={applyFilters} aria-label="Filter portfolios">
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-search">Search portfolios</label>
          <input id="portfolio-search" type="search" value={searchDraft} onChange={(event) => setSearchDraft(event.currentTarget.value)} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-status">Status</label>
          <select id="portfolio-status" value={status} onChange={(event) => changeStatus(event.currentTarget.value)}>
            <option value="">All statuses</option>
            <option value="Active">Active</option>
            <option value="Archived">Archived</option>
          </select>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-product-area">Product area</label>
          <input id="portfolio-product-area" value={areaDraft} onChange={(event) => setAreaDraft(event.currentTarget.value)} />
        </div>
        <button className="primary-button" type="submit">Apply filters</button>
      </form>

      {loading && <p className="mb-4 text-foreground-muted" role="status" aria-live="polite">Loading portfolios…</p>}
      {error && (
        <div className="mb-5" role="alert">
          <p className="mb-3 text-error">{error}</p>
          <button className="secondary-button" type="button" onClick={() => void load()}>Retry</button>
        </div>
      )}
      {!loading && !error && result?.items.length === 0 && (
        <p className="py-8 text-foreground-muted" role="status">No portfolios match these filters.</p>
      )}

      {!error && result && result.items.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <caption className="mb-3 text-left text-lg font-semibold">Portfolio inventory ({result.total})</caption>
              <thead>
                <tr>
                  <th className="px-3 py-3" scope="col">Name</th>
                  <th className="px-3 py-3" scope="col">Owner</th>
                  <th className="px-3 py-3" scope="col">Product Area</th>
                  <th className="px-3 py-3 text-right" scope="col">Applications count</th>
                  <th className="px-3 py-3" scope="col">Quality Score</th>
                  <th className="px-3 py-3" scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {result.items.map((portfolio: Portfolio) => (
                  <tr key={portfolio.id}>
                    <td className="px-3 py-4"><Link to={`/portfolios/${encodeURIComponent(portfolio.id)}`}>{portfolio.name}</Link></td>
                    <td className="px-3 py-4">{portfolio.owner}</td>
                    <td className="px-3 py-4">{portfolio.productArea}</td>
                    <td className="px-3 py-4 text-right tabular-nums">{portfolio.applicationCount}</td>
                    <td className="px-3 py-4">{formatQualityScore(portfolio.qualityScore)}</td>
                    <td className="px-3 py-4">{portfolio.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="mt-6 flex items-center justify-between gap-4" aria-label="Portfolio pages">
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
