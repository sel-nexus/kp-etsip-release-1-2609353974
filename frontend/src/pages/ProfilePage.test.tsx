import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from '../auth/AuthProvider';
import type { AuthUser } from '../api/auth';
import ProfilePage from './ProfilePage';

const executive: AuthUser = {
  id: '507f1f77bcf86cd799439011',
  name: 'Demo Executive',
  email: 'executive@ketsip.local',
  role: 'Executive',
  status: 'Active',
  permissions: ['view', 'export'],
  portfolioAccess: [],
  mustChangePassword: false,
  lastLogin: null,
  defaultLandingPage: null,
  landingPage: '/dashboard',
  allowedLandingPages: ['/dashboard', '/applications'],
};

function AuthenticatedProfile(): JSX.Element {
  const { user } = useAuth();
  return (
    <>
      <ProfilePage />
      <p aria-label="Saved landing preference">{user?.defaultLandingPage ?? 'No saved preference'}</p>
      <p aria-label="First-login password status">{user?.mustChangePassword ? 'Password change required' : 'Password current'}</p>
    </>
  );
}

function renderProfile(fetchMock: ReturnType<typeof vi.fn>): void {
  sessionStorage.setItem('ketsip.auth.token', 'profile-test-token');
  vi.stubGlobal('fetch', fetchMock);
  render(
    <MemoryRouter initialEntries={['/profile']}>
      <AuthProvider>
        <Routes>
          <Route path="/profile" element={<AuthenticatedProfile />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('ProfilePage', () => {
  it('renders safe account details and role-available profile forms', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(executive), { status: 200 }));
    renderProfile(fetchMock);

    expect(await screen.findByRole('heading', { name: 'Your profile' })).toBeInTheDocument();
    expect(screen.getByText('Demo Executive')).toBeInTheDocument();
    expect(screen.getByText('executive@ketsip.local')).toBeInTheDocument();
    expect(screen.getByText('Executive')).toBeInTheDocument();
    expect(screen.getByText('All portfolios')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Change password' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Default landing page' })).toBeInTheDocument();
    expect(screen.queryByText(/passwordHash/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Password change required')).not.toBeInTheDocument();
  });

  it('shows password-change success and updates the authenticated profile', async () => {
    const firstLogin: AuthUser = { ...executive, mustChangePassword: true };
    const changed: AuthUser = { ...executive, mustChangePassword: false };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(firstLogin), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(changed), { status: 200 }));
    renderProfile(fetchMock);
    const user = userEvent.setup();

    expect(await screen.findByRole('alert')).toHaveTextContent('Change your password before continuing to the platform.');
    expect(screen.queryByRole('heading', { name: 'Default landing page' })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText('Current password'), 'OldPassword123!');
    await user.type(screen.getByLabelText('New password'), 'NewPassword456!');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(await screen.findByText('Password changed successfully.', { selector: '[role="status"]' })).toBeInTheDocument();
    expect(await screen.findByLabelText('First-login password status')).toHaveTextContent('Password current');
    expect(screen.getByRole('heading', { name: 'Default landing page' })).toBeInTheDocument();
    expect(screen.getByLabelText('Current password')).toHaveValue('');
    expect(screen.getByLabelText('New password')).toHaveValue('');
  });

  it('displays a password-change failure returned by the API', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(executive), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Current password is incorrect.' }), { status: 400 }));
    renderProfile(fetchMock);
    const user = userEvent.setup();

    await screen.findByRole('heading', { name: 'Your profile' });
    await user.type(screen.getByLabelText('Current password'), 'WrongPassword123!');
    await user.type(screen.getByLabelText('New password'), 'NewPassword456!');
    await user.click(screen.getByRole('button', { name: 'Update password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Current password is incorrect.');
    expect(screen.getByLabelText('Current password')).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows preference success and reflects the saved user preference in the provider', async () => {
    const saved: AuthUser = { ...executive, defaultLandingPage: '/applications', landingPage: '/applications' };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(executive), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ user: saved }), { status: 200 }));
    renderProfile(fetchMock);
    const user = userEvent.setup();

    await screen.findByRole('heading', { name: 'Your profile' });
    await user.selectOptions(screen.getByLabelText('After sign in'), '/applications');
    await user.click(screen.getByRole('button', { name: 'Save preference' }));

    expect(await screen.findByText('Default page saved.', { selector: '[role="status"]' })).toBeInTheDocument();
    expect(await screen.findByLabelText('Saved landing preference')).toHaveTextContent('/applications');
  });

  it('shows a denied preference error without changing the authenticated profile', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(executive), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'That landing page is not available for this account.' }), { status: 403 }));
    renderProfile(fetchMock);
    const user = userEvent.setup();

    await screen.findByRole('heading', { name: 'Your profile' });
    await user.selectOptions(screen.getByLabelText('After sign in'), '/applications');
    await user.click(screen.getByRole('button', { name: 'Save preference' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('That landing page is not available for this account.');
    expect(screen.getByLabelText('After sign in')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByLabelText('Saved landing preference')).toHaveTextContent('No saved preference');
  });
});
