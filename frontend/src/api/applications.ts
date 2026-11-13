import { getSessionToken } from './auth';

export type ApplicationCriticality = 'Low' | 'Medium' | 'High' | 'Critical';
export type ApplicationLifecycleStatus = 'Active' | 'Deprecated' | 'Retired';
export type ApplicationRiskLevel = 'Low' | 'Medium' | 'High';

export interface ApplicationFields {
  name: string;
  description: string;
  portfolioId: string;
  productArea: string;
  businessOwner: string;
  technologyOwner: string;
  etsOwner: string;
  criticality: ApplicationCriticality;
  tier: number;
  lifecycleStatus: ApplicationLifecycleStatus;
  technologyStack: string;
  repositoryLink: string | null;
  pipelineLink: string | null;
  applicationHealthScore: number;
  qualityScore: number;
  automationCoverage: number;
  unitTestCoverage: number;
  openDefects: number;
  openCriticalDefects: number;
  riskLevel: ApplicationRiskLevel;
}

export interface ApplicationListItem extends ApplicationFields {
  id: string;
  portfolioName: string;
}

export interface ApplicationDetail extends ApplicationFields {
  id: string;
  portfolio: { id: string; name: string };
  createdAt: string;
  updatedAt: string;
}

export interface ApplicationPage {
  items: ApplicationListItem[];
  page: number;
  pageSize: number;
  total: number;
}

export interface ApplicationFilters {
  search?: string;
  portfolioId?: string;
  criticality?: ApplicationCriticality;
  riskLevel?: ApplicationRiskLevel;
  lifecycleStatus?: ApplicationLifecycleStatus;
  page?: number;
  pageSize?: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Send an authenticated same-origin application request and describe failures. */
async function applicationRequest<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const token = getSessionToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('The application request could not be completed.');
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
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

/** Fetch a bounded, permission-scoped application page with shareable filters. */
export function listApplications(filters: ApplicationFilters = {}): Promise<ApplicationPage> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  const suffix = params.size ? `?${params.toString()}` : '';
  return applicationRequest<ApplicationPage>(`/api/applications${suffix}`);
}

/** Fetch complete safe application data from its authenticated detail endpoint. */
export function getApplication(id: string): Promise<ApplicationDetail> {
  return applicationRequest<ApplicationDetail>(`/api/applications/${encodeURIComponent(id)}`);
}

/** Create an application with the complete validated source-field payload. */
export function createApplication(fields: ApplicationFields): Promise<ApplicationDetail> {
  return applicationRequest<ApplicationDetail>('/api/applications', 'POST', fields);
}

/** Replace application source fields after backend authorization and validation. */
export function updateApplication(id: string, fields: ApplicationFields): Promise<ApplicationDetail> {
  return applicationRequest<ApplicationDetail>(`/api/applications/${encodeURIComponent(id)}`, 'PUT', fields);
}

/** Request administrator-only removal of an application record. */
export function deleteApplication(id: string): Promise<void> {
  return applicationRequest<void>(`/api/applications/${encodeURIComponent(id)}`, 'DELETE');
}
