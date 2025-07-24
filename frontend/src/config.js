/**
 * Configuration file for API and media URLs
 * This provides a centralized place to manage URLs with reliable defaults
 */

// Configuration object - Use environment variables with fallbacks
export const config = {
  // API Configuration - Use environment variables with fallbacks
  API_BASE_URL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  MEDIA_BASE_URL: import.meta.env.VITE_MEDIA_BASE_URL || 'http://localhost:8000',
  
  // Development flags
  IS_DEVELOPMENT: import.meta.env.DEV,
  IS_PRODUCTION: import.meta.env.PROD,
};

// Debug logging only in development
if (import.meta.env.DEV) {
  console.log('🔧 Application Configuration:', {
    API_BASE_URL: config.API_BASE_URL,
    MEDIA_BASE_URL: config.MEDIA_BASE_URL,
    IS_DEVELOPMENT: config.IS_DEVELOPMENT
  });
}

export default config;