**How to Set Up a Conformant Prototype:**

1.  **Initialize Project:**
    *   Start with a standard React + Vite project.
    *   You can use `npm create vite@latest your-prototype-name -- --template react`.

2.  **Install Federation Plugin:**
    *   Add the module federation plugin: `npm install @originjs/vite-plugin-federation --save-dev`

3.  **Configure `.env`:**
    *   Create a `.env` file in the project root.
    *   Add the base URL where your prototype will run locally:
        ```env
        VITE_BASE_URL='http://localhost:5001'
        # Choose an unused port (e.g., 5001, 5002, etc.)
        ```

4.  **Configure `vite.config.js`:**
    *   Import and add the `federation` plugin.
    *   Define the `exposes` section to share your main app component (usually `src/App.jsx` or similar). **Do not** expose the file where `ReactDOM.createRoot` is called (e.g., `src/main.jsx`).
    *   Ensure `react` and `react-dom` are in the `shared` array.
    *   Set the `base` option using the `.env` variable.

    ```javascript
    // vite.config.js (Example Snippet)
    import { defineConfig, loadEnv } from 'vite'
    import react from '@vitejs/plugin-react'
    import federation from '@originjs/vite-plugin-federation'

    export default defineConfig(({ mode }) => {
      // Load env file based on mode (development/production)
      const env = loadEnv(mode, process.cwd(), '');

      return {
        plugins: [
          react(),
          federation({
            name: "my_prototype_app", // Choose a unique name
            filename: "remoteEntry.js",
            exposes: {
              // Expose your main component (e.g., App.jsx)
              './App': './src/App',
            },
            shared: ['react', 'react-dom'] // Add other shared dependencies if needed
          })
        ],
        server: {
          port: 5001, // Match the port in .env
          strictPort: true
        },
        // Use the VITE_BASE_URL for the base path
        base: env.VITE_BASE_URL || '/',
        build: {
          target: 'esnext',
          // ... other build options if needed
        }
        // ... other vite config
      }
    })
    ```

5.  **Verify Entry Point (`src/main.jsx`):**
    *   Ensure your main entry point (`src/main.jsx` or similar) imports and renders your main application component (`./App` in the example above).

    ```javascript
    // src/main.jsx (Example)
    import React from 'react'
    import ReactDOM from 'react-dom/client'
    import App from './App' // The component being exposed

    ReactDOM.createRoot(document.getElementById('root')).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>,
    )
    ```

6.  **Add Start Script (`package.json`):**
    *   Include a `start` script for easy local testing (builds and serves).

    ```json
    // package.json (scripts section)
    "scripts": {
      // ... other scripts like dev, build, preview ...
      "start": "vite build --watch & vite preview --port 5001" // Adjust port if needed
      // Or use concurrently as shown in the example repo
    },
    ```

7.  **Place Assets:**
    *   Store images and other static assets in the `src/assets` folder. Reference them correctly in your components (Vite handles asset paths during build).

8.  **(Optional) Add Deployment:**
    *   If deploying to S3, consider adding a deployment script, potentially in a `deploy/` directory (e.g., `deploy/deploy-to-s3.js`) as mentioned in the starter README.

Following these steps will create a prototype project structured correctly for integration into the main Playground application via module federation.
