import React, { createContext, useContext, useState, useEffect, ReactNode, useCallback } from 'react';
import { apiClient } from '../api/client';

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  department: string;
  badge_number: string;
  mfa_enabled: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  mfaVerified: boolean;
  login: (token: string, userData: User, mfa: boolean) => void;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function clearStoredSession() {
  localStorage.removeItem('lexsecure_token');
  localStorage.removeItem('lexsecure_user');
  localStorage.removeItem('lexsecure_mfa');
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [mfaVerified, setMfaVerified] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    const current = localStorage.getItem('lexsecure_token');
    if (current) {
      apiClient
        .post('/auth/logout', {}, { headers: { Authorization: `Bearer ${current}` } })
        .catch(() => {});
    }
    clearStoredSession();
    setToken(null);
    setUser(null);
    setMfaVerified(false);
    window.location.href = '/login';
  }, []);

  useEffect(() => {
    const storedToken = localStorage.getItem('lexsecure_token');
    const storedUser = localStorage.getItem('lexsecure_user');
    const storedMfa = localStorage.getItem('lexsecure_mfa');

    if (!storedToken) {
      setIsLoading(false);
      return;
    }

    apiClient
      .get('/auth/me')
      .then((res) => {
        setToken(storedToken);
        setUser(res.data);
        setMfaVerified(storedMfa === 'true');
        localStorage.setItem('lexsecure_user', JSON.stringify(res.data));
        setIsLoading(false);
      })
      .catch((err) => {
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          clearStoredSession();
          setToken(null);
          setUser(null);
        } else if (storedUser) {
          try {
            setUser(JSON.parse(storedUser));
            setToken(storedToken);
            setMfaVerified(storedMfa === 'true');
          } catch {
            clearStoredSession();
          }
        }
        setIsLoading(false);
      });
  }, []);

  const login = useCallback((newToken: string, userData: User, mfa: boolean) => {
    localStorage.setItem('lexsecure_token', newToken);
    localStorage.setItem('lexsecure_user', JSON.stringify(userData));
    localStorage.setItem('lexsecure_mfa', mfa ? 'true' : 'false');

    setToken(newToken);
    setUser(userData);
    setMfaVerified(mfa);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, mfaVerified, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
