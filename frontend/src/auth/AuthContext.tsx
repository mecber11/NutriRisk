import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, getAccessToken, login as loginRequest, setTokens } from '../api/client';
import type { User } from '../types';

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (module: string, action?: string) => boolean;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadUser = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get<User>('/auth/me');
      setUser(me);
    } catch {
      setTokens(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
    const handler = () => setUser(null);
    window.addEventListener('nr:unauthorized', handler);
    return () => window.removeEventListener('nr:unauthorized', handler);
  }, [loadUser]);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const data = await loginRequest(email, password);
      setTokens({ access_token: data.access_token, refresh_token: data.refresh_token });
      setUser(data.user);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'No se pudo iniciar sesión';
      setError(message);
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout', {});
    } catch {
      /* ignore */
    }
    setTokens(null);
    setUser(null);
  }, []);

  const can = useCallback(
    (module: string, action = 'read') => {
      if (!user) return false;
      if (user.role.code === 'ADMIN') return true;
      const permissions = user.permissions ?? {};
      return Boolean(permissions[module]?.includes(action));
    },
    [user],
  );

  const value = useMemo<AuthState>(
    () => ({ user, loading, error, login, logout, refresh: loadUser, can }),
    [user, loading, error, login, logout, loadUser, can],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth debe usarse dentro de AuthProvider');
  return context;
}
