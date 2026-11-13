import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ApplicationDetail } from '../api/applications';
import ApplicationDetailPage from './ApplicationDetailPage';
import ApplicationFormPage from './ApplicationFormPage';

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    user: {
      role: 'Administrator',
      permissions: ['view', 'create', 'edit', 'administer'],
      portfolioAccess: [],
    },
  }),
}));

const portfolio = {
  id: 'portfolio-1',
  name: 'Payments portfolio',
  owner: 'Portfolio lead',
  productArea: 'Payments',
  status: 'Active' as const,
  applicationCount: 1,
  qualityScore: 90,
};

const application: ApplicationDetail = {
  id: 'application-1',
  name: 'Payments platform',
  description: 'Application source description',
  portfolio: { id: portfolio.id, name: portfolio.name },
  productArea: 'Payments',
  businessOwner: 'Payments team',
  technologyOwner: 'Platform team',
  etsOwner: 'Quality team',
  criticality: 'High',
  tier: 1,
  lifecycleStatus: 'Active',
  technologyStack: 'TypeScript',
  repositoryLink: 'https://code.example.test/payments',
  pipelineLink: 'https://ci.example.test/payments',
  applicationHealthScore: 92,
  qualityScore: 90,
  automationCoverage: 85,
  unitTestCoverage: 80,
  openDefects: 2,
  openCriticalDefects: 0,
  riskLevel: 'Medium',
  createdAt: '2025-01-02T10:00:00.000Z',
  updatedAt: '2025-02-03T11:30:00.000Z',
};

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function portfolioPage(): unknown {
  return { items: [portfolio], page: 1, pageSize: 100, total: 1 };
}

function renderForm(initialPath: string): void {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/applications/new" element={<ApplicationFormPage />} />
        <Route path="/applications/:applicationId/edit" element={<ApplicationFormPage />} />
        <Route path="/applications/:applicationId" element={<ApplicationDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillRequiredApplicationFields(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await user.type(screen.getByLabelText('Name'), 'Payments platform');
  await user.type(screen.getByLabelText('Description'), 'Application source description');
  await user.selectOptions(screen.getByLabelText('Portfolio'), portfolio.id);
  await user.type(screen.getByLabelText('Product area'), 'Payments');
  await user.type(screen.getByLabelText('Business owner'), 'Payments team');
  await user.type(screen.getByLabelText('Technology owner'), 'Platform team');
  await user.type(screen.getByLabelText('ETS owner'), 'Quality team');
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ApplicationFormPage', () => {
  it('loads create choices with accessible labels and navigates to the saved application after creation', async () => {
    const user = userEvent.setup();
    let resolvePortfolios!: (response: Response) => void;
    const pendingPortfolios = new Promise<Response>((resolve) => {
      resolvePortfolios = resolve;
    });
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith('/api/portfolios')) return pendingPortfolios;
      if (url === '/api/applications' && init?.method === 'POST') return respond(application, 201);
      if (url === '/api/applications/application-1') return respond(application);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderForm('/applications/new');

    expect(screen.getByRole('status')).toHaveTextContent('Loading application form');
    resolvePortfolios(respond(portfolioPage()));
    expect(await screen.findByRole('form', { name: 'Create application' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Payments portfolio' })).toBeInTheDocument();

    for (const label of [
      'Name', 'Description', 'Portfolio', 'Product area', 'Business owner', 'Technology owner', 'ETS owner',
      'Criticality', 'Tier (1–4)', 'Lifecycle status', 'Risk level', 'Technology stack', 'Repository link',
      'Pipeline link', 'Application health score (0–100)', 'Quality score (0–100)', 'Automation coverage (0–100)',
      'Unit test coverage (0–100)', 'Open defects', 'Open critical defects',
    ]) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
    expect(screen.getByLabelText('Name')).toBeRequired();
    await fillRequiredApplicationFields(user);
    await user.type(screen.getByLabelText('Technology stack'), 'TypeScript');
    await user.click(screen.getByRole('button', { name: 'Create application' }));

    expect(await screen.findByRole('heading', { name: 'Payments platform' })).toBeInTheDocument();
    expect(await screen.findByRole('status')).toHaveTextContent('Application created successfully.');
    const createRequest = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(createRequest?.[0]).toBe('/api/applications');
    expect(JSON.parse(String(createRequest?.[1]?.body))).toMatchObject({
      name: 'Payments platform',
      portfolioId: 'portfolio-1',
      technologyStack: 'TypeScript',
    });
  });

  it('prepopulates edit fields, updates the record, and navigates to its detail page', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith('/api/portfolios')) return respond(portfolioPage());
      if (url === '/api/applications/application-1' && init?.method === 'PUT') return respond(application);
      if (url === '/api/applications/application-1') return respond(application);
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderForm('/applications/application-1/edit');

    expect(await screen.findByRole('form', { name: 'Edit application' })).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toHaveValue('Payments platform');
    expect(screen.getByLabelText('Portfolio')).toHaveValue('portfolio-1');
    expect(screen.getByLabelText('Technology stack')).toHaveValue('TypeScript');
    await user.clear(screen.getByLabelText('Name'));
    await user.type(screen.getByLabelText('Name'), 'Updated payments platform');
    await user.click(screen.getByRole('button', { name: 'Save application' }));

    expect(await screen.findByRole('heading', { name: 'Payments platform' })).toBeInTheDocument();
    expect(await screen.findByRole('status')).toHaveTextContent('Application updated successfully.');
    const updateRequest = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(updateRequest?.[0]).toBe('/api/applications/application-1');
    expect(JSON.parse(String(updateRequest?.[1]?.body))).toMatchObject({ name: 'Updated payments platform' });
  });

  it('blocks a missing required name and displays server URL validation errors on the related fields', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.startsWith('/api/portfolios')) return respond(portfolioPage());
      if (url === '/api/applications' && init?.method === 'POST') {
        return respond({ detail: 'Repository URL is invalid for this application.' }, 422);
      }
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderForm('/applications/new');
    expect(await screen.findByRole('form', { name: 'Create application' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('Description'), 'Application source description');
    await user.selectOptions(screen.getByLabelText('Portfolio'), portfolio.id);
    await user.type(screen.getByLabelText('Product area'), 'Payments');
    await user.type(screen.getByLabelText('Business owner'), 'Payments team');
    await user.type(screen.getByLabelText('Technology owner'), 'Platform team');
    await user.type(screen.getByLabelText('ETS owner'), 'Quality team');
    await user.click(screen.getByRole('button', { name: 'Create application' }));
    expect(screen.getByLabelText('Name')).toBeRequired();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(0);

    await user.type(screen.getByLabelText('Name'), 'Payments platform');
    await user.type(screen.getByLabelText('Repository link'), 'https://code.example.test/payments');
    await user.click(screen.getByRole('button', { name: 'Create application' }));

    const validationAlerts = await screen.findAllByRole('alert');
    expect(validationAlerts).toHaveLength(3);
    expect(validationAlerts.every((alert) => alert.textContent?.includes('Repository URL is invalid for this application.'))).toBe(true);
    expect(screen.getByLabelText('Repository link')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Repository link')).toHaveAttribute('aria-describedby', 'application-repositoryLink-error');
    expect(screen.getByRole('form', { name: 'Create application' })).toBeInTheDocument();
    expect(screen.getByLabelText('Pipeline link')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Pipeline link')).toHaveAttribute('aria-describedby', 'application-pipelineLink-error');
    expect(screen.getByText('Repository URL is invalid for this application.', { selector: '#application-repositoryLink-error' })).toHaveAttribute('role', 'alert');
    expect(screen.getByText('Repository URL is invalid for this application.', { selector: '#application-pipelineLink-error' })).toHaveAttribute('role', 'alert');
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1);
  });
});
