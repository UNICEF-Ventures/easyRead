import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { config } from '../config';
import { getAuthStatus, logout as apiLogout } from '../apiClient';
import {
  hasOAuthCallback,
  handleOAuthCallback,
  getAccessToken,
  getStoredUser,
  isOAuthAuthenticated,
  oauthLogout,
  initiateOAuthLogin,
} from '../utils/oauth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const authMethod = config.AUTH_METHOD; // 'otp' or 'oauth'

  // Check OTP authentication status (session-based)
  const checkOTPAuth = useCallback(async () => {
    try {
      const response = await getAuthStatus();
      if (response.data.authenticated) {
        setUser({ email: response.data.email });
      } else {
        setUser(null);
      }
      setError(null);
    } catch (err) {
      console.error('OTP auth check failed:', err);
      setUser(null);
      setError('Failed to check authentication status');
    }
  }, []);

  // Check OAuth authentication status (token-based)
  const checkOAuthAuth = useCallback(() => {
    const token = getAccessToken();
    const storedUser = getStoredUser();

    if (token && storedUser) {
      setAccessToken(token);
      setUser(storedUser);
      setError(null);
    } else {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  // Handle OAuth callback if present in URL
  const processOAuthCallback = useCallback(async () => {
    if (!hasOAuthCallback()) {
      return false;
    }

    try {
      setLoading(true);
      const { tokens, user: oauthUser } = await handleOAuthCallback();
      setAccessToken(tokens.access_token);
      setUser(oauthUser);
      setError(null);
      return true;
    } catch (err) {
      console.error('OAuth callback failed:', err);
      setError(err.message || 'Authentication failed');
      // Clear the callback from URL to prevent loop
      window.history.replaceState({}, document.title, window.location.pathname);
      return false;
    }
  }, []);

  // Check authentication on mount
  const checkAuth = useCallback(async () => {
    try {
      setLoading(true);

      if (authMethod === 'oauth') {
        // First check if there's a callback to process
        const callbackProcessed = await processOAuthCallback();
        if (!callbackProcessed) {
          // No callback, check stored tokens
          checkOAuthAuth();
        }
      } else {
        // OTP auth - check session
        await checkOTPAuth();
      }
    } finally {
      setLoading(false);
    }
  }, [authMethod, processOAuthCallback, checkOAuthAuth, checkOTPAuth]);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // Listen for session expiry events from API client
  useEffect(() => {
    const handleSessionExpired = () => {
      console.warn('Session expired, logging out...');
      setUser(null);
      setAccessToken(null);
      setError('Your session has expired. Please log in again.');

      if (authMethod === 'oauth') {
        oauthLogout(false);
      }
    };

    window.addEventListener('auth:sessionExpired', handleSessionExpired);
    return () => window.removeEventListener('auth:sessionExpired', handleSessionExpired);
  }, [authMethod]);

  // Login - called after successful OTP verification (OTP mode only)
  const login = useCallback((email) => {
    setUser({ email });
    setError(null);
  }, []);

  // Initiate OAuth login (OAuth mode only)
  const loginWithOAuth = useCallback(() => {
    initiateOAuthLogin();
  }, []);

  // Logout
  const logout = useCallback(async () => {
    try {
      if (authMethod === 'oauth') {
        // Clear local state first
        setUser(null);
        setAccessToken(null);
        setError(null);
        // Redirect to Auth0 logout to end the SSO session
        oauthLogout(true);
        // Note: This will redirect, so code below won't execute
        return;
      } else {
        await apiLogout();
      }
    } catch (err) {
      console.error('Logout failed:', err);
    } finally {
      // Clear all auth state (for OTP mode)
      setUser(null);
      setAccessToken(null);
      setError(null);

      if (import.meta.env.DEV) {
        console.log('Auth: Logout complete, state cleared');
      }
    }
  }, [authMethod]);

  // Get current access token (for API calls)
  const getToken = useCallback(() => {
    if (authMethod === 'oauth') {
      return getAccessToken();
    }
    return null; // OTP uses session cookies, no token needed
  }, [authMethod]);

  const value = {
    user,
    accessToken,
    loading,
    error,
    isAuthenticated: !!user,
    authMethod,
    login,           // For OTP mode
    loginWithOAuth,  // For OAuth mode
    logout,
    checkAuth,
    getToken,
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
