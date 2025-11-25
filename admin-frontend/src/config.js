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
};

// Debug logging only in development
if (import.meta.env.DEV) {
  console.log('🔧 Application Configuration:', {
    API_BASE_URL: config.API_BASE_URL,
    MEDIA_BASE_URL: config.MEDIA_BASE_URL,
    IS_DEVELOPMENT: config.IS_DEVELOPMENT,
    IS_CONTAINERIZED: config.IS_CONTAINERIZED
  });
}

export default config;