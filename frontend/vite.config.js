import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import federation from '@originjs/vite-plugin-federation'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on mode (development/production)
  const env = loadEnv(mode, process.cwd(), '');

  // Debug: Log loaded environment variables (only in development)
  if (mode === 'development') {
    console.log('Vite build mode:', mode);
    console.log('VITE_AUTH_METHOD:', env.VITE_AUTH_METHOD);
  }

  return {
    plugins: [
      react(),
      federation({
        name: "easyread_prototype", // Unique name for EasyRead
        filename: "remoteEntry.js",
        exposes: {
          // Expose the main App component (with BrowserRouter) for federation
          './App': './src/App',
          // Expose the core component (without router) for custom routing contexts
          './AppCore': './src/App',
        },
        shared: ['react', 'react-dom'] // Shared dependencies
      })
    ],
    server: {
      host: 'localhost',
      port: 5001, // Federation conformant port
      strictPort: true
    },
    // Use the VITE_BASE_URL for the base path
    base: env.VITE_BASE_URL || '/',
    build: {
      target: 'esnext'
    },
    // Explicitly define environment variables to ensure they're embedded in build
    // These values come from Docker build args (process.env) or .env files (env)
    define: {
      'import.meta.env.VITE_API_BASE_URL': JSON.stringify(process.env.VITE_API_BASE_URL || env.VITE_API_BASE_URL || '/api'),
      'import.meta.env.VITE_MEDIA_BASE_URL': JSON.stringify(process.env.VITE_MEDIA_BASE_URL || env.VITE_MEDIA_BASE_URL || ''),
      'import.meta.env.VITE_AUTH_METHOD': JSON.stringify(process.env.VITE_AUTH_METHOD || env.VITE_AUTH_METHOD || 'otp'),
      'import.meta.env.VITE_OIDC_DOMAIN': JSON.stringify(process.env.VITE_OIDC_DOMAIN || env.VITE_OIDC_DOMAIN || ''),
      'import.meta.env.VITE_OIDC_AUTH_DOMAIN': JSON.stringify(process.env.VITE_OIDC_AUTH_DOMAIN || env.VITE_OIDC_AUTH_DOMAIN || 'https://auth.ooiplayground.com'),
      'import.meta.env.VITE_OIDC_CLIENT_ID': JSON.stringify(process.env.VITE_OIDC_CLIENT_ID || env.VITE_OIDC_CLIENT_ID || ''),
      'import.meta.env.VITE_OAUTH_NAMESPACE': JSON.stringify(process.env.VITE_OAUTH_NAMESPACE || env.VITE_OAUTH_NAMESPACE || 'https://ooi-playground.com'),
      'import.meta.env.VITE_PROJECT_KEY': JSON.stringify(process.env.VITE_PROJECT_KEY || env.VITE_PROJECT_KEY || 'easyread'),
    }
  }
})
