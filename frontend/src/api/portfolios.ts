import { getSessionToken } from './auth';

export type PortfolioStatus = 'Active' | 'Archived';

export interface Portfolio {
  id: string;
  name: string;
  owner: string;
  description?: string;
  productArea: string;
  status: PortfolioStatus;
  applicationCount: number;
  qualityScore: number | null;
}

export interface PortfolioApplication {
  id: string;
  name: string;
  description: string;
  portfolioId: string;
  productArea: string;
  businessOwner: string;
  technologyOwner: string;
  etsOwner: string;
  criticality: string;
  tier: number;
  lifecycleStatus: string;
  technologyStack: string;
  repositoryLink: string | null;
  pipelineLink: string | null;
  applicationHealthScore: number;
  qualityScore: number;
  automationCoverage: number;
  unitTestCoverage: number;
  openDefects: number;
  openCriticalDefects: number;
  riskLevel: string;
}

export interface PortfolioPage {
  items: Portfolio[];
  page: number;
  pageSize: number;
  total: number;
}

export interface PortfolioApplicationPage {
  items: PortfolioApplication[];
  page: number;
  pageSize: number;
  total: number;
}

export interface PortfolioFilters {
  search?: string;
  status?: PortfolioStatus;
  productArea?: string;
  page?: number;
  pageSize?: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Send one authenticated inventory request and surface server failures. */
async function portfolioRequest<T>(path: string): Promise<T> {
  const token = getSessionToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('The portfolio request could not be completed.');
  }
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const data = await response.json() as { detail?: string; error?: { message?: string } };
      message = data.error?.message ?? data.detail ?? message;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
    throw new Error(message);
  }
  return await response.json() as T;
}

/** Read visible portfolio inventory with backend filtering and pagination. */
export function listPortfolios(filters: PortfolioFilters = {}): Promise<PortfolioPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  const suffix = params.size ? `?${params.toString()}` : '';
  return portfolioRequest<PortfolioPage>(`/api/portfolios${suffix}`);
}

/** Read one portfolio detail record and its source-derived rollups. */
export function getPortfolio(id: string): Promise<Portfolio> {
  return portfolioRequest<Portfolio>(`/api/portfolios/${encodeURIComponent(id)}`);
}

/** Read one bounded page of applications linked to an accessible portfolio. */
export function listPortfolioApplications(id: string, page = 1, pageSize = 25): Promise<PortfolioApplicationPage> {
  const params = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  return portfolioRequest<PortfolioApplicationPage>(`/api/portfolios/${encodeURIComponent(id)}/applications?${params.toString()}`);
}

/** Format absent arithmetic means explicitly instead of implying a zero score. */
export function formatQualityScore(score: number | null): string {
  return score === null ? 'No quality score' : `${score.toFixed(1)} / 100`;
}
