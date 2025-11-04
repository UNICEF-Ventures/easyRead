import React, { useState, useMemo } from 'react';
import { Routes, Route, useNavigate, Link, BrowserRouter, useLocation } from 'react-router-dom';
import IntroPage from './components/IntroPage';
import HomePage from './components/HomePage';
import ResultPage from './components/ResultPage';
import AdminRoute from './components/AdminRoute';
import SavedContentPage from './components/SavedContentPage';
import SavedContentDetailPage from './components/SavedContentDetailPage';
import { Box, CssBaseline, Typography, Alert, CircularProgress, LinearProgress, AppBar, Toolbar, Button } from '@mui/material';

// Core App component that requires router context
function AppCore({ token, apiKey, email }) {
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

  // Only show header on pages that need it (not on intro page)
  const shouldShowHeader = location.pathname !== '/';

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
      </Toolbar>
    </AppBar>
  );

  const progressPercent = useMemo(() => {
    return totalPages > 0 ? (pagesProcessed / totalPages) * 100 : 0;
  }, [totalPages, pagesProcessed]);



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
        <Box sx={{ width: '80%', mx: 'auto', my: 3, maxWidth: 'md', p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
          <Typography variant="body1" sx={{ mb: 1, textAlign: 'center', fontWeight: 'bold' }}>
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
            sx={{ height: 10, borderRadius: 5 }}
          />
          <Typography variant="body2" sx={{ mt: 1, textAlign: 'center', color: 'text.secondary' }}>
            {Math.round(progressPercent)}% complete
          </Typography>
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
              token={token}
              apiKey={apiKey}
              email={email}
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
function App({ token, apiKey, email }) {
  return (
    <BrowserRouter>
      <AppCore token={token} apiKey={apiKey} email={email} />
    </BrowserRouter>
  );
}

// Export both the wrapped App (for standalone use) and AppCore (for federated use with custom routing)
export { AppCore };
export default App;
