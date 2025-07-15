import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Clear dev server config for consistent behavior
  server: {
    host: 'localhost',
    port: 5173
  }
})
