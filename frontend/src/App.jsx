import React, { useState, useMemo } from 'react';
import { Routes, Route, useNavigate, Link, BrowserRouter, useLocation } from 'react-router-dom';
import IntroPage from './components/IntroPage';
import HomePage from './components/HomePage';
import ResultPage from './components/ResultPage';
import AdminRoute from './components/AdminRoute';
import SavedContentPage from './components/SavedContentPage';
import SavedContentDetailPage from './components/SavedContentDetailPage';
import LoginPage from './components/LoginPage';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Box, CssBaseline, Typography, Alert, CircularProgress, LinearProgress, AppBar, Toolbar, Button } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';

// Core App component that requires router context
function AppCore() {
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth();
  const [markdownContent, setMarkdownContent] = useState('');
  const [easyReadContent, setEasyReadContent] = useState([]);
  const [contentTitle, setContentTitle] = useState('');
  const [selectedSets, setSelectedSets] = useState([]);
  const [preventDuplicateImages, setPreventDuplicateImages] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessingPages, setIsProcessingPages] = useState(false);
  const [totalPages, setTotalPages] = useState(0);
  const [pagesProcessed, setPagesProcessed] = useState(0);
  const [currentProcessingStep, setCurrentProcessingStep] = useState('');
  const [error, setError] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();

  // Must call useMemo before any conditional returns (React hooks rule)
  const progressPercent = useMemo(() => {
    return totalPages > 0 ? (pagesProcessed / totalPages) * 100 : 0;
  }, [totalPages, pagesProcessed]);

  // Only show header on pages that need it (not on intro page or login)
  const shouldShowHeader = location.pathname !== '/' && isAuthenticated;

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const AppHeader = () => (
    <AppBar position="static" sx={{ mb: 3 }}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          EasyRead Generator
        </Typography>
        <Button color="inherit" component={Link} to="/easyread">
          Home
        </Button>
        <Button color="inherit" component={Link} to="/saved">
          Saved Content
        </Button>
        {user && (
          <>
            <Typography variant="body2" sx={{ ml: 2, mr: 1, opacity: 0.8 }}>
              {user.email}
            </Typography>
            <Button color="inherit" onClick={handleLogout} startIcon={<LogoutIcon />}>
              Logout
            </Button>
          </>
        )}
      </Toolbar>
    </AppBar>
  );

  // Show loading while checking auth
  if (authLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh' }}>
        <CircularProgress />
      </Box>
    );
  }

  // Show login page if not authenticated
  if (!isAuthenticated) {
    return <LoginPage />;
  }

  const handleProcessingComplete = (finalMarkdown, finalEasyRead) => {
    console.log("App: Processing complete");
    let newTitle = 'Untitled';
    let newContent = [];
    let newSelectedSets = [];
    let newPreventDuplicates = true;
    let errorMsg = null;

    // Determine final state values based on the result
    if (finalEasyRead && typeof finalEasyRead === 'object' && finalEasyRead.easy_read_sentences) {
      newTitle = finalEasyRead.title || 'Untitled';
      newContent = finalEasyRead.easy_read_sentences; // Get the final array reference
      newSelectedSets = finalEasyRead.selected_sets || [];
      newPreventDuplicates = finalEasyRead.prevent_duplicate_images ?? true;
    } else {
      newTitle = 'Processing Error'; 
      newContent = []; 
      newSelectedSets = [];
      newPreventDuplicates = true;
      errorMsg = 'Received invalid format from easy read generation.';
      console.error('Invalid easy read content format:', finalEasyRead);
    }
    
    // Update all state at once before navigating
    setMarkdownContent(finalMarkdown);
    setContentTitle(newTitle);
    setEasyReadContent(newContent);
    setSelectedSets(newSelectedSets);
    setPreventDuplicateImages(newPreventDuplicates);
    setIsLoading(false);
    setIsProcessingPages(false);
    setTotalPages(0);
    setPagesProcessed(0);
    setError(errorMsg);
    
    // Navigate after state updates
    navigate('/results', { state: { fromProcessing: true } });
  };


  return (
    <Box>
      <CssBaseline />
      {shouldShowHeader && <AppHeader />}
      
      {isLoading && !isProcessingPages && (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
             <CircularProgress />
          </Box>
      )}
      {isProcessingPages && (
          <Box
            sx={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(255, 255, 255, 0.3)',
              backdropFilter: 'blur(8px)',
              WebkitBackdropFilter: 'blur(8px)',
              zIndex: 1300,
            }}
          >
            <Box
              sx={{
                width: '90%',
                maxWidth: 500,
                p: 4,
                bgcolor: 'white',
                borderRadius: 3,
                boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15)',
              }}
            >
              <Typography variant="h6" sx={{ mb: 1, textAlign: 'center', fontWeight: 'bold' }}>
                Processing page {Math.ceil(pagesProcessed)} of {totalPages}...
              </Typography>
              {currentProcessingStep && (
                <Typography variant="body2" sx={{ mb: 2, textAlign: 'center', color: 'primary.main', fontStyle: 'italic' }}>
                  {currentProcessingStep}
                </Typography>
              )}
              <LinearProgress
                variant="determinate"
                value={progressPercent}
                sx={{ height: 12, borderRadius: 6 }}
              />
              <Typography variant="body1" sx={{ mt: 2, textAlign: 'center', color: 'text.secondary', fontWeight: 500 }}>
                {Math.round(progressPercent)}% complete
              </Typography>
            </Box>
          </Box>
      )}
      {error && (
          <Alert severity="error" sx={{ mx: 'auto', maxWidth: 'md', my: 2 }}>{error}</Alert>
      )}

      <Routes>
        <Route 
          path="/" 
          element={<IntroPage />}
        />
        <Route 
          path="/easyread" 
          element={
            <HomePage 
              setMarkdownContent={setMarkdownContent}
              setIsLoading={setIsLoading}
              setIsProcessingPages={setIsProcessingPages}
              setTotalPages={setTotalPages}
              setPagesProcessed={setPagesProcessed}
              setCurrentProcessingStep={setCurrentProcessingStep}
              setError={setError}
              currentMarkdown={markdownContent}
              onProcessingComplete={handleProcessingComplete}
            />
          }
        />
        <Route 
          path="/results" 
          element={
             <ResultPage 
                title={contentTitle}
                markdownContent={markdownContent}
                easyReadContent={easyReadContent}
                selectedSets={selectedSets}
                preventDuplicateImages={preventDuplicateImages}
             />
            }
        />
        <Route
          path="/admin"
          element={<AdminRoute />}
        />
        <Route 
          path="/saved" 
          element={<SavedContentPage />} 
        />
        <Route 
          path="/saved/:id" 
          element={<SavedContentDetailPage />} 
        />
      </Routes>
    </Box>
  );
}

// Main App wrapper that provides router context for both standalone and federated use
function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppCore />
      </AuthProvider>
    </BrowserRouter>
  );
}

// Export both the wrapped App (for standalone use) and AppCore (for federated use with custom routing)
export { AppCore };
export default App;
