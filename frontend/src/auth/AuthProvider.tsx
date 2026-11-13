import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import {
  type AuthUser,
  type LoginResult,
  clearSessionToken,
  fetchCurrentUser,
  getSessionToken,
  login as loginRequest,
  logout as logoutRequest,
} from '../api/auth';

interface AuthContextValue {
  user: AuthUser | null;
  isLoading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<LoginResult>;
  signOut: () => Promise<void>;
  setUser: (user: AuthUser) => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

/** Hydrate and maintain the backend-backed bearer-token session. */
export function AuthProvider({ children }: AuthProviderProps): JSX.Element {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function hydrate(): Promise<void> {
      if (!getSessionToken()) {
        setIsLoading(false);
        return;
      }
      try {
        const current = await fetchCurrentUser();
        if (active) {
          setUser(current);
        }
      } catch {
        clearSessionToken();
        if (active) {
          setUser(null);
          setError('Could not verify the saved session. Please sign in again.');
        }
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    }
    void hydrate();
    const onUnauthorized = (): void => {
      if (active) {
        setUser(null);
      }
    };
    window.addEventListener('ketsip:unauthorized', onUnauthorized);
    return () => {
      active = false;
      window.removeEventListener('ketsip:unauthorized', onUnauthorized);
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string): Promise<LoginResult> => {
    setError(null);
    try {
      const result = await loginRequest(email, password);
      const currentUser = await fetchCurrentUser();
      const authenticated = { token: result.token, user: currentUser };
      setUser(currentUser);
      return authenticated;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed.');
      throw reason;
    }
  }, []);

  const signOut = useCallback(async (): Promise<void> => {
    try {
      if (getSessionToken()) {
        await logoutRequest();
      }
    } catch {
      // Expired tokens still end the local session below.
    } finally {
      clearSessionToken();
      setUser(null);
      setError(null);
    }
  }, []);

  const clearError = useCallback((): void => setError(null), []);
  const context = useMemo<AuthContextValue>(
    () => ({ user, isLoading, error, signIn, signOut, setUser, clearError }),
    [user, isLoading, error, signIn, signOut, clearError],
  );

  return <AuthContext.Provider value={context}>{children}</AuthContext.Provider>;
}

/** Return the session context or fail immediately when no provider is mounted. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider.');
  }
  return context;
}
