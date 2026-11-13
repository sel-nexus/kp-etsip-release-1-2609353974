import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getExecutiveDashboard } from '../api/dashboard';
import type { DashboardFilters, ExecutiveDashboard } from '../api/dashboard';

const RISK_LEVELS = ['Low', 'Medium', 'High'] as const;

/** Render read-only executive metrics and URL-shareable dashboard filters. */
export default function DashboardPage(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const portfolioId = searchParams.get('portfolioId') ?? '';
  const productArea = searchParams.get('productArea') ?? '';
  const riskLevel = searchParams.get('riskLevel') ?? '';
  const [productAreaDraft, setProductAreaDraft] = useState(productArea);
  const [result, setResult] = useState<ExecutiveDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError('');
    const filters: DashboardFilters = {
      portfolioId: portfolioId || undefined,
      productArea: productArea || undefined,
      riskLevel: RISK_LEVELS.find((risk) => risk === riskLevel),
    };
    try {
      setResult(await getExecutiveDashboard(filters));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Executive dashboard could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [portfolioId, productArea, riskLevel]);

  useEffect(() => {
    setProductAreaDraft(productArea);
    void load();
  }, [load, productArea]);

  function updateFilter(key: string, value: string): void {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next);
  }

  function applyProductArea(): void {
    updateFilter('productArea', productAreaDraft.trim());
  }

  const metrics = result
    ? [
      { label: 'Enterprise quality', value: result.enterpriseQualityScore === null ? '—' : `${result.enterpriseQualityScore} / 100`, detail: 'Average application quality score' },
      { label: 'Average health', value: result.averageApplicationHealthScore === null ? '—' : `${result.averageApplicationHealthScore} / 100`, detail: 'Application health score' },
      { label: 'Automation maturity', value: result.automationMaturityScore === null ? '—' : `${result.automationMaturityScore}%`, detail: 'Average automation coverage' },
      { label: 'Critical defects', value: String(result.openCriticalDefects), detail: 'Open critical defects' },
      { label: 'Applications at risk', value: String(result.applicationsAtRisk), detail: 'High-risk applications' },
      { label: 'Total applications', value: String(result.totalApplications), detail: 'Applications matching filters' },
      { label: 'Total portfolios', value: String(result.totalPortfolios), detail: 'Visible portfolios' },
    ]
    : [];
  const maxRiskCount = result ? Math.max(1, ...result.portfolioQualityScores.map((item) => item.highRiskApplicationCount)) : 1;

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="dashboard-title">
      <header className="mb-8">
        <p className="mb-2 text-sm font-semibold tracking-wide text-foreground-muted">EXECUTIVE INSIGHTS</p>
        <h1 id="dashboard-title" className="mb-2">Executive dashboard</h1>
        <p className="text-foreground-muted">A source-derived view of application quality, health, automation, and risk.</p>
      </header>

      <form className="quiet-card mb-8 grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-[minmax(12rem,1fr)_minmax(12rem,1fr)_minmax(10rem,0.7fr)] lg:items-end" onSubmit={(event) => { event.preventDefault(); applyProductArea(); }} aria-label="Filter executive dashboard">
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="dashboard-portfolio">Portfolio</label>
          <select id="dashboard-portfolio" value={portfolioId} onChange={(event) => updateFilter('portfolioId', event.currentTarget.value)}>
            <option value="">All visible portfolios</option>
            {(result?.portfolioQualityScores ?? []).map((portfolio) => (
              <option key={portfolio.portfolioId} value={portfolio.portfolioId}>{portfolio.portfolioName}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="dashboard-product-area">Product area</label>
          <input id="dashboard-product-area" value={productAreaDraft} maxLength={120} onChange={(event) => setProductAreaDraft(event.currentTarget.value)} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="dashboard-risk-level">Risk level</label>
          <select id="dashboard-risk-level" value={riskLevel} onChange={(event) => updateFilter('riskLevel', event.currentTarget.value)}>
            <option value="">All risk levels</option>
            {RISK_LEVELS.map((risk) => <option key={risk} value={risk}>{risk}</option>)}
          </select>
        </div>
        <button className="primary-button sm:col-span-2 lg:col-span-3 lg:justify-self-start" type="submit">Apply filters</button>
      </form>

      {loading && (
        <p className="mb-6 text-foreground-muted" role="status" aria-live="polite">Loading executive dashboard…</p>
      )}
      {error && (
        <div className="mb-6" role="alert">
          <p className="mb-3 text-error">{error}</p>
          <button className="secondary-button" type="button" onClick={() => void load()}>Retry</button>
        </div>
      )}

      {!error && result && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Executive metrics">
            {metrics.map((metric) => (
              <article className="quiet-card min-h-32 p-5" key={metric.label}>
                <h2 className="mb-3 text-sm font-semibold text-foreground-muted">{metric.label}</h2>
                <p className="mb-1 text-3xl font-semibold tabular-nums">{metric.value}</p>
                <p className="mb-0 text-sm text-foreground-muted">{metric.detail}</p>
              </article>
            ))}
          </div>

          {!loading && result.totalApplications === 0 && (
            <p className="py-8 text-foreground-muted" role="status">No applications match these filters.</p>
          )}

          <section className="mt-10" aria-labelledby="portfolio-comparison-title">
            <header className="mb-5">
              <h2 id="portfolio-comparison-title" className="mb-2 text-xl font-semibold">Portfolio quality and risk</h2>
              <p className="text-foreground-muted">Filtered application averages and high-risk counts across visible portfolios.</p>
            </header>
            {result.portfolioQualityScores.length === 0 ? (
              <p className="py-6 text-foreground-muted" role="status">No visible portfolios are available for comparison.</p>
            ) : (
              <ul className="divide-y divide-border border-y border-border" aria-label="Portfolio comparisons">
                {result.portfolioQualityScores.map((portfolio) => (
                  <li className="grid gap-3 py-5 sm:grid-cols-[minmax(10rem,1fr)_minmax(8rem,1.2fr)_minmax(8rem,1fr)] sm:items-center" key={portfolio.portfolioId}>
                    <div>
                      <h3 className="mb-1 font-semibold">{portfolio.portfolioName}</h3>
                    </div>
                    <div>
                      <div className="mb-2 flex justify-between gap-3 text-sm">
                        <span className="text-foreground-muted">Quality</span>
                        <span className="font-semibold tabular-nums">{portfolio.qualityScore === null ? 'No score' : `${portfolio.qualityScore} / 100`}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-sm bg-surface-container-high" role="img" aria-label={`${portfolio.portfolioName} quality ${portfolio.qualityScore ?? 'unavailable'} out of 100`}>
                        <span className="block h-full bg-primary" style={{ width: `${portfolio.qualityScore ?? 0}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="mb-2 flex justify-between gap-3 text-sm">
                        <span className="text-foreground-muted">High-risk applications</span>
                        <span className="font-semibold tabular-nums">{portfolio.highRiskApplicationCount}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-sm bg-surface-container-high" role="img" aria-label={`${portfolio.portfolioName} high-risk applications ${portfolio.highRiskApplicationCount}`}>
                        <span className="block h-full bg-secondary" style={{ width: `${(portfolio.highRiskApplicationCount / maxRiskCount) * 100}%` }} />
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  );
}
