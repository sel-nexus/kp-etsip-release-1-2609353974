import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';

/** Submit credentials to the backend and route only after real authentication. */
export default function LoginPage(): JSX.Element {
  const { user, isLoading, error, signIn, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const returnPath = (location.state as { from?: string } | null)?.from;

  useEffect(() => {
    clearError();
  }, [clearError]);

  if (isLoading) {
    return <p className="mx-auto max-w-shell px-6 py-12" role="status">Checking your session…</p>;
  }
  if (user) {
    return <Navigate to={user.mustChangePassword ? '/profile' : user.landingPage} replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const result = await signIn(email, password);
      const requestedDestination = returnPath && !returnPath.startsWith('//') && result.user.allowedLandingPages.includes(returnPath)
        ? returnPath
        : result.user.landingPage;
      navigate(result.user.mustChangePassword ? '/profile' : requestedDestination, { replace: true });
    } catch {
      // AuthProvider exposes the generic backend failure in its live error state.
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-shell items-center px-4 py-12 sm:px-6 lg:grid-cols-12 lg:px-12">
      <div className="lg:col-span-5 lg:col-start-4">
        <p className="mb-3 text-sm font-semibold tracking-wide text-foreground-muted">PLATFORM ACCESS</p>
        <h1 className="mb-3">Sign in to KP ETSIP</h1>
        <p className="mb-8 max-w-prose text-foreground-muted">
          Access portfolio and application information for your role.
        </p>
        <form className="quiet-card space-y-5 p-6 sm:p-8" onSubmit={handleSubmit}>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="email">Email address</label>
            <input
              autoComplete="username"
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.currentTarget.value)}
              aria-required="true"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'login-error' : undefined}
              required
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="password">Password</label>
            <input
              autoComplete="current-password"
              id="password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              aria-required="true"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'login-error' : undefined}
              required
            />
          </div>
          <button className="primary-button w-full" type="submit" disabled={isSubmitting}>
            Sign in
          </button>
          {error && <p id="login-error" className="text-sm text-error" role="alert">{error.includes('Invalid email or password') ? 'Invalid email or password.' : 'Unable to sign in right now. Please try again.'}</p>}
          <p className="min-h-6 text-sm text-foreground-muted" aria-live="polite" role="status">
            {isSubmitting ? 'Signing in…' : ''}
          </p>
        </form>
      </div>
    </section>
  );
}
