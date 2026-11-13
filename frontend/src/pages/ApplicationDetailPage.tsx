import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { deleteApplication, getApplication } from '../api/applications';
import type { ApplicationDetail } from '../api/applications';

/** Show all source fields and only role-appropriate application actions. */
export default function ApplicationDetailPage(): JSX.Element {
  const { applicationId = '' } = useParams<{ applicationId: string }>();
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const navigationState = location.state as { success?: string } | null;
  const [application, setApplication] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(navigationState?.success ?? '');
  const [deleting, setDeleting] = useState(false);
  const canEdit = Boolean(user?.permissions.includes('edit') && ['Administrator', 'Engineer', 'Portfolio Leader'].includes(user.role) && (user.role === 'Administrator' || user.portfolioAccess.includes(application?.portfolio.id ?? '')));
  const canDelete = Boolean(user?.role === 'Administrator' && user.permissions.includes('administer'));

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setError('');
    try {
      setApplication(await getApplication(applicationId));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Application details could not be loaded.');
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => { void load(); }, [load]);

  async function remove(): Promise<void> {
    if (!application || !window.confirm(`Delete ${application.name}?`)) return;
    setDeleting(true);
    setError('');
    try {
      await deleteApplication(application.id);
      setSuccess('Application deleted successfully.');
      navigate('/applications', { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Application could not be deleted.');
    } finally {
      setDeleting(false);
    }
  }

  function field(label: string, value: ReactNode): JSX.Element {
    return <div key={label}><dt className="text-sm text-foreground-muted">{label}</dt><dd className="break-words">{value ?? 'Not provided'}</dd></div>;
  }

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="application-detail-title">
      <p className="mb-3 text-sm font-semibold tracking-wide text-foreground-muted">APPLICATION INVENTORY</p>
      <p className="mb-5"><Link to="/applications">All applications</Link></p>
      {loading && <p className="py-6 text-foreground-muted" role="status" aria-live="polite">Loading application details…</p>}
      {error && <div className="py-4" role="alert"><p className="mb-3 text-error">{error}</p><button className="secondary-button" type="button" onClick={() => void load()}>Retry</button></div>}
      {success && <p className="py-3" role="status" aria-live="polite">{success}</p>}
      {!loading && !error && application && (
        <>
          <header className="mb-8 flex flex-wrap items-start justify-between gap-4 border-b border-border pb-6">
            <div><h1 id="application-detail-title" className="mb-2">{application.name}</h1><p className="max-w-prose text-foreground-muted">{application.description}</p></div>
            <div className="flex gap-2">
              {canEdit && <Link className="secondary-button inline-flex items-center no-underline" to={`/applications/${encodeURIComponent(application.id)}/edit`}>Edit application</Link>}
              {canDelete && <button className="secondary-button" type="button" disabled={deleting} onClick={() => void remove()}>{deleting ? 'Deleting…' : 'Delete application'}</button>}
            </div>
          </header>
          <section aria-labelledby="application-source-fields">
            <h2 id="application-source-fields" className="mb-5 text-xl font-semibold">Source fields</h2>
            <dl className="grid gap-x-8 gap-y-5 border-t border-border py-5 sm:grid-cols-2 lg:grid-cols-3">
              {field('Portfolio', <Link to={`/portfolios/${encodeURIComponent(application.portfolio.id)}`}>{application.portfolio.name}</Link>)}
              {field('Product area', application.productArea)}
              {field('Business owner', application.businessOwner)}
              {field('Technology owner', application.technologyOwner)}
              {field('ETS owner', application.etsOwner)}
              {field('Criticality', application.criticality)}
              {field('Tier', application.tier)}
              {field('Lifecycle status', application.lifecycleStatus)}
              {field('Technology stack', application.technologyStack)}
              {field('Repository link', application.repositoryLink ? <a href={application.repositoryLink} target="_blank" rel="noreferrer">{application.repositoryLink}</a> : null)}
              {field('Pipeline link', application.pipelineLink ? <a href={application.pipelineLink} target="_blank" rel="noreferrer">{application.pipelineLink}</a> : null)}
              {field('Application health score', application.applicationHealthScore)}
              {field('Quality score', application.qualityScore)}
              {field('Automation coverage', `${application.automationCoverage}%`)}
              {field('Unit test coverage', `${application.unitTestCoverage}%`)}
              {field('Open defects', application.openDefects)}
              {field('Open critical defects', application.openCriticalDefects)}
              {field('Risk level', application.riskLevel)}
              {field('Created at', new Date(application.createdAt).toLocaleString())}
              {field('Updated at', new Date(application.updatedAt).toLocaleString())}
            </dl>
          </section>
        </>
      )}
    </section>
  );
}
