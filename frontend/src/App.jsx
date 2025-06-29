import React, { useState } from 'react';
import { Routes, Route, useNavigate, Link } from 'react-router-dom';
import HomePage from './components/HomePage';
import ResultPage from './components/ResultPage';
import ImageManagementPage from './components/ImageManagementPage';
import SavedContentPage from './components/SavedContentPage';
import SavedContentDetailPage from './components/SavedContentDetailPage';
import { Box, CssBaseline, Typography, Alert, CircularProgress, LinearProgress, AppBar, Toolbar, Button } from '@mui/material';

function App() {
  const [markdownContent, setMarkdownContent] = useState('');
  const [easyReadContent, setEasyReadContent] = useState([]);
  const [contentTitle, setContentTitle] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isProcessingPages, setIsProcessingPages] = useState(false);
  const [totalPages, setTotalPages] = useState(0);
  const [pagesProcessed, setPagesProcessed] = useState(0);
  const [error, setError] = useState(null);

  const navigate = useNavigate();

  const AppHeader = () => (
    <AppBar position="static" sx={{ mb: 3 }}>
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          EasyRead Generator
        </Typography>
        <Button color="inherit" component={Link} to="/">
          Home
        </Button>
        <Button color="inherit" component={Link} to="/saved">
          Saved Content
        </Button>
        <Button color="inherit" component={Link} to="/images">
          Image Management
        </Button>
      </Toolbar>
    </AppBar>
  );

  const progressPercent = totalPages > 0 ? (pagesProcessed / totalPages) * 100 : 0;

  const handleProcessingComplete = (finalMarkdown, finalEasyRead) => {
    console.log("App: Processing complete");
    let newTitle = 'Untitled';
    let newContent = [];
    let errorOccurred = false;
    let errorMsg = null;

    // Determine final state values based on the result
    if (finalEasyRead && typeof finalEasyRead === 'object' && finalEasyRead.easy_read_sentences) {
      newTitle = finalEasyRead.title || 'Untitled';
      newContent = finalEasyRead.easy_read_sentences; // Get the final array reference
    } else {
      newTitle = 'Processing Error'; 
      newContent = []; 
      errorOccurred = true; // Mark that an error occurred
      errorMsg = 'Received invalid format from easy read generation.';
      console.error('Invalid easy read content format:', finalEasyRead);
    }
    
    // Update all state at once before navigating
    setMarkdownContent(finalMarkdown);
    setContentTitle(newTitle);
    setEasyReadContent(newContent); // Use the reference stored above
    setIsLoading(false);
    setIsProcessingPages(false);
    setTotalPages(0);
    setPagesProcessed(0);
    setError(errorMsg); // Set error state (null if no error)
    
    // Navigate *after* the single state update batch is processed
    navigate('/results', { state: { fromProcessing: true } });
  };

  console.log('Render App:', { isLoading, isProcessingPages, totalPages, pagesProcessed, progressPercent });

  return (
    <Box>
      <CssBaseline />
      <AppHeader />
      
      {isLoading && !isProcessingPages && (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
             <CircularProgress />
          </Box>
      )}
      {isProcessingPages && (
          <Box sx={{ width: '80%', mx: 'auto', my: 3, maxWidth: 'md', p: 2, bgcolor: '#f5f5f5', borderRadius: 1 }}>
            <Typography variant="body1" sx={{ mb: 1, textAlign: 'center', fontWeight: 'bold' }}>
              Processing page {pagesProcessed} of {totalPages}...
            </Typography>
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
          element={
            <HomePage 
              setMarkdownContent={setMarkdownContent}
              setIsLoading={setIsLoading}
              setIsProcessingPages={setIsProcessingPages}
              setTotalPages={setTotalPages}
              setPagesProcessed={setPagesProcessed}
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
             />
            }
        />
        <Route
          path="/images"
          element={<ImageManagementPage />}
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

export default App;
