import { getSessionToken } from './auth';

export type AdminRole = 'Administrator' | 'Executive' | 'Portfolio Leader' | 'Engineer' | 'Auditor' | 'Read Only';
export type AdminPermission = 'view' | 'create' | 'edit' | 'delete' | 'export' | 'administer';
export type AuditAction = 'login' | 'create' | 'edit' | 'delete' | 'roleChange' | 'permissionChange' | 'export';

export interface ManagedUser {
  id: string;
  name: string;
  email: string;
  role: AdminRole;
  portfolioAccess: string[];
  status: 'Active' | 'Inactive';
  lastLogin: string | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface ManagedRole {
  id: string;
  name: AdminRole;
  description: string;
  permissions: AdminPermission[];
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  userId: string;
  userName: string;
  action: AuditAction;
  entityType: string;
  entityId: string | null;
  details: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  pageSize: number;
  total: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Send one authenticated request and surface server or transport failures. */
async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getSessionToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });
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

/** Load managed accounts from the protected administration endpoint. */
export function listManagedUsers(): Promise<Page<ManagedUser>> {
  return adminRequest<Page<ManagedUser>>('/api/users?page=1&pageSize=100');
}

/** Create an account using the protected administration endpoint. */
export function createManagedUser(payload: { name: string; email: string; role: AdminRole; portfolioAccess: string[]; password: string }): Promise<ManagedUser> {
  return adminRequest<ManagedUser>('/api/users', { method: 'POST', body: JSON.stringify(payload) });
}

/** Update permitted fields of a managed account. */
export function updateManagedUser(id: string, payload: Partial<Pick<ManagedUser, 'name' | 'email' | 'role' | 'portfolioAccess' | 'status'>>): Promise<ManagedUser> {
  return adminRequest<ManagedUser>(`/api/users/${encodeURIComponent(id)}`, { method: 'PUT', body: JSON.stringify(payload) });
}

/** Deactivate a managed account without removing persisted history. */
export function deactivateManagedUser(id: string): Promise<ManagedUser> {
  return adminRequest<ManagedUser>(`/api/users/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

/** Read existing roles from protected role administration. */
export function listManagedRoles(): Promise<ManagedRole[]> {
  return adminRequest<ManagedRole[]>('/api/roles');
}

/** Save an existing role's description and supported permissions. */
export function updateManagedRole(name: AdminRole, description: string, permissions: AdminPermission[]): Promise<ManagedRole> {
  return adminRequest<ManagedRole>(`/api/roles/${encodeURIComponent(name)}`, { method: 'PUT', body: JSON.stringify({ description, permissions }) });
}

/** Search the authorized audit view with optional user, action, and time filters. */
export function searchAudit(filters: { userId?: string; action?: AuditAction; from?: string; to?: string }): Promise<Page<AuditEntry>> {
  const params = new URLSearchParams({ page: '1', pageSize: '100' });
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  return adminRequest<Page<AuditEntry>>(`/api/audit-logs?${params.toString()}`);
}
