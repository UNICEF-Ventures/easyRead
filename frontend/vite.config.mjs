import { defineConfig } from 'vite'
import reactplugin from '@vitejs/plugin-react'
import federation from '@originjs/vite-plugin-federation'
import * as dotenv from 'dotenv';
import * as dotenvExpand from 'dotenv-expand';
import path from 'path';
import tailwindcss from "@tailwindcss/vite";

dotenvExpand.expand(dotenv.config())

const devHost = process.env.VITE_HOST || '127.0.0.1';
const devPort = Number(process.env.VITE_PORT || '5173');

export default defineConfig({
  plugins: [
    tailwindcss(),
    reactplugin(),
    federation({
      name: "sample",
      filename: "remoteEntry.js",
      exposes: {
         './App': './src/App'
      },
      shared: {
        'react': {
          import: true,
          //singleton: true,
          requiredVersion: '18.3.1',
        },
        'react-dom': {
          import: true,
          //singleton: true,
          requiredVersion: '18.3.1',
        },
      },
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'), // This makes @ point to /src
    },
  },
  server: {
    host: devHost,
    port: devPort,
    strictPort: true,
  },
  base: process.env.NODE_ENV == 'production' ? process.env.VITE_BASE_URL_PROD : process.env.VITE_BASE_URL,
  build: {
    rollupOptions: {
      external:[],
    },
    modulePreload: false,
    target: 'esnext',
    minify: false,
    cssCodeSplit: false
  }
})
