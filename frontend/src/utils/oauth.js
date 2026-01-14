/**
 * OAuth 2.0 PKCE utilities for Auth0/OIDC authentication.
 *
 * This module handles the OAuth authorization code flow with PKCE
 * for secure authentication without a client secret.
 */

// Auth0 configuration from environment variables
const AUTH_CONFIG = {
  domain: import.meta.env.VITE_OIDC_AUTH_DOMAIN || 'https://auth.ooiplayground.com',
  clientId: import.meta.env.VITE_OIDC_CLIENT_ID || '',
  // Use root path since /callback isn't allowed for port 5173
  redirectUri: `${window.location.origin}`,
  scope: 'openid profile email',
  audience: import.meta.env.VITE_OIDC_DOMAIN
    ? `${import.meta.env.VITE_OIDC_DOMAIN.replace(/\/$/, '')}/api/v2/`
    : '',
  namespace: import.meta.env.VITE_OAUTH_NAMESPACE || 'https://ooi-playground.com',
};

// Storage keys
const STORAGE_KEYS = {
  codeVerifier: 'oauth_code_verifier',
  state: 'oauth_state',
  accessToken: 'oauth_access_token',
  idToken: 'oauth_id_token',
  refreshToken: 'oauth_refresh_token',
  user: 'oauth_user',
  expiresAt: 'oauth_expires_at',
  callbackProcessing: 'oauth_callback_processing',
};

// Use sessionStorage for tokens (more secure - cleared on tab close)
// This reduces XSS attack surface compared to localStorage
const tokenStorage = sessionStorage;

/**
 * Generate a random string for PKCE code verifier and state
 * Uses rejection sampling to avoid modulo bias
 */
function generateRandomString(length = 64) {
  const charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~';
  const charsetLength = charset.length; // 66 characters
  // Calculate the largest multiple of charsetLength that fits in a byte (256)
  // This ensures uniform distribution by rejecting values >= maxValid
  const maxValid = Math.floor(256 / charsetLength) * charsetLength; // 264 > 256, so use 198

  const result = [];
  while (result.length < length) {
    const randomValues = crypto.getRandomValues(new Uint8Array(length - result.length));
    for (const v of randomValues) {
      if (v < maxValid && result.length < length) {
        result.push(charset[v % charsetLength]);
      }
    }
  }
  return result.join('');
}

/**
 * Generate SHA-256 hash and base64url encode it for PKCE challenge
 */
async function generateCodeChallenge(codeVerifier) {
  const encoder = new TextEncoder();
  const data = encoder.encode(codeVerifier);
  const digest = await crypto.subtle.digest('SHA-256', data);

  // Base64url encode (no padding, URL safe)
  const base64 = btoa(String.fromCharCode(...new Uint8Array(digest)));
  return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/**
 * Initiate OAuth login by redirecting to Auth0
 */
export async function initiateOAuthLogin() {
  // Generate PKCE parameters
  const codeVerifier = generateRandomString(64);
  const codeChallenge = await generateCodeChallenge(codeVerifier);
  const state = generateRandomString(32);

  // Store for later verification
  sessionStorage.setItem(STORAGE_KEYS.codeVerifier, codeVerifier);
  sessionStorage.setItem(STORAGE_KEYS.state, state);

  // Build authorization URL
  const params = new URLSearchParams({
    response_type: 'code',
    client_id: AUTH_CONFIG.clientId,
    redirect_uri: AUTH_CONFIG.redirectUri,
    scope: AUTH_CONFIG.scope,
    state: state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  // Add audience if configured
  if (AUTH_CONFIG.audience) {
    params.append('audience', AUTH_CONFIG.audience);
  }

  const authUrl = `${AUTH_CONFIG.domain}/authorize?${params.toString()}`;

  if (import.meta.env.DEV) {
    console.log('OAuth: Redirecting to authorization URL:', authUrl);
  }

  // Redirect to Auth0
  window.location.href = authUrl;
}

/**
 * Check if there's an OAuth callback in the URL
 */
export function hasOAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const hasCallback = params.has('code') && params.has('state');

  // Don't process if we're already processing or have already processed this callback
  if (hasCallback && sessionStorage.getItem(STORAGE_KEYS.callbackProcessing)) {
    return false;
  }

  return hasCallback;
}

/**
 * Handle OAuth callback - exchange code for tokens
 */
export async function handleOAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const state = params.get('state');
  const error = params.get('error');
  const errorDescription = params.get('error_description');

  // Mark that we're processing to prevent double execution (React Strict Mode, etc.)
  sessionStorage.setItem(STORAGE_KEYS.callbackProcessing, 'true');

  // Clean up URL immediately to prevent re-processing on re-renders
  // Do this early because the code is single-use
  window.history.replaceState({}, document.title, window.location.pathname);

  try {
    // Check for errors
    if (error) {
      throw new Error(errorDescription || error);
    }

    if (!code || !state) {
      throw new Error('Missing code or state in callback');
    }

    // Verify state
    const storedState = sessionStorage.getItem(STORAGE_KEYS.state);
    if (state !== storedState) {
      throw new Error('State mismatch - possible CSRF attack');
    }

    // Get code verifier
    const codeVerifier = sessionStorage.getItem(STORAGE_KEYS.codeVerifier);
    if (!codeVerifier) {
      throw new Error('Code verifier not found - session may have expired');
    }

    // Exchange code for tokens
    const tokenResponse = await fetch(`${AUTH_CONFIG.domain}/oauth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: AUTH_CONFIG.clientId,
        code: code,
        redirect_uri: AUTH_CONFIG.redirectUri,
        code_verifier: codeVerifier,
      }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.json().catch(() => ({}));
      throw new Error(errorData.error_description || errorData.error || 'Token exchange failed');
    }

    const tokens = await tokenResponse.json();

    // Clean up PKCE session storage (no longer needed)
    sessionStorage.removeItem(STORAGE_KEYS.codeVerifier);
    sessionStorage.removeItem(STORAGE_KEYS.state);

    // Parse user info from ID token or fetch from userinfo endpoint
    const user = await getUserFromTokens(tokens);

    // Store tokens
    storeTokens(tokens, user);

    return { tokens, user };
  } finally {
    // Clear the processing flag
    sessionStorage.removeItem(STORAGE_KEYS.callbackProcessing);
  }
}

/**
 * Parse user information from tokens
 */
async function getUserFromTokens(tokens) {
  // Try to parse ID token first
  if (tokens.id_token) {
    try {
      const payload = parseJwt(tokens.id_token);
      return extractUserFromPayload(payload);
    } catch (e) {
      console.warn('OAuth: Failed to parse ID token, falling back to userinfo endpoint');
    }
  }

  // Fallback: fetch from userinfo endpoint
  const userInfoResponse = await fetch(`${AUTH_CONFIG.domain}/userinfo`, {
    headers: {
      Authorization: `Bearer ${tokens.access_token}`,
    },
  });

  if (userInfoResponse.ok) {
    const userInfo = await userInfoResponse.json();
    return extractUserFromPayload(userInfo);
  }

  // If all else fails, parse access token
  if (tokens.access_token) {
    const payload = parseJwt(tokens.access_token);
    return extractUserFromPayload(payload);
  }

  throw new Error('Could not extract user information from tokens');
}

/**
 * Extract user info from JWT payload
 */
function extractUserFromPayload(payload) {
  const namespace = AUTH_CONFIG.namespace;

  return {
    sub: payload.sub,
    email: payload[`${namespace}/email`] || payload.email || '',
    name: payload.name || payload.nickname || '',
    roles: payload[`${namespace}/roles`] || '',
    allowedProjects: payload[`${namespace}/allowed-projects`] || [],
  };
}

/**
 * Parse a JWT token (without verification - verification happens on backend)
 */
function parseJwt(token) {
  const parts = token.split('.');
  if (parts.length !== 3) {
    throw new Error('Invalid JWT format');
  }

  const payload = parts[1];
  // Handle base64url encoding
  const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
  const padded = base64 + '='.repeat((4 - base64.length % 4) % 4);

  return JSON.parse(atob(padded));
}

/**
 * Store tokens in sessionStorage (more secure than localStorage)
 */
function storeTokens(tokens, user) {
  tokenStorage.setItem(STORAGE_KEYS.accessToken, tokens.access_token);

  if (tokens.id_token) {
    tokenStorage.setItem(STORAGE_KEYS.idToken, tokens.id_token);
  }

  if (tokens.refresh_token) {
    tokenStorage.setItem(STORAGE_KEYS.refreshToken, tokens.refresh_token);
  }

  tokenStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));

  // Calculate expiration time
  const expiresAt = Date.now() + (tokens.expires_in || 3600) * 1000;
  tokenStorage.setItem(STORAGE_KEYS.expiresAt, expiresAt.toString());
}

/**
 * Get stored access token (returns null if expired)
 */
export function getAccessToken() {
  const token = tokenStorage.getItem(STORAGE_KEYS.accessToken);
  const expiresAt = parseInt(tokenStorage.getItem(STORAGE_KEYS.expiresAt) || '0', 10);

  // Check if token is expired
  if (!token || Date.now() >= expiresAt) {
    return null;
  }

  return token;
}

/**
 * Get stored refresh token
 */
export function getRefreshToken() {
  return tokenStorage.getItem(STORAGE_KEYS.refreshToken);
}

/**
 * Get stored user
 */
export function getStoredUser() {
  const userJson = tokenStorage.getItem(STORAGE_KEYS.user);
  if (!userJson) return null;

  try {
    return JSON.parse(userJson);
  } catch {
    return null;
  }
}

/**
 * Check if user is authenticated via OAuth
 */
export function isOAuthAuthenticated() {
  return !!getAccessToken();
}

/**
 * Check if access token is expired or about to expire (within 60 seconds)
 */
export function isTokenExpired() {
  const expiresAt = parseInt(tokenStorage.getItem(STORAGE_KEYS.expiresAt) || '0', 10);
  // Consider expired if within 60 seconds of expiration
  return Date.now() >= (expiresAt - 60000);
}

/**
 * Refresh the access token using the refresh token
 * Returns the new tokens if successful, null otherwise
 */
export async function refreshAccessToken() {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    if (import.meta.env.DEV) {
      console.log('OAuth: No refresh token available');
    }
    return null;
  }

  try {
    const tokenResponse = await fetch(`${AUTH_CONFIG.domain}/oauth/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: AUTH_CONFIG.clientId,
        refresh_token: refreshToken,
      }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.json().catch(() => ({}));
      console.error('OAuth: Token refresh failed:', errorData);
      return null;
    }

    const tokens = await tokenResponse.json();

    // Get existing user data (refresh doesn't return user info)
    const existingUser = getStoredUser();

    // Store the new tokens
    storeTokens(tokens, existingUser);

    if (import.meta.env.DEV) {
      console.log('OAuth: Token refreshed successfully');
    }

    return tokens;
  } catch (error) {
    console.error('OAuth: Token refresh error:', error);
    return null;
  }
}

/**
 * Get a valid access token, refreshing if necessary
 * Returns the token or null if unable to get one
 */
export async function getValidAccessToken() {
  // Check if we have a valid (non-expired) token
  const currentToken = getAccessToken();
  if (currentToken) {
    return currentToken;
  }

  // Token is expired or missing, try to refresh
  const refreshed = await refreshAccessToken();
  if (refreshed) {
    return refreshed.access_token;
  }

  // Unable to get a valid token
  return null;
}

/**
 * Clear all stored auth data (logout)
 */
export function clearOAuthData() {
  Object.values(STORAGE_KEYS).forEach(key => {
    // Clear from all storage locations to ensure complete logout
    tokenStorage.removeItem(key);
    sessionStorage.removeItem(key);
    localStorage.removeItem(key);  // Also clear localStorage for legacy cleanup
  });

  if (import.meta.env.DEV) {
    console.log('OAuth: Cleared all auth data from storage');
  }
}

/**
 * Logout - clear local data and optionally redirect to Auth0 logout
 */
export function oauthLogout(redirectToAuth0 = false) {
  clearOAuthData();

  if (redirectToAuth0) {
    const logoutUrl = new URL(`${AUTH_CONFIG.domain}/oidc/logout`);
    logoutUrl.searchParams.set('client_id', AUTH_CONFIG.clientId);
    logoutUrl.searchParams.set('returnTo', window.location.origin);
    window.location.href = logoutUrl.toString();
  }
}

/**
 * Get auth configuration (for debugging)
 */
export function getAuthConfig() {
  return { ...AUTH_CONFIG };
}

export default {
  initiateOAuthLogin,
  hasOAuthCallback,
  handleOAuthCallback,
  getAccessToken,
  getRefreshToken,
  getValidAccessToken,
  getStoredUser,
  isOAuthAuthenticated,
  isTokenExpired,
  refreshAccessToken,
  clearOAuthData,
  oauthLogout,
  getAuthConfig,
};
