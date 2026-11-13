import '@testing-library/jest-dom/vitest';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LoginPage from './LoginPage';

afterEach(() => {
  cleanup();
});

describe('LoginPage', () => {
  it('shows labelled credentials and an accessible submit action', () => {
    render(<LoginPage />);
    expect(screen.getByRole('heading', { name: 'Sign in to KP ETSIP' })).toBeInTheDocument();
    expect(screen.getByLabelText('Email address')).toBeRequired();
    expect(screen.getByLabelText('Password')).toBeRequired();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled();
  });

  it('announces that authentication is unavailable instead of faking a session', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByLabelText('Email address'), 'person@example.com');
    await user.type(screen.getByLabelText('Password'), 'secret-value');
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByRole('status')).toHaveTextContent('Authentication service not yet available.');
  });
});
