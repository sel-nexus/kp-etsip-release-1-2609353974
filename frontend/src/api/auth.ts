/** Define the safe profile shape returned by the local authentication API. */
export interface AuthUser {
  id: string;
  name: string;
  email: string;
  role: string;
  status: string;
  permissions: string[];
  portfolioAccess: string[];
  mustChangePassword: boolean;
  lastLogin: string | null;
  defaultLandingPage: string | null;
  landingPage: string;
  allowedLandingPages: string[];
}

/** Carry a backend-issued bearer token and the matching safe user profile. */
export interface LoginResult {
  token: string;
  user: AuthUser;
}

const TOKEN_KEY = 'ketsip.auth.token';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/** Read the short-lived bearer token from this browser tab's session. */
export function getSessionToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

/** Store the backend token only for the current browser session. */
export function storeSessionToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

/** Remove the current tab's bearer token and never persist it across sessions. */
export function clearSessionToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

/** Call the auth API and safely handle bearer expiry outside the login mutation. */
async function authRequest<T>(path: string, body?: unknown, authenticated = true, method?: string): Promise<T> {
  const token = authenticated ? getSessionToken() : null;
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: method ?? (body === undefined ? 'GET' : 'POST'),
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    if (error instanceof Error) {
      throw error;
    }
    throw new Error('The authentication request could not be completed.');
  }

  if (!response.ok) {
    if (response.status === 401 && !path.endsWith('/login')) {
      clearSessionToken();
      window.dispatchEvent(new Event('ketsip:unauthorized'));
    }
    let message = 'The request could not be completed.';
    try {
      const data = (await response.json()) as { detail?: string; error?: { message?: string } };
      message = data.error?.message ?? data.detail ?? message;
    } catch (error) {
      if (!(error instanceof SyntaxError)) {
        throw error;
      }
    }
    throw new Error(message);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Authenticate credentials and return the backend-issued session token. */
export async function login(email: string, password: string): Promise<LoginResult> {
  const result = await authRequest<LoginResult>('/api/auth/login', { email, password }, false);
  storeSessionToken(result.token);
  return result;
}

/** Hydrate a tab session by asking the backend for the current profile. */
export function fetchCurrentUser(): Promise<AuthUser> {
  return authRequest<AuthUser>('/api/auth/me');
}

/** Acknowledge sign-out before the local tab session is discarded. */
export function logout(): Promise<{ success: boolean }> {
  return authRequest<{ success: boolean }>('/api/auth/logout', {});
}

/** Change the signed-in user's password through the protected API. */
export function changePassword(currentPassword: string, newPassword: string): Promise<AuthUser> {
  return authRequest<AuthUser>('/api/auth/me/password', { currentPassword, newPassword }, true, 'PUT');
}

/** Save a self-service landing-page preference. */
export function saveLandingPreference(defaultLandingPage: string | null): Promise<{ user: AuthUser }> {
  return authRequest<{ user: AuthUser }>('/api/auth/me/preferences', { defaultLandingPage }, true, 'PUT');
}
