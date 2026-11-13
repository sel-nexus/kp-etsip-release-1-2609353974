import { getSessionToken } from './auth';

export interface ReportPage<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

export interface ApplicationReportRow {
  id: string;
  name: string;
  description: string;
  portfolioId: string;
  portfolioName: string;
  productArea: string;
  businessOwner: string;
  technologyOwner: string;
  etsOwner: string;
  criticality: 'Low' | 'Medium' | 'High' | 'Critical';
  tier: number;
  lifecycleStatus: 'Active' | 'Deprecated' | 'Retired';
  technologyStack: string;
  repositoryLink: string | null;
  pipelineLink: string | null;
  applicationHealthScore: number;
  qualityScore: number;
  automationCoverage: number;
  unitTestCoverage: number;
  openDefects: number;
  openCriticalDefects: number;
  riskLevel: 'Low' | 'Medium' | 'High';
}

export interface PortfolioReportRow {
  id: string;
  name: string;
  owner: string;
  productArea: string;
  status: 'Active' | 'Archived';
  applicationCount: number;
  qualityScore: number | null;
}

export interface ApplicationReportFilters {
  search?: string;
  portfolioId?: string;
  criticality?: ApplicationReportRow['criticality'];
  riskLevel?: ApplicationReportRow['riskLevel'];
  lifecycleStatus?: ApplicationReportRow['lifecycleStatus'];
  page?: number;
  pageSize?: number;
}

export interface PortfolioReportFilters {
  search?: string;
  status?: PortfolioReportRow['status'];
  productArea?: string;
  page?: number;
  pageSize?: number;
}

export interface AuditCsvFilters {
  userId?: string;
  action?: string;
  from?: string;
  to?: string;
}

export interface CsvDownload {
  blob: Blob;
  filename: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Fetch a same-origin report response with the current bearer session. */
async function reportRequest(path: string, accept: string): Promise<Response> {
  const token = getSessionToken();
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: 'same-origin',
      headers: {
        Accept: accept,
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  } catch (error) {
    if (error instanceof Error) throw error;
    throw new Error('The report request could not be completed.');
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
  return response;
}

function queryString(values: Record<string, string | number | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== '') params.set(key, String(value));
  }
  return params.size ? `?${params.toString()}` : '';
}

/** Fetch the bounded application report table page with inventory filters. */
export async function listApplicationReport(filters: ApplicationReportFilters = {}): Promise<ReportPage<ApplicationReportRow>> {
  const response = await reportRequest(`/api/reports/applications${queryString(filters)}`, 'application/json');
  return await response.json() as ReportPage<ApplicationReportRow>;
}

/** Fetch the bounded portfolio report table page with inventory filters. */
export async function listPortfolioReport(filters: PortfolioReportFilters = {}): Promise<ReportPage<PortfolioReportRow>> {
  const response = await reportRequest(`/api/reports/portfolios${queryString(filters)}`, 'application/json');
  return await response.json() as ReportPage<PortfolioReportRow>;
}

function filenameFrom(response: Response, fallback: string): string {
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? fallback;
}

/** Request an explicitly selected report CSV and preserve its attachment filename. */
async function fetchCsv(path: string, fallback: string): Promise<CsvDownload> {
  const response = await reportRequest(path, 'text/csv');
  return { blob: await response.blob(), filename: filenameFrom(response, fallback) };
}

/** Fetch a filtered full application CSV only when explicitly requested. */
export function fetchApplicationReportCsv(filters: Omit<ApplicationReportFilters, 'page' | 'pageSize'> = {}): Promise<CsvDownload> {
  return fetchCsv(`/api/reports/applications${queryString({ ...filters, format: 'csv' })}`, 'applications.csv');
}

/** Fetch a filtered full portfolio CSV only when explicitly requested. */
export function fetchPortfolioReportCsv(filters: Omit<PortfolioReportFilters, 'page' | 'pageSize'> = {}): Promise<CsvDownload> {
  return fetchCsv(`/api/reports/portfolios${queryString({ ...filters, format: 'csv' })}`, 'portfolios.csv');
}

/** Fetch authorized audit history CSV with the existing history filters. */
export function fetchAuditCsv(filters: AuditCsvFilters = {}): Promise<CsvDownload> {
  return fetchCsv(`/api/audit-logs${queryString({ ...filters, format: 'csv' })}`, 'audit-logs.csv');
}

/** Trigger a browser download and release its temporary object URL. */
export function downloadCsv(download: CsvDownload): void {
  const url = URL.createObjectURL(download.blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = download.filename;
  anchor.style.display = 'none';
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
