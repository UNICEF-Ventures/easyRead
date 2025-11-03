import { defineConfig } from 'vite'
import reactplugin from '@vitejs/plugin-react'
import federation from '@originjs/vite-plugin-federation'
import * as dotenv from 'dotenv';
import * as dotenvExpand from 'dotenv-expand';
import path from 'path';
import tailwindcss from "@tailwindcss/vite";

dotenvExpand.expand(dotenv.config())


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
