import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AuthProvider, useAuth } from './AuthProvider';
import type { AuthUser } from '../api/auth';

const profile: AuthUser = {
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

function SessionSummary(): JSX.Element {
  const { user, isLoading, signIn, signOut } = useAuth();
  return (
    <section>
      <p role="status">{isLoading ? 'Loading session' : user?.email ?? 'Signed out'}</p>
      <button type="button" onClick={() => void signIn('executive@ketsip.local', 'password')}>Sign in</button>
      <button type="button" onClick={() => void signOut()}>Sign out</button>
    </section>
  );
}

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('AuthProvider session behavior', () => {
  it('hydrates an existing tab token from the current-profile API', async () => {
    sessionStorage.setItem('ketsip.auth.token', 'backend-token');
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(profile), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<AuthProvider><SessionSummary /></AuthProvider>);
    expect(await screen.findByText('executive@ketsip.local')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/auth/me', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer backend-token' }),
    }));
  });

  it('stores the backend login token and clears it on logout', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: 'signed-token', user: profile }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(profile), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ success: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<AuthProvider><SessionSummary /></AuthProvider>);
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('executive@ketsip.local'));
    expect(sessionStorage.getItem('ketsip.auth.token')).toBe('signed-token');
    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Signed out'));
    expect(sessionStorage.getItem('ketsip.auth.token')).toBeNull();
  });

  it('discards an expired token while hydrating without fabricating a user', async () => {
    sessionStorage.setItem('ketsip.auth.token', 'expired-token');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Authentication required.' }), { status: 401 })));
    render(<AuthProvider><SessionSummary /></AuthProvider>);
    expect(await screen.findByText('Signed out')).toBeInTheDocument();
    expect(sessionStorage.getItem('ketsip.auth.token')).toBeNull();
  });
});
