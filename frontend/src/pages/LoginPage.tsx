import { useState } from 'react';

/** Render a keyboard-accessible sign-in form until the auth API is available. */
export default function LoginPage(): JSX.Element {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [status, setStatus] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  /** Explain unavailable authentication without inventing a local session. */
  function handleSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setIsSubmitting(true);
    setStatus('Authentication service not yet available.');
    setIsSubmitting(false);
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
              required
            />
          </div>
          <button className="primary-button w-full" type="submit" disabled={isSubmitting}>
            Sign in
          </button>
          <p className="min-h-6 text-sm text-foreground-muted" aria-live="polite" role="status">
            {status}
          </p>
        </form>
      </div>
    </section>
  );
}
