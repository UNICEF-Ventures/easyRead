/**
 * Configuration file for API and media URLs
 * This provides a centralized place to manage URLs with reliable defaults
 */

// Configuration object - FORCE correct defaults to override caching issues
export const config = {
  // API Configuration - Force port 8000 for now
  API_BASE_URL: 'http://localhost:8000/api',
  MEDIA_BASE_URL: 'http://localhost:8000',
  
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