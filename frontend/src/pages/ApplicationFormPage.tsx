import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { createApplication, getApplication, updateApplication } from '../api/applications';
import type { ApplicationFields, ApplicationCriticality, ApplicationLifecycleStatus, ApplicationRiskLevel } from '../api/applications';
import { listPortfolios } from '../api/portfolios';
import type { Portfolio } from '../api/portfolios';

const initialFields: ApplicationFields = {
  name: '', description: '', portfolioId: '', productArea: '', businessOwner: '', technologyOwner: '', etsOwner: '',
  criticality: 'Medium', tier: 2, lifecycleStatus: 'Active', technologyStack: '', repositoryLink: null, pipelineLink: null,
  applicationHealthScore: 0, qualityScore: 0, automationCoverage: 0, unitTestCoverage: 0,
  openDefects: 0, openCriticalDefects: 0, riskLevel: 'Low',
};

interface TextFieldProps {
  name: keyof ApplicationFields;
  label: string;
  type?: string;
  required?: boolean;
  value: string | number;
  error?: string;
  onChange: (name: keyof ApplicationFields, value: string | number) => void;
}

/** Render a labeled form input with associated field-level validation feedback. */
function TextField({ name, label, type = 'text', required = true, value, error, onChange }: TextFieldProps): JSX.Element {
  const id = `application-${name}`;
  return (
    <div>
      <label className="mb-2 block text-sm font-semibold" htmlFor={id}>{label}</label>
      <input
        id={id}
        name={name}
        type={type}
        value={value}
        required={required}
        aria-required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(name, type === 'number' ? Number(event.currentTarget.value) : event.currentTarget.value)}
      />
      {error && <p className="mt-1 text-sm text-error" id={`${id}-error`} role="alert">{error}</p>}
    </div>
  );
}

/** Create or fully replace an application using scoped portfolio choices. */
export default function ApplicationFormPage(): JSX.Element {
  const { applicationId } = useParams<{ applicationId: string }>();
  const editing = Boolean(applicationId);
  const { user } = useAuth();
  const navigate = useNavigate();
  const [fields, setFields] = useState<ApplicationFields>(initialFields);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [success, setSuccess] = useState('');
  const roleCanWrite = Boolean(user?.permissions.includes(editing ? 'edit' : 'create') && ['Administrator', 'Engineer', 'Portfolio Leader'].includes(user.role));

  useEffect(() => {
    let active = true;
    async function loadForm(): Promise<void> {
      setLoading(true);
      setError('');
      try {
        const [page, existing] = await Promise.all([
          listPortfolios({ page: 1, pageSize: 100 }),
          editing && applicationId ? getApplication(applicationId) : Promise.resolve(null),
        ]);
        if (!active) return;
        setPortfolios(page.items);
        if (existing) {
          setFields({
            name: existing.name, description: existing.description, portfolioId: existing.portfolio.id,
            productArea: existing.productArea, businessOwner: existing.businessOwner, technologyOwner: existing.technologyOwner,
            etsOwner: existing.etsOwner, criticality: existing.criticality, tier: existing.tier,
            lifecycleStatus: existing.lifecycleStatus, technologyStack: existing.technologyStack,
            repositoryLink: existing.repositoryLink, pipelineLink: existing.pipelineLink,
            applicationHealthScore: existing.applicationHealthScore, qualityScore: existing.qualityScore,
            automationCoverage: existing.automationCoverage, unitTestCoverage: existing.unitTestCoverage,
            openDefects: existing.openDefects, openCriticalDefects: existing.openCriticalDefects, riskLevel: existing.riskLevel,
          });
        }
      } catch (reason) {
        if (active) setError(reason instanceof Error ? reason.message : 'Application form data could not be loaded.');
      } finally {
        if (active) setLoading(false);
      }
    }
    void loadForm();
    return () => { active = false; };
  }, [applicationId, editing]);

  function changeField(name: keyof ApplicationFields, value: string | number): void {
    setFields((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => ({ ...current, [name]: '' }));
    setSuccess('');
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    setFieldErrors({});
    setSuccess('');
    const payload: ApplicationFields = {
      ...fields,
      repositoryLink: fields.repositoryLink?.trim() || null,
      pipelineLink: fields.pipelineLink?.trim() || null,
      tier: Number(fields.tier),
      applicationHealthScore: Number(fields.applicationHealthScore),
      qualityScore: Number(fields.qualityScore),
      automationCoverage: Number(fields.automationCoverage),
      unitTestCoverage: Number(fields.unitTestCoverage),
      openDefects: Number(fields.openDefects),
      openCriticalDefects: Number(fields.openCriticalDefects),
    };
    try {
      const saved = editing && applicationId
        ? await updateApplication(applicationId, payload)
        : await createApplication(payload);
      setSuccess(editing ? 'Application updated successfully.' : 'Application created successfully.');
      navigate(`/applications/${encodeURIComponent(saved.id)}`, { state: { success: editing ? 'Application updated successfully.' : 'Application created successfully.' } });
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : 'Application could not be saved.';
      setError(message);
      if (message.toLowerCase().includes('url') || message.toLowerCase().includes('invalid')) {
        setFieldErrors({ repositoryLink: message, pipelineLink: message });
      }
    } finally {
      setSubmitting(false);
    }
  }

  function renderText(name: keyof ApplicationFields, label: string, options: { type?: string; required?: boolean } = {}): JSX.Element {
    const value = fields[name];
    return <TextField name={name} label={label} type={options.type} required={options.required} value={typeof value === 'number' ? value : value ?? ''} error={fieldErrors[name]} onChange={changeField} />;
  }

  function renderSelect<K extends 'criticality' | 'lifecycleStatus' | 'riskLevel'>(name: K, label: string, options: readonly string[]): JSX.Element {
    const id = `application-${name}`;
    return (
      <div>
        <label className="mb-2 block text-sm font-semibold" htmlFor={id}>{label}</label>
        <select id={id} name={name} value={fields[name]} required aria-required="true" aria-invalid={Boolean(fieldErrors[name])} aria-describedby={fieldErrors[name] ? `${id}-error` : undefined} onChange={(event) => changeField(name, event.currentTarget.value)}>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
        {fieldErrors[name] && <p id={`${id}-error`} role="alert">{fieldErrors[name]}</p>}
      </div>
    );
  }

  if (!roleCanWrite) {
    return <section className="mx-auto max-w-shell px-4 py-10" aria-labelledby="application-access-title"><h1 id="application-access-title">Application access unavailable</h1><p role="alert">Your account cannot manage application records.</p><Link to="/applications">Return to applications</Link></section>;
  }

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12" aria-labelledby="application-form-title">
      <p className="mb-3 text-sm font-semibold tracking-wide text-foreground-muted">APPLICATION INVENTORY</p>
      <p className="mb-5"><Link to="/applications">All applications</Link></p>
      <h1 id="application-form-title" className="mb-2">{editing ? 'Edit application' : 'Create application'}</h1>
      <p className="mb-7 text-foreground-muted">Enter the complete application source record. Required fields are marked by the browser form.</p>
      {loading && <p role="status" aria-live="polite">Loading application form…</p>}
      {error && <p className="mb-5 text-error" role="alert">{error}</p>}
      {success && <p className="mb-5" role="status" aria-live="polite">{success}</p>}
      {!loading && !error && (
        <form className="quiet-card grid gap-5 p-5 sm:grid-cols-2 lg:grid-cols-3" onSubmit={(event) => void submit(event)} aria-label={editing ? 'Edit application' : 'Create application'}>
          <div className="sm:col-span-2 lg:col-span-3"><h2 className="mb-0 text-lg font-semibold">Ownership and identity</h2></div>
          {renderText('name', 'Name')}
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="application-portfolioId">Portfolio</label>
            <select id="application-portfolioId" required aria-required="true" aria-invalid={Boolean(fieldErrors.portfolioId)} aria-describedby={fieldErrors.portfolioId ? 'application-portfolioId-error' : undefined} value={fields.portfolioId} onChange={(event) => changeField('portfolioId', event.currentTarget.value)}>
              <option value="">Select a portfolio</option>
              {portfolios.map((portfolio) => <option key={portfolio.id} value={portfolio.id}>{portfolio.name}</option>)}
            </select>
            {fieldErrors.portfolioId && <p id="application-portfolioId-error" role="alert">{fieldErrors.portfolioId}</p>}
          </div>
          {renderText('productArea', 'Product area')}
          {renderText('businessOwner', 'Business owner')}
          {renderText('technologyOwner', 'Technology owner')}
          {renderText('etsOwner', 'ETS owner')}
          <div className="sm:col-span-2 lg:col-span-3">{renderText('description', 'Description')}</div>
          <div className="sm:col-span-2 lg:col-span-3"><h2 className="mb-0 text-lg font-semibold">Classification and technology</h2></div>
          {renderSelect('criticality', 'Criticality', ['Low', 'Medium', 'High', 'Critical'] satisfies ApplicationCriticality[])}
          {renderText('tier', 'Tier (1–4)', { type: 'number' })}
          {renderSelect('lifecycleStatus', 'Lifecycle status', ['Active', 'Deprecated', 'Retired'] satisfies ApplicationLifecycleStatus[])}
          {renderSelect('riskLevel', 'Risk level', ['Low', 'Medium', 'High'] satisfies ApplicationRiskLevel[])}
          {renderText('technologyStack', 'Technology stack', { required: false })}
          {renderText('repositoryLink', 'Repository link', { type: 'url', required: false })}
          {renderText('pipelineLink', 'Pipeline link', { type: 'url', required: false })}
          <div className="sm:col-span-2 lg:col-span-3"><h2 className="mb-0 text-lg font-semibold">Quality and defects</h2></div>
          {renderText('applicationHealthScore', 'Application health score (0–100)', { type: 'number' })}
          {renderText('qualityScore', 'Quality score (0–100)', { type: 'number' })}
          {renderText('automationCoverage', 'Automation coverage (0–100)', { type: 'number' })}
          {renderText('unitTestCoverage', 'Unit test coverage (0–100)', { type: 'number' })}
          {renderText('openDefects', 'Open defects', { type: 'number' })}
          {renderText('openCriticalDefects', 'Open critical defects', { type: 'number' })}
          <div className="sm:col-span-2 lg:col-span-3 flex flex-wrap items-center gap-3 border-t border-border pt-5">
            <button className="primary-button" type="submit" disabled={submitting}>{submitting ? 'Saving…' : editing ? 'Save application' : 'Create application'}</button>
            <Link className="secondary-button inline-flex items-center no-underline" to="/applications">Cancel</Link>
            <span className="sr-only" role="status" aria-live="polite">{submitting ? 'Saving application' : success}</span>
          </div>
        </form>
      )}
    </section>
  );
}
