import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import federation from '@originjs/vite-plugin-federation'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on mode (development/production)
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [
      react(),
      federation({
        name: "easyread", // Unique name for EasyRead
        filename: "remoteEntry.js",
        exposes: {
          './Demo': './src/Demo',
          // Expose the main App component (with BrowserRouter) for federation
          // './App': './src/App',
          // // Expose the core component (without router) for custom routing contexts
          // './AppCore': './src/App',
        },
        shared: ['react', 'react-dom'] // Shared dependencies
      })
    ],
    server: {
      host: 'localhost',
      strictPort: true
    },
    // Use the VITE_BASE_URL for the base path
    base: process.env.NODE_ENV == 'production' ? process.env.VITE_BASE_URL_PROD : process.env.VITE_BASE_URL,
    build: {
      target: 'esnext'
    }
  }
})
