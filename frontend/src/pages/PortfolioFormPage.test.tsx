import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PortfolioFormPage from './PortfolioFormPage';
import PortfolioDetailPage from './PortfolioDetailPage';
import PortfoliosPage from './PortfoliosPage';

const authForTest = vi.hoisted(() => ({
  user: { role: 'Administrator', permissions: ['view', 'administer'], portfolioAccess: [] as string[] },
}));

vi.mock('../auth/AuthProvider', () => ({
  useAuth: () => ({ user: authForTest.user }),
}));

const portfolio = {
  id: 'portfolio-1',
  name: 'Payments portfolio',
  owner: 'Payments group',
  description: 'Payments investment portfolio',
  productArea: 'Payments',
  status: 'Active' as const,
  applicationCount: 0,
  qualityScore: null,
};

function respond(data: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

function renderRoutes(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/portfolios" element={<PortfoliosPage />} />
        <Route path="/portfolios/new" element={<PortfolioFormPage />} />
        <Route path="/portfolios/:portfolioId/edit" element={<PortfolioFormPage />} />
        <Route path="/portfolios/:portfolioId" element={<PortfolioDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillPortfolioForm(user: ReturnType<typeof userEvent.setup>, name: string): Promise<void> {
  await user.type(screen.getByLabelText('Name'), name);
  await user.type(screen.getByLabelText('Owner'), 'Payments group');
  await user.type(screen.getByLabelText('Description'), 'Payments investment portfolio');
  await user.type(screen.getByLabelText('Product area'), 'Payments');
}

afterEach(() => {
  cleanup();
  authForTest.user = { role: 'Administrator', permissions: ['view', 'administer'], portfolioAccess: [] };
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('PortfolioFormPage', () => {
  it('creates a portfolio with all fields and navigates to its detail page', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/portfolios' && init?.method === 'POST') return respond(portfolio, 201);
      if (String(input) === '/api/portfolios/portfolio-1') return respond(portfolio);
      if (String(input).includes('/applications?')) return respond({ items: [], page: 1, pageSize: 100, total: 0 });
      throw new Error(`Unexpected request: ${String(input)}`);
    });
    vi.stubGlobal('fetch', fetchMock);
    sessionStorage.setItem('ketsip.auth.token', 'test-bearer');

    renderRoutes('/portfolios/new');
    expect(await screen.findByRole('form', { name: 'Create portfolio' })).toBeInTheDocument();
    await fillPortfolioForm(user, 'Payments portfolio');
    await user.selectOptions(screen.getByLabelText('Status'), 'Active');
    await user.click(screen.getByRole('button', { name: 'Create portfolio' }));

    expect(await screen.findByRole('heading', { name: 'Payments portfolio' })).toBeInTheDocument();
    expect(await screen.findByText('Portfolio created successfully.', { selector: 'p' })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST');
    expect(request?.[0]).toBe('/api/portfolios');
    expect(request?.[1]?.headers).toMatchObject({ Authorization: 'Bearer test-bearer' });
    expect(JSON.parse(String(request?.[1]?.body))).toEqual({
      name: 'Payments portfolio', owner: 'Payments group', description: 'Payments investment portfolio',
      productArea: 'Payments', status: 'Active',
    });
  });

  it('displays a failed create response and keeps the rendered form available', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(respond({ detail: 'A portfolio already uses this name.' }, 409));
    vi.stubGlobal('fetch', fetchMock);

    renderRoutes('/portfolios/new');
    expect(await screen.findByRole('form', { name: 'Create portfolio' })).toBeInTheDocument();
    await fillPortfolioForm(user, 'Payments portfolio');
    await user.click(screen.getByRole('button', { name: 'Create portfolio' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('A portfolio already uses this name.');
    expect(screen.getByRole('form', { name: 'Create portfolio' })).toBeInTheDocument();
  });

  it('loads all edit values and updates the portfolio before navigating to its details', async () => {
    const user = userEvent.setup();
    let persistedPortfolio = portfolio;
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/portfolios/portfolio-1' && init?.method === 'PUT') {
        persistedPortfolio = { ...persistedPortfolio, ...JSON.parse(String(init.body)) };
        return respond(persistedPortfolio);
      }
      if (String(input) === '/api/portfolios/portfolio-1') return respond(persistedPortfolio);
      if (String(input).includes('/applications?')) return respond({ items: [], page: 1, pageSize: 100, total: 0 });
      throw new Error(`Unexpected request: ${String(input)}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderRoutes('/portfolios/portfolio-1/edit');
    expect(await screen.findByRole('form', { name: 'Edit portfolio' })).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toHaveValue('Payments portfolio');
    expect(screen.getByLabelText('Owner')).toHaveValue('Payments group');
    expect(screen.getByLabelText('Description')).toHaveValue('Payments investment portfolio');
    expect(screen.getByLabelText('Product area')).toHaveValue('Payments');
    await user.clear(screen.getByLabelText('Name'));
    await user.type(screen.getByLabelText('Name'), 'Payments portfolio updated');
    await user.selectOptions(screen.getByLabelText('Status'), 'Archived');
    await user.click(screen.getByRole('button', { name: 'Save portfolio' }));

    expect(await screen.findByRole('heading', { name: 'Payments portfolio updated' })).toBeInTheDocument();
    expect(await screen.findByText('Portfolio updated successfully.', { selector: 'p' })).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(request?.[0]).toBe('/api/portfolios/portfolio-1');
    expect(JSON.parse(String(request?.[1]?.body))).toMatchObject({ name: 'Payments portfolio updated', status: 'Archived' });
  });

  it('shows an update failure and retries a failed edit load', async () => {
    const user = userEvent.setup();
    let reads = 0;
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) !== '/api/portfolios/portfolio-1') throw new Error(`Unexpected request: ${String(input)}`);
      if (init?.method === 'PUT') return respond({ detail: 'Portfolio update is unavailable.' }, 503);
      reads += 1;
      return reads === 1 ? respond({ detail: 'Portfolio read is unavailable.' }, 503) : respond(portfolio);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderRoutes('/portfolios/portfolio-1/edit');
    expect(await screen.findByRole('alert')).toHaveTextContent('Portfolio read is unavailable.');
    await user.click(screen.getByRole('button', { name: 'Retry loading form' }));
    expect(await screen.findByRole('form', { name: 'Edit portfolio' })).toBeInTheDocument();
    await user.clear(screen.getByLabelText('Name'));
    await user.type(screen.getByLabelText('Name'), 'Changed portfolio');
    await user.click(screen.getByRole('button', { name: 'Save portfolio' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Portfolio update is unavailable.');
    expect(screen.getByRole('form', { name: 'Edit portfolio' })).toBeInTheDocument();
  });
});

describe('PortfolioDetailPage management', () => {
  it('confirms deletion accessibly, deletes through the API, and navigates back', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/portfolios/portfolio-1' && init?.method === 'DELETE') return respond(null, 204);
      if (String(input) === '/api/portfolios/portfolio-1') return respond(portfolio);
      if (String(input).includes('/applications?')) return respond({ items: [], page: 1, pageSize: 100, total: 0 });
      if (String(input).startsWith('/api/portfolios?')) return respond({ items: [], page: 1, pageSize: 25, total: 0 });
      throw new Error(`Unexpected request: ${String(input)}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderRoutes('/portfolios/portfolio-1');
    expect(await screen.findByRole('heading', { name: 'Payments portfolio' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete portfolio' }));
    expect(screen.getByText('Delete portfolio?', { selector: 'h2' })).toBeInTheDocument();
    expect(screen.getByText(/Portfolios with linked applications cannot be deleted/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Confirm delete' }));

    expect(await screen.findByText('No portfolios match these filters.')).toBeInTheDocument();
    expect(await screen.findByText('Portfolio deleted successfully.', { selector: 'p' })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url) === '/api/portfolios/portfolio-1' && init?.method === 'DELETE')).toBe(true);
  });

  it('shows backend 409 feedback for a linked portfolio and allows cancelling confirmation', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input) === '/api/portfolios/portfolio-1' && init?.method === 'DELETE') {
        return respond({ detail: 'Portfolio has linked applications and cannot be deleted.' }, 409);
      }
      if (String(input) === '/api/portfolios/portfolio-1') return respond(portfolio);
      if (String(input).includes('/applications?')) return respond({ items: [], page: 1, pageSize: 100, total: 0 });
      throw new Error(`Unexpected request: ${String(input)}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    renderRoutes('/portfolios/portfolio-1');
    expect(await screen.findByRole('heading', { name: 'Payments portfolio' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete portfolio' }));
    await user.click(screen.getByRole('button', { name: 'Confirm delete' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('This portfolio cannot be deleted because it has linked applications.');
    expect(screen.queryByRole('button', { name: 'Confirm delete' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete portfolio' }));
    await user.click(screen.getByRole('button', { name: 'Cancel deletion' }));
    expect(screen.queryByText('Delete portfolio?', { selector: 'h2' })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url) === '/api/portfolios/portfolio-1' && init?.method === 'DELETE')).toBe(true);
  });
});

it('hides portfolio management controls when an administrator lacks administer permission', async () => {
  authForTest.user = { role: 'Administrator', permissions: ['view'], portfolioAccess: [] };
  const fetchMock = vi.fn().mockResolvedValue(respond({ items: [portfolio], page: 1, pageSize: 25, total: 1 }));
  vi.stubGlobal('fetch', fetchMock);

  renderRoutes('/portfolios');

  expect(await screen.findByRole('link', { name: 'Payments portfolio' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Create portfolio' })).not.toBeInTheDocument();
});

it('hides detail actions and denies direct form access when the role is not Administrator', async () => {
  authForTest.user = { role: 'Portfolio Leader', permissions: ['view', 'administer'], portfolioAccess: [] };
  const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    if (String(input) === '/api/portfolios/portfolio-1') return respond(portfolio);
    if (String(input).includes('/applications?')) return respond({ items: [], page: 1, pageSize: 100, total: 0 });
    throw new Error(`Unexpected request: ${String(input)}`);
  });
  vi.stubGlobal('fetch', fetchMock);

  renderRoutes('/portfolios/portfolio-1');
  expect(await screen.findByRole('heading', { name: 'Payments portfolio' })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: 'Edit portfolio' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Delete portfolio' })).not.toBeInTheDocument();

  cleanup();
  renderRoutes('/portfolios/new');
  expect(await screen.findByRole('heading', { name: 'Portfolio access unavailable' })).toBeInTheDocument();
  expect(screen.queryByRole('form', { name: 'Create portfolio' })).not.toBeInTheDocument();
});
