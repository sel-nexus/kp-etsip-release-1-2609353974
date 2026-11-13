import { useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { changePassword, saveLandingPreference } from '../api/auth';
import { useAuth } from '../auth/AuthProvider';

/** Show the signed-in user's safe profile and self-service account forms. */
export default function ProfilePage(): JSX.Element {
  const { user, setUser, signOut } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [landingPage, setLandingPage] = useState(user?.defaultLandingPage ?? user?.landingPage ?? '/applications');
  const [passwordMessage, setPasswordMessage] = useState('');
  const [preferenceMessage, setPreferenceMessage] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [preferenceError, setPreferenceError] = useState('');
  const [savingPassword, setSavingPassword] = useState(false);
  const [savingPreference, setSavingPreference] = useState(false);

  async function handlePasswordSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPasswordError('');
    setPasswordMessage('');
    setSavingPassword(true);
    try {
      const updated = await changePassword(currentPassword, newPassword);
      setUser(updated);
      setCurrentPassword('');
      setNewPassword('');
      setPasswordMessage('Password changed successfully.');
    } catch (error) {
      setPasswordError(error instanceof Error ? error.message : 'Password change failed.');
    } finally {
      setSavingPassword(false);
    }
  }

  async function handlePreferenceSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPreferenceError('');
    setPreferenceMessage('');
    setSavingPreference(true);
    try {
      const result = await saveLandingPreference(landingPage || null);
      setUser(result.user);
      setPreferenceMessage('Default page saved.');
    } catch (error) {
      setPreferenceError(error instanceof Error ? error.message : 'Preference could not be saved.');
    } finally {
      setSavingPreference(false);
    }
  }

  async function handleSignOut(): Promise<void> {
    await signOut();
    navigate('/login', { replace: true });
  }

  if (!user) {
    return <p role="status">Loading profile…</p>;
  }

  return (
    <section className="mx-auto max-w-shell px-4 py-10 sm:px-6 lg:px-12">
      <div className="mb-8 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-2 text-sm font-semibold tracking-wide text-foreground-muted">ACCOUNT</p>
          <h1 className="mb-2">Your profile</h1>
          <p className="text-foreground-muted">Review your account and manage your sign-in preferences.</p>
        </div>
        <button className="primary-button" type="button" onClick={() => void handleSignOut()}>Sign out</button>
      </div>

      {user.mustChangePassword && (
        <p className="mb-6 border border-border p-4" role="alert">
          Change your password before continuing to the platform.
        </p>
      )}

      <section className="quiet-card mb-8 p-6" aria-labelledby="profile-details-title">
        <h2 id="profile-details-title" className="mb-5 text-xl font-semibold">Account details</h2>
        <dl className="grid gap-4 sm:grid-cols-2">
          <div><dt className="text-sm text-foreground-muted">Name</dt><dd>{user.name}</dd></div>
          <div><dt className="text-sm text-foreground-muted">Email</dt><dd>{user.email}</dd></div>
          <div><dt className="text-sm text-foreground-muted">Role</dt><dd>{user.role}</dd></div>
          <div><dt className="text-sm text-foreground-muted">Portfolio access</dt><dd>{user.portfolioAccess.length ? `${user.portfolioAccess.length} assigned portfolio(s)` : 'All portfolios'}</dd></div>
        </dl>
      </section>

      <form className="quiet-card mb-8 max-w-2xl space-y-5 p-6" onSubmit={(event) => void handlePasswordSubmit(event)}>
        <div>
          <h2 className="mb-2 text-xl font-semibold">Change password</h2>
          <p className="text-sm text-foreground-muted">Use at least 12 characters for your new password.</p>
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="current-password">Current password</label>
          <input id="current-password" name="currentPassword" type="password" autoComplete="current-password" required aria-required="true" aria-invalid={Boolean(passwordError)} aria-describedby={passwordError ? 'password-error' : undefined} value={currentPassword} onChange={(event) => setCurrentPassword(event.currentTarget.value)} />
        </div>
        <div>
          <label className="mb-2 block text-sm font-semibold" htmlFor="new-password">New password</label>
          <input id="new-password" name="newPassword" type="password" autoComplete="new-password" minLength={12} required aria-required="true" aria-invalid={Boolean(passwordError)} aria-describedby={passwordError ? 'password-error' : undefined} value={newPassword} onChange={(event) => setNewPassword(event.currentTarget.value)} />
        </div>
        {passwordError && <p id="password-error" className="text-sm text-error" role="alert">{passwordError}</p>}
        <p className="text-sm text-foreground-muted" aria-live="polite" role="status">{passwordMessage}</p>
        <button className="primary-button" type="submit" disabled={savingPassword}>{savingPassword ? 'Saving…' : 'Update password'}</button>
      </form>

      {!user.mustChangePassword && (
        <form className="quiet-card max-w-2xl space-y-5 p-6" onSubmit={(event) => void handlePreferenceSubmit(event)}>
          <div>
            <h2 className="mb-2 text-xl font-semibold">Default landing page</h2>
            <p className="text-sm text-foreground-muted">Choose a destination available to your role.</p>
          </div>
          <div>
            <label className="mb-2 block text-sm font-semibold" htmlFor="landing-page">After sign in</label>
            <select id="landing-page" name="landingPage" aria-invalid={Boolean(preferenceError)} aria-describedby={preferenceError ? 'preference-error' : undefined} value={landingPage} onChange={(event) => setLandingPage(event.currentTarget.value)}>
              {user.allowedLandingPages.map((page) => (
                <option key={page} value={page}>{page === '/dashboard' ? 'Executive dashboard' : 'Applications'}</option>
              ))}
            </select>
          </div>
          {preferenceError && <p id="preference-error" className="text-sm text-error" role="alert">{preferenceError}</p>}
          <p className="text-sm text-foreground-muted" aria-live="polite" role="status">{preferenceMessage}</p>
          <button className="primary-button" type="submit" disabled={savingPreference}>{savingPreference ? 'Saving…' : 'Save preference'}</button>
        </form>
      )}
    </section>
  );
}
