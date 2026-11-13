import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../auth/AuthProvider';
import type { AuthUser } from '../api/auth';
import LoginPage from './LoginPage';

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

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

function renderLogin(): void {
  render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<p>Executive dashboard</p>} />
          <Route path="/applications" element={<p>Applications</p>} />
          <Route path="/profile" element={<p>Change your password</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('LoginPage', () => {
  it('shows labelled credentials and an accessible submit action', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid email or password.' }), { status: 401 }));
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    renderLogin();
    expect(screen.getByRole('heading', { name: 'Sign in to KP ETSIP' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeRequired();
    expect(screen.getByLabelText('Password')).toBeRequired();
    await user.type(screen.getByLabelText('Email address'), 'person@example.com');
    await user.type(screen.getByLabelText('Password'), 'secret-value');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.');
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('accepts a backend-issued session and follows the role landing preference', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ token: 'issued-token', user: executive }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(executive), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const user = userEvent.setup();
    renderLogin();
    await user.type(screen.getByLabelText('Email address'), executive.email);
    await user.type(screen.getByLabelText('Password'), 'demo-password');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText('Executive dashboard')).toBeInTheDocument();
    expect(sessionStorage.getItem('ketsip.auth.token')).toBe('issued-token');
  });
});
