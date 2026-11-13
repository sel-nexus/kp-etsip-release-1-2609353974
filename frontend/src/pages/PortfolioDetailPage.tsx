import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  formatQualityScore,
  getPortfolio,
  listPortfolioApplications,
} from '../api/portfolios';
import type { Portfolio, PortfolioApplication } from '../api/portfolios';

/** Render an accessible portfolio summary and its linked application inventory. */
export default function PortfolioDetailPage(): JSX.Element {
  const { portfolioId = '' } = useParams<{ portfolioId: string }>();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [applications, setApplications] = useState<PortfolioApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (): Promise<void> => {
    if (!portfolioId) {
      setError('Portfolio identifier is missing.');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const [details, linked] = await Promise.all([
        getPortfolio(portfolioId),
        listPortfolioApplications(portfolioId, 1, 100),
      ]);
      setPortfolio(details);
      setApplications(linked.items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Portfolio details could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [portfolioId]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="portfolio-detail-title">
      <p className="mb-3 text-sm font-semibold tracking-wide text-foreground-muted">PORTFOLIO INVENTORY</p>
      <p className="mb-5"><Link to="/portfolios">All portfolios</Link></p>
      {loading && <p className="py-6 text-foreground-muted" role="status" aria-live="polite">Loading portfolio details…</p>}
      {error && (
        <div className="py-4" role="alert">
          <p className="mb-3 text-error">{error}</p>
          <button className="secondary-button" type="button" onClick={() => void load()}>Retry</button>
        </div>
      )}
      {!loading && !error && portfolio && (
        <>
          <header className="mb-8 border-b border-border pb-6">
            <h1 id="portfolio-detail-title" className="mb-2">{portfolio.name}</h1>
            <p className="max-w-prose text-foreground-muted">{portfolio.description}</p>
            <span className="text-sm" role="status">{portfolio.status}</span>
          </header>
          <section className="mb-10" aria-labelledby="portfolio-summary-title">
            <h2 id="portfolio-summary-title" className="mb-4 text-xl font-semibold">Portfolio summary</h2>
            <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-sm text-foreground-muted">Owner</dt><dd>{portfolio.owner}</dd></div>
              <div><dt className="text-sm text-foreground-muted">Product area</dt><dd>{portfolio.productArea}</dd></div>
              <div><dt className="text-sm text-foreground-muted">Applications</dt><dd className="tabular-nums">{portfolio.applicationCount}</dd></div>
              <div><dt className="text-sm text-foreground-muted">Average quality score</dt><dd>{formatQualityScore(portfolio.qualityScore)}</dd></div>
            </dl>
          </section>
          <section aria-labelledby="linked-applications-title">
            <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="linked-applications-title" className="text-xl font-semibold">Linked applications</h2>
              <span className="text-sm text-foreground-muted">{applications.length} shown</span>
            </div>
            {applications.length === 0 ? (
              <p className="py-5 text-foreground-muted" role="status">No applications are linked to this portfolio.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <caption className="sr-only">Applications linked to {portfolio.name}</caption>
                  <thead>
                    <tr>
                      <th className="px-3 py-3" scope="col">Name</th>
                      <th className="px-3 py-3" scope="col">Business Owner</th>
                      <th className="px-3 py-3" scope="col">Criticality</th>
                      <th className="px-3 py-3" scope="col">Lifecycle Status</th>
                      <th className="px-3 py-3" scope="col">Quality Score</th>
                      <th className="px-3 py-3" scope="col">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {applications.map((application) => (
                      <tr key={application.id}>
                        <td className="px-3 py-4"><Link to={`/applications/${encodeURIComponent(application.id)}`}>{application.name}</Link></td>
                        <td className="px-3 py-4">{application.businessOwner}</td>
                        <td className="px-3 py-4">{application.criticality}</td>
                        <td className="px-3 py-4">{application.lifecycleStatus}</td>
                        <td className="px-3 py-4 tabular-nums">{application.qualityScore}</td>
                        <td className="px-3 py-4">{application.riskLevel}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </section>
  );
}
