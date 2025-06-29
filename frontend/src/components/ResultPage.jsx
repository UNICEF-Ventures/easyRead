import React, { useState, useEffect, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Container,
  Paper,
  Button,
  Snackbar,
  Alert,
  CircularProgress,
  FormControlLabel,
  Checkbox,
  LinearProgress
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import SaveIcon from '@mui/icons-material/Save';
import { saveContent } from '../apiClient'; // Removed unused findSimilarImages, generateNewImage
import EasyReadContentList from './EasyReadContentList';
import useEasyReadImageManager from '../hooks/useEasyReadImageManager'; // Import the custom hook

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = 'http://localhost:8000';

// Wrap the component function directly
const ResultPageComponent = ({ title, markdownContent, easyReadContent }) => {
  const location = useLocation();
  const navigate = useNavigate();

  // Debug output for easyReadContent structure
  useEffect(() => {
    if (easyReadContent && easyReadContent.length > 0) {
      console.log("ResultPage: easyReadContent structure", {
        firstItem: easyReadContent[0],
        totalItems: easyReadContent.length,
        hasImageRetrieval: easyReadContent.some(item => item.image_retrieval),
        itemsWithImageRetrieval: easyReadContent.filter(item => item.image_retrieval).length,
        imageRetrievalValues: easyReadContent.slice(0, 5).map(item => item.image_retrieval)
      });
    }
  }, [easyReadContent]);

  // Memoize the easyReadContent to prevent unnecessary reinitializations
  const memoizedEasyReadContent = useMemo(() => easyReadContent, [easyReadContent]);

  // Use the custom hook for image management
  const {
    imageState,
    preventDuplicateImages,
    setPreventDuplicateImages,
    refreshingAll,
    refreshProgress,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleRefreshAllImages,
    handleCloseNotification
  } = useEasyReadImageManager(memoizedEasyReadContent, null); // Pass memoized content

  // State for saving feedback (remains specific to this page)
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Redirect if no content (remains specific)
  useEffect(() => {
    if (!location.state?.fromProcessing && (!easyReadContent || easyReadContent.length === 0)) {
      console.log('Redirecting from ResultPage: No content found.');
      navigate('/');
    }
  }, [location.state, easyReadContent, navigate]);

  // Initial image fetching is handled by the hook

  const isEmpty = !easyReadContent || easyReadContent.length === 0;
  
  // Save function remains specific to this page
  const handleSave = async () => {
    if (!markdownContent || easyReadContent.length === 0) {
      setSaveError("Content missing, cannot save.");
      return;
    }
    
    // Construct the JSON to save, including the selected image path from the hook's state
    const dataToSave = easyReadContent.map((item, index) => ({
      ...item,
      selected_image_path: imageState[index]?.selectedPath || null,
      alternative_images: imageState[index]?.images?.map(img => img.url) || []
    }));

    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const response = await saveContent(title, markdownContent, dataToSave);
      console.log('Save response:', response.data);
      setSaveSuccess(true);
      // Optional: Redirect to the saved content page after successful save
      // navigate(`/saved/${response.data.id}`);
    } catch (err) {
      console.error("Error saving content:", err);
      setSaveError(err.response?.data?.error || 'Failed to save content.');
    } finally {
      setIsSaving(false);
    }
  };
  
  // Snackbar handlers remain specific or could be part of the hook if generalized
  const handleCloseSuccessSnackbar = (event, reason) => {
     if (reason === 'clickaway') return;
    setSaveSuccess(false);
  };

  const handleCloseErrorSnackbar = (event, reason) => {
     if (reason === 'clickaway') return;
    setSaveError(null);
  };

  // Refresh function is now provided by the hook (handleRefreshAllImages)
  // Generate function is now provided by the hook (handleGenerateImage)
  // Image selection change is now provided by the hook (handleImageSelectionChange)

  console.log('ResultPage render:', { isEmpty, imageState });
  
  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 6 }}>
      {isEmpty ? (
        <Paper 
          elevation={3} 
          sx={{ 
            p: 4, 
            mt: 4, 
            textAlign: 'center',
            borderRadius: 'var(--border-radius-md)',
            backgroundColor: 'white',
          }}
        >
          <Typography variant="h5" sx={{ mb: 3, color: 'var(--medium-gray)' }}>
            No content to display
          </Typography>
          <Button 
            variant="contained" 
            onClick={() => navigate('/')}
            sx={{
              backgroundColor: 'var(--color-primary)',
              px: 3,
              py: 1,
              borderRadius: 'var(--border-radius-md)',
              '&:hover': {
                backgroundColor: '#357ae8',
              }
            }}
          >
            Go Home
          </Button>
        </Paper>
      ) : (
        <>
          <Paper 
            elevation={3} 
            sx={{ 
              p: 4, 
              mb: 4,
              borderRadius: 'var(--border-radius-md)',
              backgroundColor: 'white',
            }}
          >
            <Box sx={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center', 
              mb: 4,
              borderBottom: '1px solid var(--lighter-gray)',
              pb: 2
            }}>
              <Typography variant="h4" sx={{ 
                color: 'var(--dark-gray)', 
                fontWeight: 600,
              }}>
                {title || 'Untitled Content'}
              </Typography>
              
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
                  <Button
                    startIcon={<RefreshIcon />}
                    variant="outlined"
                    onClick={handleRefreshAllImages} // From hook
                    disabled={refreshingAll} // From hook
                    sx={{
                      borderColor: 'var(--color-primary)',
                      color: 'var(--color-primary)',
                      borderRadius: 'var(--border-radius-md)',
                      '&:hover': {
                        borderColor: '#357ae8',
                        backgroundColor: 'rgba(66, 133, 244, 0.04)',
                      }
                    }}
                  >
                    Refresh Images
                  </Button>
                  <Button
                    startIcon={isSaving ? <CircularProgress size={20}/> : <SaveIcon />}
                    variant="contained"
                    onClick={handleSave} // Page-specific save
                    disabled={isSaving || refreshingAll} // Use hook's refreshingAll
                    sx={{
                      backgroundColor: 'var(--color-accent)',
                      borderRadius: 'var(--border-radius-md)',
                      '&:hover': {
                        backgroundColor: '#0b8043',
                      }
                    }}
                  >
                    {isSaving ? 'Saving...' : 'Save Content'}
                  </Button>
                </Box>
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={preventDuplicateImages} // From hook
                      onChange={(e) => setPreventDuplicateImages(e.target.checked)} // From hook
                      color="primary"
                      size="small"
                      disabled={refreshingAll} // From hook
                    />
                  }
                  label="Avoid duplicate images when refreshing"
                  sx={{ mb: 0 }}
                />
              </Box>
          </Box>
          
          {refreshingAll && (
              <Box sx={{ width: '100%', mb: 4 }}>
                <Typography sx={{ mb: 1, color: 'var(--medium-gray)' }}>
                  Refreshing images... {Math.round(refreshProgress)}% 
                </Typography>
              <LinearProgress 
                variant="determinate" 
                  value={refreshProgress} // From hook
                  sx={{ 
                    height: 8, 
                    borderRadius: 4,
                    backgroundColor: 'var(--lighter-gray)',
                    '& .MuiLinearProgress-bar': {
                      backgroundColor: 'var(--color-primary)',
                      borderRadius: 4
                    }
                  }}
              />
            </Box>
          )}

            <EasyReadContentList 
              easyReadContent={easyReadContent}
              imageState={imageState} // From hook
              onImageSelectionChange={handleImageSelectionChange} // From hook
              onGenerateImage={handleGenerateImage} // From hook
            />
          </Paper>
        </>
      )}

      {/* Save success/error snackbars */}
      <Snackbar open={saveSuccess} autoHideDuration={6000} onClose={handleCloseSuccessSnackbar}>
        <Alert onClose={handleCloseSuccessSnackbar} severity="success" sx={{ width: '100%' }}>
          Content saved successfully!
        </Alert>
      </Snackbar>
      <Snackbar open={saveError !== null} autoHideDuration={6000} onClose={handleCloseErrorSnackbar}>
        <Alert onClose={handleCloseErrorSnackbar} severity="error" sx={{ width: '100%' }}>
          {saveError}
        </Alert>
      </Snackbar>

      {/* Notification snackbar from hook */}
      <Snackbar open={notification.open} autoHideDuration={6000} onClose={handleCloseNotification}>
        <Alert onClose={handleCloseNotification} severity={notification.severity} sx={{ width: '100%' }}>
          {notification.message}
        </Alert>
      </Snackbar>
    </Container>
  );
}

// Export the memoized component
const ResultPage = React.memo(ResultPageComponent);

export default ResultPage; 