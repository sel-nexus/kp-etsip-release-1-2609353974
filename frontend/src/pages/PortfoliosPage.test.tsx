import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import PortfoliosPage from './PortfoliosPage';
import PortfolioDetailPage from './PortfolioDetailPage';

const portfolioResponse = {
  items: [
    {
      id: 'portfolio-1',
      name: 'Payments portfolio from API',
      owner: 'Digital Payments',
      productArea: 'Payments',
      status: 'Active',
      applicationCount: 3,
      qualityScore: 79,
    },
  ],
  page: 1,
  pageSize: 25,
  total: 1,
};

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}

function renderPage(): void {
  sessionStorage.setItem('ketsip.auth.token', 'test-bearer');
  render(
    <MemoryRouter initialEntries={['/portfolios']}>
      <Routes>
        <Route path="/portfolios" element={<PortfoliosPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('PortfoliosPage', () => {
  it('renders real API response fields in the inventory table', async () => {
    const fetchMock = vi.fn().mockResolvedValue(respond(portfolioResponse));
    vi.stubGlobal('fetch', fetchMock);
    renderPage();

    expect(await screen.findByRole('link', { name: 'Payments portfolio from API' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Digital Payments' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Payments' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '3' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '79.0 / 100' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'Active' })).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/portfolios?page=1&pageSize=25', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer test-bearer' }),
    }));
  });

  it('applies shareable search filters and exposes no-results state', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      const path = String(input);
      return path.includes('search=Missing')
        ? respond({ items: [], page: 1, pageSize: 25, total: 0 })
        : respond(portfolioResponse);
    });
    vi.stubGlobal('fetch', fetchMock);
    renderPage();

    await user.type(await screen.findByLabelText('Search portfolios'), 'Missing');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    expect(await screen.findByRole('status')).toHaveTextContent('No portfolios match these filters.');
    await waitFor(() => expect(fetchMock).toHaveBeenLastCalledWith('/api/portfolios?search=Missing&page=1&pageSize=25', expect.any(Object)));
  });

  it('shows API failure and allows a retry', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(respond({ detail: 'Portfolio API unavailable.' }, 503))
      .mockResolvedValueOnce(respond(portfolioResponse));
    vi.stubGlobal('fetch', fetchMock);
    renderPage();

    expect(await screen.findByRole('alert')).toHaveTextContent('Portfolio API unavailable.');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Payments portfolio from API')).toBeInTheDocument();
  });

  it('shows a null portfolio average and renders links from linked application data', async () => {
    sessionStorage.setItem('ketsip.auth.token', 'test-bearer');
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).includes('/applications?')) {
        return respond({
          items: [{
            id: 'application-1', name: 'API linked application', description: 'Linked record',
            portfolioId: 'portfolio-1', productArea: 'Payments', businessOwner: 'Payments owner',
            technologyOwner: 'Platform Engineering', etsOwner: 'Quality Office', criticality: 'High', tier: 2,
            lifecycleStatus: 'Active', technologyStack: 'React', repositoryLink: null, pipelineLink: null,
            applicationHealthScore: 80, qualityScore: 80, automationCoverage: 40, unitTestCoverage: 50,
            openDefects: 0, openCriticalDefects: 0, riskLevel: 'Low',
          }],
          page: 1,
          pageSize: 100,
          total: 1,
        });
      }
      return respond({ ...portfolioResponse.items[0], description: 'Portfolio description', applicationCount: 1, qualityScore: null });
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter initialEntries={['/portfolios/portfolio-1']}>
        <Routes>
          <Route path="/portfolios/:portfolioId" element={<PortfolioDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole('heading', { name: 'Payments portfolio from API' })).toBeInTheDocument();
    expect(screen.getByText('No quality score')).toBeInTheDocument();
    expect(await screen.findByRole('link', { name: 'API linked application' })).toHaveAttribute('href', '/applications/application-1');
  });
});
