import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../auth/AuthProvider';
import type { AuthUser } from '../api/auth';
import AdministrationPage from './AdministrationPage';

const administrator: AuthUser = {
  id: '507f1f77bcf86cd799439011', name: 'Demo Admin', email: 'admin@example.com', role: 'Administrator',
  status: 'Active', permissions: ['view', 'create', 'edit', 'delete', 'export', 'administer'], portfolioAccess: [],
  mustChangePassword: false, lastLogin: null, defaultLandingPage: null, landingPage: '/applications', allowedLandingPages: ['/applications'],
};

const auditor: AuthUser = { ...administrator, role: 'Auditor', permissions: ['view', 'export'] };

function respond(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
}

function renderPage(currentUser: AuthUser = administrator): void {
  const profile = { ...currentUser };
  vi.stubGlobal('fetch', vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
    const path = String(input);
    if (path.includes('/api/auth/me')) return respond(profile);
    if (path.includes('/api/users')) return respond({ items: [{ id: 'user-1', name: 'Seeded Engineer', email: 'engineer@example.com', role: 'Engineer', portfolioAccess: [], status: 'Active', lastLogin: null, createdAt: null, updatedAt: null }], page: 1, pageSize: 100, total: 1 });
    if (path.includes('/api/roles')) return respond([{ id: 'role-1', name: 'Engineer', description: 'Maintains applications', permissions: ['view', 'create', 'edit', 'export'] }]);
    if (path.includes('/api/audit-logs')) return respond({ items: [{ id: 'audit-1', timestamp: '2025-01-01T12:00:00Z', userId: 'user-1', userName: 'Seeded Engineer', action: 'login', entityType: 'auth', entityId: null, details: 'Local account authentication succeeded' }], page: 1, pageSize: 100, total: 1 });
    return respond({ id: 'user-1', name: 'Seeded Engineer', email: 'engineer@example.com', role: 'Engineer', portfolioAccess: [], status: 'Inactive', lastLogin: null, createdAt: null, updatedAt: null });
  }));
  render(
    <MemoryRouter initialEntries={['/administration']}>
      <AuthProvider>
        <Routes><Route path="/administration" element={<AdministrationPage auditOnly={currentUser.role === 'Auditor'} />} /></Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('AdministrationPage', () => {
  it('shows live users and account actions to administrators', async () => {
    renderPage();
    expect(await screen.findByText('Seeded Engineer')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deactivate' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Users' })).toBeInTheDocument();
    expect(screen.getByLabelText('Name')).toBeRequired();
  });

  it('shows permission controls and audit events for admin tabs', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole('tab', { name: 'Roles' }));
    expect(await screen.findByRole('heading', { name: 'Engineer' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Engineer edit' })).toBeChecked();
    await user.click(screen.getByRole('tab', { name: 'Audit history' }));
    expect(await screen.findByText('Local account authentication succeeded')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Search audit history' })).toBeInTheDocument();
  });

  it('shows auditors only the audit history controls and events', async () => {
    renderPage(auditor);
    expect(await screen.findByRole('heading', { name: 'Audit history' })).toBeInTheDocument();
    expect(await screen.findByText('Local account authentication succeeded')).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Users' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Roles' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Deactivate' })).not.toBeInTheDocument();
  });

  it('reports loading completion and API failure visibly', async () => {
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo | URL) => {
      if (String(input).includes('/api/auth/me')) return respond(administrator);
      return respond({ detail: 'Administration service unavailable.' }, 503);
    });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <MemoryRouter initialEntries={['/administration']}>
        <AuthProvider><Routes><Route path="/administration" element={<AdministrationPage />} /></Routes></AuthProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('Administration service unavailable.');
    await waitFor(() => expect(screen.queryByText('Loading administration data…')).not.toBeInTheDocument());
    expect(screen.getByRole('heading', { name: 'Administration' })).toBeInTheDocument();
  });
});
