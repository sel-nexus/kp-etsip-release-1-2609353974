import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import DashboardPage from './DashboardPage';
import { getExecutiveDashboard } from '../api/dashboard';
import type { ExecutiveDashboard } from '../api/dashboard';

vi.mock('../api/dashboard', () => ({ getExecutiveDashboard: vi.fn() }));

const populated: ExecutiveDashboard = {
  enterpriseQuality: 81,
  averageHealth: 84,
  automationMaturity: 75,
  openCriticalDefects: 11,
  applicationsAtRisk: 3,
  totalApplications: 10,
  totalPortfolios: 3,
  portfolios: [
    { id: 'portfolio-1', name: 'Payments', productArea: 'Payments', qualityScore: 79, highRiskApplications: 1 },
    { id: 'portfolio-2', name: 'Empty portfolio', productArea: 'Other', qualityScore: null, highRiskApplications: 0 },
  ],
};

function LocationOutput(): JSX.Element {
  const location = useLocation();
  return <output aria-label="Current location">{location.pathname}{location.search}</output>;
}

function renderDashboard(initialEntry = '/dashboard'): void {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/dashboard" element={<><DashboardPage /><LocationOutput /></>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('DashboardPage', () => {
  it('renders API metrics and portfolio comparisons including a portfolio with no applications', async () => {
    vi.mocked(getExecutiveDashboard).mockResolvedValue(populated);
    renderDashboard();

    expect(await screen.findByText('81 / 100')).toBeInTheDocument();
    expect(screen.getByText('84 / 100')).toBeInTheDocument();
    expect(screen.getByText('75%')).toBeInTheDocument();
    expect(screen.getByText('Critical defects')).toBeInTheDocument();
    expect(screen.getByText('Applications at risk')).toBeInTheDocument();
    expect(screen.getByText('10', { selector: 'p' })).toBeInTheDocument();
    expect(screen.getAllByText('3', { selector: 'p' })).toHaveLength(2);
    expect(screen.getByRole('list', { name: 'Portfolio comparisons' })).toHaveTextContent('Payments');
    expect(screen.getByText('No score')).toBeInTheDocument();
  });

  it('loads and applies portfolio, risk, and product area filters to URL and API', async () => {
    const user = userEvent.setup();
    vi.mocked(getExecutiveDashboard).mockResolvedValue(populated);
    renderDashboard();
    await screen.findByText('81 / 100');

    await user.selectOptions(screen.getByLabelText('Portfolio'), 'portfolio-1');
    await waitFor(() => expect(getExecutiveDashboard).toHaveBeenLastCalledWith({ portfolioId: 'portfolio-1' }));
    await user.selectOptions(screen.getByLabelText('Risk level'), 'High');
    await waitFor(() => expect(getExecutiveDashboard).toHaveBeenLastCalledWith({ portfolioId: 'portfolio-1', riskLevel: 'High' }));
    await user.clear(screen.getByLabelText('Product area'));
    await user.type(screen.getByLabelText('Product area'), 'Payments');
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    await waitFor(() => expect(getExecutiveDashboard).toHaveBeenLastCalledWith({ portfolioId: 'portfolio-1', productArea: 'Payments', riskLevel: 'High' }));
    expect(screen.getByLabelText('Current location')).toHaveTextContent('portfolioId=portfolio-1');
    expect(screen.getByLabelText('Current location')).toHaveTextContent('productArea=Payments');
    expect(screen.getByLabelText('Current location')).toHaveTextContent('riskLevel=High');
  });

  it('shows loading and empty states without inventing zero averages', async () => {
    let resolveRequest: ((value: ExecutiveDashboard) => void) | undefined;
    vi.mocked(getExecutiveDashboard).mockReturnValue(new Promise((resolve) => { resolveRequest = resolve; }));
    renderDashboard();
    expect(screen.getByText('Loading executive dashboard…')).toHaveAttribute('role', 'status');
    resolveRequest?.({
      enterpriseQuality: null,
      averageHealth: null,
      automationMaturity: null,
      openCriticalDefects: 0,
      applicationsAtRisk: 0,
      totalApplications: 0,
      totalPortfolios: 1,
      portfolios: [{ id: 'portfolio-1', name: 'Payments', productArea: 'Payments', qualityScore: null, highRiskApplications: 0 }],
    });
    expect(await screen.findByText('No applications match these filters.')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.getByText('No score')).toBeInTheDocument();
  });

  it('shows an error with a retry action after a failed API request', async () => {
    const user = userEvent.setup();
    vi.mocked(getExecutiveDashboard)
      .mockRejectedValueOnce(new Error('Dashboard unavailable'))
      .mockResolvedValueOnce(populated);
    renderDashboard();

    expect(await screen.findByRole('alert')).toHaveTextContent('Dashboard unavailable');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('81 / 100')).toBeInTheDocument();
    expect(getExecutiveDashboard).toHaveBeenCalledTimes(2);
  });
});
