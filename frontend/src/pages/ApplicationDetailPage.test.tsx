import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import type { ApplicationDetail } from '../api/applications';
import ApplicationDetailPage from './ApplicationDetailPage';

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({
    user: {
      role: 'Engineer',
      permissions: ['view', 'edit'],
      portfolioAccess: ['portfolio-1'],
    },
  }),
}));

const application: ApplicationDetail = {
  id: 'application-1',
  name: 'Payments service from backend',
  description: 'Authoritative source record for payments.',
  portfolio: { id: 'portfolio-1', name: 'Payments portfolio from backend' },
  productArea: 'Payments',
  businessOwner: 'Payments business team',
  technologyOwner: 'Platform engineering',
  etsOwner: 'Quality office',
  criticality: 'Critical',
  tier: 1,
  lifecycleStatus: 'Active',
  technologyStack: 'TypeScript and PostgreSQL',
  repositoryLink: 'https://code.example.test/payments',
  pipelineLink: 'https://ci.example.test/payments',
  applicationHealthScore: 94,
  qualityScore: 91,
  automationCoverage: 86,
  unitTestCoverage: 82,
  openDefects: 3,
  openCriticalDefects: 1,
  riskLevel: 'High',
  createdAt: '2025-01-02T10:00:00.000Z',
  updatedAt: '2025-02-03T11:30:00.000Z',
  internalNotes: 'Sensitive backend-only notes',
  passwordHash: 'must-not-be-rendered',
} as ApplicationDetail;

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function renderDetail(): void {
  render(
    <MemoryRouter initialEntries={['/applications/application-1']}>
      <Routes>
        <Route path="/applications/:applicationId" element={<ApplicationDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ApplicationDetailPage', () => {
  it('shows loading then renders backend source fields and safe portfolio and repository links', async () => {
    let resolveApplication!: (response: Response) => void;
    const pendingResponse = new Promise<Response>((resolve) => {
      resolveApplication = resolve;
    });
    const fetchMock = vi.fn().mockImplementation(() => pendingResponse);
    vi.stubGlobal('fetch', fetchMock);

    renderDetail();

    expect(screen.getByRole('status')).toHaveTextContent('Loading application details');
    resolveApplication(respond(application));

    expect(await screen.findByRole('heading', { name: 'Payments service from backend' })).toBeInTheDocument();
    expect(screen.getByText('Authoritative source record for payments.')).toBeInTheDocument();
    expect(screen.getByText('Payments business team')).toBeInTheDocument();
    expect(screen.getByText('TypeScript and PostgreSQL')).toBeInTheDocument();
    expect(screen.getByText('94')).toBeInTheDocument();
    expect(screen.getByText('86%')).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'Payments portfolio from backend' })).toHaveAttribute('href', '/portfolios/portfolio-1');
    expect(screen.getByRole('link', { name: 'https://code.example.test/payments' })).toHaveAttribute('href', 'https://code.example.test/payments');
    expect(screen.getByRole('link', { name: 'https://code.example.test/payments' })).toHaveAttribute('rel', 'noreferrer');
    expect(screen.getByRole('link', { name: 'https://ci.example.test/payments' })).toHaveAttribute('href', 'https://ci.example.test/payments');
    expect(screen.queryByText('Sensitive backend-only notes')).not.toBeInTheDocument();
    expect(screen.queryByText('must-not-be-rendered')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Edit application' })).toHaveAttribute('href', '/applications/application-1/edit');
  });

  it('shows a backend load error and retries successfully after the user requests it', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(respond({ detail: 'Application record is unavailable.' }, 503))
      .mockResolvedValueOnce(respond(application));
    vi.stubGlobal('fetch', fetchMock);

    renderDetail();

    expect(await screen.findByRole('alert')).toHaveTextContent('Application record is unavailable.');
    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByRole('heading', { name: 'Payments service from backend' })).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
