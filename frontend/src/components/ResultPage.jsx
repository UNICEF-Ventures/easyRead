import React, { useState, useEffect, useMemo } from 'react';
import PropTypes from 'prop-types';
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
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import { saveContent, exportCurrentContentDocx } from '../apiClient'; // Removed unused findSimilarImages, generateNewImage
import EasyReadContentList from './EasyReadContentList';
import useEasyReadImageManager from '../hooks/useEasyReadImageManager'; // Import the custom hook
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

// Wrap the component function directly
const ResultPageComponent = ({ title, markdownContent, easyReadContent, selectedSets = [], preventDuplicateImages = true }) => {
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
    userKeywords,
    imageSearchSource,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleSearchWithCustomKeywords,
    handleCloseNotification,
    getCurrentImageSelections,
    handleReorderContent
  } = useEasyReadImageManager(memoizedEasyReadContent, null, selectedSets, preventDuplicateImages); // Pass memoized content, selected sets, and duplicate prevention setting

  // State for saving feedback (remains specific to this page)
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);
  
  // State for export functionality
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

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
    
    
    // Get the most current image selections (handles async state updates)
    const currentSelections = getCurrentImageSelections();
    
    
    // Construct the JSON to save, including the selected image path from the current selections
    const dataToSave = easyReadContent.map((item, index) => {
      const finalSelectedPath = currentSelections[index] || imageState[index]?.selectedPath || null;
      
      
      return {
        ...item,
        selected_image_path: finalSelectedPath,
        alternative_images: imageState[index]?.images?.map(img => img.url) || [],
        user_keywords: userKeywords[index] || null // Include user keywords if available
      };
    });


    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const response = await saveContent(title, markdownContent, dataToSave);
      console.log('Save response:', response.data);

      // Store token in LocalStorage
      const token = response.data?.public_id;
      if (token) {
        try {
          const key = 'easyread_saved_tokens';
          const raw = localStorage.getItem(key);
          const arr = raw ? JSON.parse(raw) : [];
          if (!arr.includes(token)) {
            arr.push(token);
            localStorage.setItem(key, JSON.stringify(arr));
          }
        } catch (e) {
          console.warn('Failed to persist token to LocalStorage:', e);
        }
      }

      setSaveSuccess(true);
      // Redirect to the saved content page after successful save
      navigate(`/saved/${token}`);
    } catch (err) {
      console.error("Error saving content:", err);
      setSaveError(err.response?.data?.error || 'Failed to save content.');
    } finally {
      setIsSaving(false);
    }
  };

  // Handle sentence changes from inline editing
  const handleSentenceChange = (index, newSentence) => {
    // Update the easyReadContent directly since it's passed as props
    // The parent component would need to handle this state update
    console.log(`Sentence at index ${index} changed to: "${newSentence}"`);
    
    // For now, we'll just log it. In a complete implementation,
    // this would need to bubble up to the parent component that owns easyReadContent
    // or we'd need to manage a local copy of the content with useState
  };

  // Handle sentence reordering from drag and drop
  const handleReorderSentences = (newOrder) => {
    console.log('Sentences reordered:', newOrder);
    
    // Find which item was moved by comparing with current content
    let oldIndex = -1;
    let newIndex = -1;
    
    // Find the item that changed position
    for (let i = 0; i < newOrder.length; i++) {
      if (i < easyReadContent.length && newOrder[i] !== easyReadContent[i]) {
        // Found a difference, now find where this item came from
        const movedItem = newOrder[i];
        oldIndex = easyReadContent.findIndex(item => item === movedItem);
        newIndex = i;
        break;
      }
    }
    
    // If we found valid indices, reorder both keywords and image state
    if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
      handleReorderContent(oldIndex, newIndex, newOrder.length);
    }
    
    // For now, just log it. In a complete implementation,
    // this would update the parent's easyReadContent state
  };

  // Handle highlight changes for sentences
  const handleHighlightChange = (index, highlighted) => {
    console.log(`Sentence at index ${index} highlight changed to: ${highlighted}`);
    // For now, just log it. In a complete implementation,
    // this would update the parent's easyReadContent state
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

  // Export function
  const handleExport = async () => {
    if (!markdownContent || easyReadContent.length === 0) {
      setExportError("Content missing, cannot export.");
      return;
    }

    setIsExporting(true);
    setExportError(null);

    try {
      // Get current image selections
      const currentSelections = getCurrentImageSelections();
      
      // Prepare content with selected images
      const contentToExport = easyReadContent.map((item, index) => {
        const finalSelectedPath = currentSelections[index] || imageState[index]?.selectedPath || null;
        return {
          ...item,
          selected_image_path: finalSelectedPath
        };
      });

      const response = await exportCurrentContentDocx(title, contentToExport, markdownContent);
      
      // Create download link
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Generate filename
      const safeTitle = (title || 'easyread_document').replace(/[^a-zA-Z0-9\-_]/g, '_').toLowerCase();
      link.download = `${safeTitle}.docx`;
      
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);
      
    } catch (err) {
      console.error("Error exporting content:", err);
      setExportError(err.response?.data?.error || 'Failed to export content.');
    } finally {
      setIsExporting(false);
    }
  };

  // Generate function is now provided by the hook (handleGenerateImage)
  // Image selection change is now provided by the hook (handleImageSelectionChange)

  
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
              
              <Box sx={{ display: 'flex', gap: 2 }}>
                <Button
                  startIcon={isExporting ? <CircularProgress size={20}/> : <DownloadIcon />}
                  variant="outlined"
                  onClick={handleExport}
                  disabled={isExporting || isSaving}
                  sx={{
                    borderColor: 'var(--color-primary)',
                    color: 'var(--color-primary)',
                    borderRadius: 'var(--border-radius-md)',
                    '&:hover': {
                      borderColor: '#357ae8',
                      backgroundColor: 'rgba(74, 144, 226, 0.04)',
                    }
                  }}
                >
                  {isExporting ? 'Exporting...' : 'Export DOCX'}
                </Button>
                
                <Button
                  startIcon={isSaving ? <CircularProgress size={20}/> : <SaveIcon />}
                  variant="contained"
                  onClick={handleSave} // Page-specific save
                  disabled={isSaving || isExporting}
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
          </Box>
          

            <EasyReadContentList 
              easyReadContent={easyReadContent}
              imageState={imageState} // From hook
              userKeywords={userKeywords} // From hook
              imageSearchSource={imageSearchSource} // From hook
              onImageSelectionChange={handleImageSelectionChange} // From hook
              onGenerateImage={handleGenerateImage} // From hook
              onSearchWithCustomKeywords={handleSearchWithCustomKeywords} // From hook
              onSentenceChange={handleSentenceChange} // For inline editing
              onHighlightChange={handleHighlightChange} // For highlight toggle
              onReorderSentences={handleReorderSentences} // For drag and drop reordering
            />

            {/* Disclaimer and Acknowledgements */}
            <Box sx={{ 
              mt: 4, 
              pt: 3, 
              borderTop: '1px solid var(--lighter-gray)',
              textAlign: 'center'
            }}>
              {/* UNICEF Disclaimer */}
              <Typography variant="body2" sx={{ 
                color: 'var(--medium-gray)', 
                fontSize: '0.8rem',
                fontStyle: 'italic',
                mb: 2,
                maxWidth: '600px',
                mx: 'auto'
              }}>
                This content was generated by a prototype created at the Office of Innovation at UNICEF for evaluation purposes only. The content was generated using Artificial Intelligence and may contain errors, inaccuracies or biases. It is not intended for use in UNICEF programs or by program partners.
              </Typography>
              
              {/* GlobalSymbols Acknowledgement */}
              <Typography variant="body2" sx={{ 
                color: 'var(--medium-gray)', 
                fontSize: '0.875rem',
                fontStyle: 'italic'
              }}>
                🌍 <strong>Symbols kindly provided by <a 
                  href="https://www.globalsymbols.com" 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  style={{ 
                    color: 'var(--color-primary)', 
                    textDecoration: 'none' 
                  }}
                >
                  GlobalSymbols
                </a></strong> - making communication accessible worldwide
              </Typography>
            </Box>
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
      <Snackbar open={exportError !== null} autoHideDuration={6000} onClose={() => setExportError(null)}>
        <Alert onClose={() => setExportError(null)} severity="error" sx={{ width: '100%' }}>
          {exportError}
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

// PropTypes for type safety
ResultPage.propTypes = {
  // No props as this component gets data from location.state
};

export default ResultPage; 