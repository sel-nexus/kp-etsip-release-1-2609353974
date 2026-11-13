import { getSessionToken } from './auth';

/** Match the typed backend response for enterprise dashboard metrics. */
export interface ExecutiveDashboard {
  enterpriseQuality: number | null;
  averageHealth: number | null;
  automationMaturity: number | null;
  openCriticalDefects: number;
  applicationsAtRisk: number;
  totalApplications: number;
  totalPortfolios: number;
  portfolios: PortfolioComparison[];
}

/** Describe a visible portfolio's filtered quality and high-risk count. */
export interface PortfolioComparison {
  id: string;
  name: string;
  productArea: string;
  qualityScore: number | null;
  highRiskApplications: number;
}

/** Keep dashboard filters constrained to the API's supported query fields. */
export interface DashboardFilters {
  portfolioId?: string;
  productArea?: string;
  riskLevel?: 'Low' | 'Medium' | 'High';
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Request one authenticated executive summary and surface server failures. */
export async function getExecutiveDashboard(filters: DashboardFilters = {}): Promise<ExecutiveDashboard> {
  const token = getSessionToken();
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  const query = params.size ? `?${params.toString()}` : '';
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/dashboard/executive${query}`, {
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('The dashboard request could not be completed.');
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json() as { detail?: string; error?: { message?: string } };
      message = body.error?.message ?? body.detail ?? message;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
    throw new Error(message);
  }
  return await response.json() as ExecutiveDashboard;
}
