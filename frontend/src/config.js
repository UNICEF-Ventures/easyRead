/**
 * Configuration file for API and media URLs
 * This provides a centralized place to manage URLs with reliable defaults
 */

// Detect if we're running in a containerized environment
const isContainerized = () => {
  // Check if we're accessing via localhost:3000 (containerized frontend)
  // or if VITE_API_BASE_URL is set to relative path
  return window.location.port === '3000' ||
         import.meta.env.VITE_API_BASE_URL?.startsWith('/');
};

// Authentication method: 'otp' (email code) or 'oauth' (playground OIDC)
const getAuthMethod = () => {
  const method = import.meta.env.VITE_AUTH_METHOD?.toLowerCase() || 'otp';
  return ['otp', 'oauth'].includes(method) ? method : 'otp';
};

// Configuration object - Use environment variables with fallbacks
export const config = {
  // API Configuration - Use environment variables with fallbacks
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',

  // Media URL handling: use relative URLs in containerized environment
  MEDIA_BASE_URL: isContainerized() ? '' : (import.meta.env.VITE_MEDIA_BASE_URL || 'http://localhost:8000'),

  // Development flags
  IS_DEVELOPMENT: import.meta.env.DEV,
  IS_PRODUCTION: import.meta.env.PROD,
  IS_CONTAINERIZED: isContainerized(),

  // Feature flags
  ENABLE_IMAGE_GENERATION: (import.meta.env.VITE_ENABLE_IMAGE_GENERATION ?? 'false') === 'true',

  // Authentication configuration
  // 'otp' = Email OTP authentication (default, standalone mode)
  // 'oauth' = OAuth/OIDC via ooiplayground Auth0
  AUTH_METHOD: getAuthMethod(),

  // OAuth/OIDC Configuration (only used when AUTH_METHOD='oauth')
  OAUTH: {
    DOMAIN: import.meta.env.VITE_OIDC_AUTH_DOMAIN || 'https://auth.ooiplayground.com',
    CLIENT_ID: import.meta.env.VITE_OIDC_CLIENT_ID || '',
    NAMESPACE: import.meta.env.VITE_OAUTH_NAMESPACE || 'https://ooi-playground.com',
  },
};

// Debug logging only in development
if (import.meta.env.DEV) {
  console.log('🔧 Application Configuration:', {
    API_BASE_URL: config.API_BASE_URL,
    MEDIA_BASE_URL: config.MEDIA_BASE_URL,
    IS_DEVELOPMENT: config.IS_DEVELOPMENT,
    IS_CONTAINERIZED: config.IS_CONTAINERIZED,
    AUTH_METHOD: config.AUTH_METHOD,
  });
}

export default config;