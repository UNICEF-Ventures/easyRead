import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getAuthStatus, logout as apiLogout } from '../apiClient';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check authentication status on mount
  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);
      const response = await getAuthStatus();
      if (response.data.authenticated) {
        setUser({ email: response.data.email });
      } else {
        setUser(null);
      }
      setError(null);
    } catch (err) {
      console.error('Auth check failed:', err);
      setUser(null);
      setError('Failed to check authentication status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Listen for session expiry events from API client
  useEffect(() => {
    const handleSessionExpired = () => {
      console.warn('Session expired, logging out...');
      setUser(null);
      setError('Your session has expired. Please log in again.');
    };

    window.addEventListener('auth:sessionExpired', handleSessionExpired);
    return () => window.removeEventListener('auth:sessionExpired', handleSessionExpired);
  }, []);

  // Login - called after successful OTP verification
  const login = useCallback((email) => {
    setUser({ email });
    setError(null);
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch (err) {
      console.error('Logout failed:', err);
    } finally {
      setUser(null);
    }
  }, []);

  const value = {
    user,
    loading,
    error,
    isAuthenticated: !!user,
    login,
    logout,
    checkAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
