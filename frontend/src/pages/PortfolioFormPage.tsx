import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { createPortfolio, getPortfolio, updatePortfolio } from '../api/portfolios';
import type { PortfolioFields, PortfolioStatus } from '../api/portfolios';

const initialFields: PortfolioFields = {
  name: '',
  owner: '',
  description: '',
  productArea: '',
  status: 'Active',
};

/** Create or update a portfolio through the authenticated inventory API. */
export default function PortfolioFormPage(): JSX.Element {
  const { portfolioId } = useParams<{ portfolioId: string }>();
  const editing = Boolean(portfolioId);
  const { user } = useAuth();
  const navigate = useNavigate();
  const [fields, setFields] = useState<PortfolioFields>(initialFields);
  const [loading, setLoading] = useState(editing);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [error, setError] = useState('');
  const canManage = Boolean(user?.role === 'Administrator' && user.permissions.includes('administer'));

  useEffect(() => {
    if (!editing || !portfolioId) {
      setLoading(false);
      return;
    }
    let active = true;
    async function loadPortfolio(): Promise<void> {
      setLoading(true);
      setLoadError('');
      try {
        const portfolio = await getPortfolio(portfolioId);
        if (active) {
          setFields({
            name: portfolio.name,
            owner: portfolio.owner,
            description: portfolio.description ?? '',
            productArea: portfolio.productArea,
            status: portfolio.status,
          });
        }
      } catch (reason) {
        if (active) setLoadError(reason instanceof Error ? reason.message : 'Portfolio form could not be loaded.');
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadPortfolio();
    return () => { active = false; };
  }, [editing, loadAttempt, portfolioId]);

  function changeField(name: keyof PortfolioFields, value: string): void {
    setFields((current) => ({ ...current, [name]: value }));
    setError('');
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    const payload: PortfolioFields = {
      name: fields.name.trim(),
      owner: fields.owner.trim(),
      description: fields.description.trim(),
      productArea: fields.productArea.trim(),
      status: fields.status,
    };
    try {
      const saved = editing && portfolioId
        ? await updatePortfolio(portfolioId, payload)
        : await createPortfolio(payload);
      navigate(`/portfolios/${encodeURIComponent(saved.id)}`, {
        state: { success: editing ? 'Portfolio updated successfully.' : 'Portfolio created successfully.' },
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Portfolio could not be saved.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!canManage) {
    return (
      <section className="mx-auto max-w-shell px-4 py-10" aria-labelledby="portfolio-access-title">
        <h1 id="portfolio-access-title">Portfolio access unavailable</h1>
        <p role="alert">Your account cannot manage portfolios.</p>
        <Link to="/portfolios">Return to portfolios</Link>
      </section>
    );
  }

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="portfolio-form-title">
      <p className="mb-3 text-sm font-semibold tracking-wide text-foreground-muted">PORTFOLIO INVENTORY</p>
      <p className="mb-5"><Link to={editing && portfolioId ? `/portfolios/${encodeURIComponent(portfolioId)}` : '/portfolios'}>Cancel</Link></p>
      <h1 id="portfolio-form-title" className="mb-2">{editing ? 'Edit portfolio' : 'Create portfolio'}</h1>
      <p className="mb-7 text-foreground-muted">Enter the portfolio name, ownership, description, product area, and status.</p>
      {loading && <p role="status" aria-live="polite">Loading portfolio form…</p>}
      {loadError && (
        <div className="mb-5">
          <p className="text-error" role="alert">{loadError}</p>
          <button className="secondary-button mt-3" type="button" onClick={() => setLoadAttempt((attempt) => attempt + 1)}>Retry loading form</button>
        </div>
      )}
      {error && <p className="mb-5 text-error" role="alert">{error}</p>}
      {!loading && !loadError && (
        <form className="quiet-card grid gap-5 p-5 sm:grid-cols-2" onSubmit={(event) => void submit(event)} aria-label={editing ? 'Edit portfolio' : 'Create portfolio'}>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-name">Name</label>
            <input id="portfolio-name" name="name" value={fields.name} maxLength={120} required aria-required="true" onChange={(event) => changeField('name', event.currentTarget.value)} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-owner">Owner</label>
            <input id="portfolio-owner" name="owner" value={fields.owner} maxLength={120} required aria-required="true" onChange={(event) => changeField('owner', event.currentTarget.value)} />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-description">Description</label>
            <textarea id="portfolio-description" name="description" value={fields.description} maxLength={1000} required aria-required="true" rows={4} onChange={(event) => changeField('description', event.currentTarget.value)} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-product-area">Product area</label>
            <input id="portfolio-product-area" name="productArea" value={fields.productArea} maxLength={120} required aria-required="true" onChange={(event) => changeField('productArea', event.currentTarget.value)} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="portfolio-status">Status</label>
            <select id="portfolio-status" name="status" value={fields.status} required aria-required="true" onChange={(event) => changeField('status', event.currentTarget.value as PortfolioStatus)}>
              <option value="Active">Active</option>
              <option value="Archived">Archived</option>
            </select>
          </div>
          <div className="sm:col-span-2 flex flex-wrap items-center gap-3 border-t border-border pt-5">
            <button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Saving…' : editing ? 'Save portfolio' : 'Create portfolio'}</button>
            <Link className="secondary-button inline-flex items-center no-underline" to={editing && portfolioId ? `/portfolios/${encodeURIComponent(portfolioId)}` : '/portfolios'}>Cancel</Link>
            <span className="sr-only" role="status" aria-live="polite">{submitting ? 'Saving portfolio' : ''}</span>
          </div>
        </form>
      )}
    </section>
  );
}
