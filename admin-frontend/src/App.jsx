import React, { useState, useMemo, useEffect } from 'react';
import { Routes, Route, useNavigate, BrowserRouter, useLocation, Navigate } from 'react-router-dom';
import AdminRoute from './components/AdminRoute';
import { Box, CssBaseline, Typography, Alert, CircularProgress, LinearProgress } from '@mui/material';
import axios from 'axios';
import { getApiKey } from "playground_commons";
import IntroPage from './components/IntroPage';

// Core App component that requires router context
function AppCore({ token, apiKey, email }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
 
  return (
    <Box>
      <CssBaseline />

      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
          <CircularProgress />
        </Box>
      )}
      
      {error && (
        <Alert severity="error" sx={{ mx: 'auto', maxWidth: 'md', my: 2 }}>{error}</Alert>
      )}
      <Routes>
        <Route
          path="/easyread"
        >
          <Route
            index
            element={
              <IntroPage

              />
            }
          />


        </Route>
        <Route
          path="admin"
          element={<AdminRoute />}
        />
        <Route
          path="*"
          element={<Navigate to="/easyread" replace />}
        />
      </Routes>
    </Box>
  );
}

// Main App wrapper that provides router context for both standalone and federated use
function App({ user, accessToken }) {
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      console.log("App useEffect - accessToken:", accessToken, "type:", typeof accessToken);
      console.log("App useEffect - user:", user);

      // Only try to get API key if running in federated/platform mode (with accessToken)
      if (!accessToken) {
        console.log("Running in standalone mode - skipping API key fetch");
        setLoading(false);
        return;
      }

      try {
        console.log("Loading metadata for federated mode");
        setLoading(true);
        const key = await getApiKey(import.meta.env.VITE_API_STAGE ?? "dev", accessToken, import.meta.env.VITE_PROJECT_KEY);
        setApiKey(key);
        console.log("API key loaded successfully");
      } catch (error) {
        console.error("Error loading API key:", error);
        if (axios.isAxiosError(error)) {
          if (error.response && error.response.status === 429) {
            console.error('❌ Rate limit hit (429):', error.response.data);
            setError('Too many requests. Please try again later.');
            return;
          }
        }
        setError("Something went wrong. Try refreshing!");
      } finally {
        setLoading(false);
      }

    }
    load();

  }, [accessToken, user]);
  return (
    <BrowserRouter>
      {error && (
        <Alert severity="error" sx={{ mx: 'auto', maxWidth: 'md', my: 2 }}>{error}</Alert>
      )}
      {loading ? <div className='w-full items-center align-center flex justify-center'><CircularProgress classNames={{
        label: "text-primary text-sm"
      }} color='primary' /></div>
        : <AppCore token={accessToken} apiKey={apiKey} email={user.email} />}
    </BrowserRouter>
  );
}

// Export both the wrapped App (for standalone use) and AppCore (for federated use with custom routing)
export { AppCore };
export default App;
