import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import ApplicationsPage from './ApplicationsPage';
import ApplicationFormPage from './ApplicationFormPage';

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ user: { role: 'Administrator', permissions: ['view', 'create', 'edit', 'administer'], portfolioAccess: [] } }),
}));

const application = {
  id: 'app-1', name: 'Payments service from API', description: 'Source record description', portfolioId: 'portfolio-1',
  portfolioName: 'Payments portfolio', productArea: 'Payments', businessOwner: 'Business team', technologyOwner: 'Platform team',
  etsOwner: 'Quality office', criticality: 'Critical', tier: 1, lifecycleStatus: 'Active', technologyStack: 'Python',
  repositoryLink: null, pipelineLink: null, applicationHealthScore: 91, qualityScore: 89, automationCoverage: 84,
  unitTestCoverage: 78, openDefects: 3, openCriticalDefects: 1, riskLevel: 'High',
};

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ApplicationsPage', () => {
  it('renders the required list columns from the API and attaches the session bearer token', async () => {
    sessionStorage.setItem('ketsip.auth.token', 'app-test-token');
    const fetchMock = vi.fn().mockResolvedValue(respond({ items: [application], page: 1, pageSize: 25, total: 1 }));
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter initialEntries={['/applications']}>
        <Routes><Route path="/applications" element={<ApplicationsPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('link', { name: 'Payments service from API' })).toHaveAttribute('href', '/applications/app-1');
    for (const value of ['Payments portfolio', 'Critical', '1', 'Active', '91', '84%', '1', 'High']) {
      expect(screen.getAllByRole('cell', { name: value }).length).toBeGreaterThan(0);
    }
    expect(fetchMock).toHaveBeenCalledWith('/api/applications?page=1&pageSize=25', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer app-test-token' }),
    }));
    for (const label of ['Name', 'Portfolio', 'Criticality', 'Tier', 'Lifecycle status', 'Health Score', 'Automation Coverage', 'Open Critical Defects', 'Risk Level']) {
      expect(screen.getByRole('columnheader', { name: label })).toBeInTheDocument();
    }
  });

  it('round-trips search state into the API query and renders the filtered empty state', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const path = String(input);
      return path.includes('search=Absent')
        ? respond({ items: [], page: 1, pageSize: 25, total: 0 })
        : respond({ items: [application], page: 1, pageSize: 25, total: 1 });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter initialEntries={['/applications?criticality=Critical']}>
        <Routes><Route path="/applications" element={<ApplicationsPage />} /></Routes>
      </MemoryRouter>,
    );

    await user.type(await screen.findByLabelText('Search applications'), 'Absent');
    await user.click(screen.getByRole('button', { name: 'Apply search' }));
    expect(await screen.findByRole('status')).toHaveTextContent('No applications match these filters.');
    await waitFor(() => {
      const lastUrl = String(fetchMock.mock.calls.at(-1)?.[0]);
      const query = new URL(lastUrl, 'http://localhost').searchParams;
      expect(query.get('criticality')).toBe('Critical');
      expect(query.get('search')).toBe('Absent');
      expect(query.get('page')).toBe('1');
      expect(query.get('pageSize')).toBe('25');
    });
  });

  it('loads portfolio choices and reports form submission errors accessibly', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).startsWith('/api/portfolios')) {
        return respond({ items: [{ id: 'portfolio-1', name: 'Payments portfolio' }], page: 1, pageSize: 100, total: 1 });
      }
      if (init?.method === 'POST') return respond({ detail: 'An application already uses this name.' }, 409);
      return respond({ items: [application], page: 1, pageSize: 25, total: 1 });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter initialEntries={['/applications/new']}>
        <Routes><Route path="/applications/new" element={<ApplicationFormPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('option', { name: 'Payments portfolio' })).toBeInTheDocument();
    await user.type(screen.getByLabelText('Name'), 'Duplicate application');
    await user.type(screen.getByLabelText('Description'), 'A valid description');
    await user.selectOptions(screen.getByLabelText('Portfolio'), 'portfolio-1');
    await user.type(screen.getByLabelText('Product area'), 'Payments');
    await user.type(screen.getByLabelText('Business owner'), 'Business');
    await user.type(screen.getByLabelText('Technology owner'), 'Engineering');
    await user.type(screen.getByLabelText('ETS owner'), 'Quality');
    await user.type(screen.getByLabelText('Technology stack'), 'Python');
    await user.click(screen.getByRole('button', { name: 'Create application' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('An application already uses this name.');
    expect(fetchMock).toHaveBeenCalledWith('/api/portfolios?page=1&pageSize=100', expect.any(Object));
  });
});
