import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ReportsPage from './ReportsPage';

const appPage = {
  items: [{
    id: 'app-1', name: 'Payments service from API', description: 'A source record', portfolioId: 'portfolio-1',
    portfolioName: 'Payments portfolio from API', productArea: 'Payments', businessOwner: 'Payments group',
    technologyOwner: 'Platform group', etsOwner: 'Quality group', criticality: 'High', tier: 1,
    lifecycleStatus: 'Active', technologyStack: 'Python', repositoryLink: null, pipelineLink: null,
    applicationHealthScore: 91, qualityScore: 88, automationCoverage: 84, unitTestCoverage: 75,
    openDefects: 2, openCriticalDefects: 1, riskLevel: 'High',
  }],
  page: 1,
  pageSize: 25,
  total: 1,
};

const portfolioPage = {
  items: [{ id: 'portfolio-1', name: 'Payments portfolio from API', owner: 'Digital Payments', productArea: 'Payments', status: 'Active', applicationCount: 3, qualityScore: 79 }],
  page: 1,
  pageSize: 25,
  total: 1,
};

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}

function renderPage(): void {
  sessionStorage.setItem('ketsip.auth.token', 'reports-test-token');
  render(<ReportsPage />);
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ReportsPage', () => {
  it('renders exactly two report tables from authenticated API rows', async () => {
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => (
      String(input).includes('/applications?') ? jsonResponse(appPage) : jsonResponse(portfolioPage)
    ));
    vi.stubGlobal('fetch', fetchMock);
    renderPage();

    expect(await screen.findByRole('cell', { name: 'Payments service from API' })).toBeInTheDocument();
    expect(screen.getAllByRole('cell', { name: 'Payments portfolio from API' })).toHaveLength(2);
    expect(screen.getAllByRole('table')).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith('/api/reports/applications?page=1&pageSize=25', expect.objectContaining({
      credentials: 'same-origin',
      headers: expect.objectContaining({ Authorization: 'Bearer reports-test-token' }),
    }));
  });

  it('applies independent filters and requests new bounded pages', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => (
      String(input).includes('/applications') ? jsonResponse(appPage) : jsonResponse(portfolioPage)
    ));
    vi.stubGlobal('fetch', fetchMock);
    renderPage();

    await user.type(await screen.findByRole('searchbox', { name: 'Search reports' }), 'Payments');
    await user.click(screen.getByRole('button', { name: 'Apply search' }));
    await user.selectOptions(screen.getByLabelText('Risk level'), 'High');
    await user.selectOptions(screen.getByLabelText('Status'), 'Active');

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/reports/applications?search=Payments&riskLevel=High&page=1&pageSize=25', expect.any(Object));
      expect(fetchMock).toHaveBeenCalledWith('/api/reports/portfolios?search=Payments&status=Active&page=1&pageSize=25', expect.any(Object));
    });
  });

  it('shows empty results and accessible loading state', async () => {
    const finish: Array<() => void> = [];
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => new Promise<Response>((resolve) => {
      finish.push(() => resolve(String(input).includes('/applications')
        ? jsonResponse({ items: [], page: 1, pageSize: 25, total: 0 })
        : jsonResponse({ items: [], page: 1, pageSize: 25, total: 0 })));
    }));
    vi.stubGlobal('fetch', fetchMock);
    renderPage();
    expect(screen.getByRole('status')).toHaveTextContent('Loading reports');
    finish.forEach((resolve) => resolve());
    expect(await screen.findByText('No applications match these filters.')).toBeInTheDocument();
    expect(screen.getByText('No portfolios match these filters.')).toBeInTheDocument();
  });

  it('renders request errors and supports retry', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: 'Report service unavailable.' }, 503))
      .mockResolvedValueOnce(jsonResponse({ detail: 'Report service unavailable.' }, 503))
      .mockResolvedValueOnce(jsonResponse(appPage))
      .mockResolvedValueOnce(jsonResponse(portfolioPage));
    vi.stubGlobal('fetch', fetchMock);
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Report service unavailable.');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByRole('cell', { name: 'Payments service from API' })).toBeInTheDocument();
  });

  it('downloads CSV only on explicit action and reports an export failure', async () => {
    const user = userEvent.setup();
    const createObjectURL = vi.fn().mockReturnValue('blob:report');
    const revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).includes('format=csv')) {
        return new Response('name\r\nPayments\r\n', {
          status: 200,
          headers: { 'Content-Type': 'text/csv; charset=utf-8', 'Content-Disposition': 'attachment; filename="applications.csv"' },
        });
      }
      if (String(input).includes('/applications?')) return jsonResponse(appPage);
      return jsonResponse(portfolioPage);
    });
    vi.stubGlobal('fetch', fetchMock);
    renderPage();
    await screen.findByRole('cell', { name: 'Payments service from API' });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes('format=csv'))).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Export applications CSV' }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));
    expect(fetchMock).toHaveBeenCalledWith('/api/reports/applications?format=csv', expect.objectContaining({
      headers: expect.objectContaining({ Accept: 'text/csv', Authorization: 'Bearer reports-test-token' }),
    }));
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:report');

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => (
      String(input).includes('format=csv')
        ? jsonResponse({ detail: 'Export denied.' }, 403)
        : String(input).includes('/applications?') ? jsonResponse(appPage) : jsonResponse(portfolioPage)
    ));
    await user.click(screen.getByRole('button', { name: 'Export portfolios CSV' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Export denied.');
  });
});
