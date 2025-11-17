import React, { useState, useEffect, useMemo } from 'react';
import { DISCLAIMER_TEXT, GLOBALSYMBOLS_ACKNOWLEDGEMENT_TEXT, GLOBALSYMBOLS_URL } from '../constants';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Backdrop,
  LinearProgress,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import { saveContent, exportCurrentContentDocx } from '../apiClient'; // Removed unused findSimilarImages, generateNewImage, reviseSentencesWithFeedback
import EasyReadContentList from './EasyReadContentList';
import useContentManager from '../hooks/useContentManager'; // Import the unified content management hook
import RevisionModal from './RevisionModal'; // Import the reusable revision modal
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

// Wrap the component function directly
const ResultPageComponent = ({ title, markdownContent, easyReadContent, selectedSets = [], preventDuplicateImages = true }) => {
  const location = useLocation();
  const navigate = useNavigate();

  // Initial content structure
  const initialContent = useMemo(() => ({
    title: title,
    original_markdown: markdownContent,
    easy_read_content: easyReadContent
  }), [title, markdownContent, easyReadContent]);

  // Use the unified content management hook
  const {
    content,
    isEmpty,
    easyReadContent: currentEasyReadContent,
    updateEasyReadContent,
    handleSentenceChange,
    handleHighlightChange,
    handleReorderSentences,
    handleSentenceDelete,
    handleSentenceAdd,
    // Image management from the hook
    imageState,
    userKeywords,
    imageSearchSource,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleSearchWithCustomKeywords,
    handleCloseNotification,
    getCurrentImageSelections
  } = useContentManager(initialContent, null, selectedSets, preventDuplicateImages);

  // Debug output for easyReadContent structure
  useEffect(() => {
    if (currentEasyReadContent && currentEasyReadContent.length > 0) {
      console.log("ResultPage: currentEasyReadContent structure", {
        firstItem: currentEasyReadContent[0],
        totalItems: currentEasyReadContent.length,
        hasImageRetrieval: currentEasyReadContent.some(item => item.image_retrieval),
        itemsWithImageRetrieval: currentEasyReadContent.filter(item => item.image_retrieval).length,
        imageRetrievalValues: currentEasyReadContent.slice(0, 5).map(item => item.image_retrieval)
      });
    }
  }, [currentEasyReadContent]);

  // State for saving feedback (remains specific to this page)
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);
  
  // State for export functionality
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  // State for revision modal
  const [isRevisionModalOpen, setIsRevisionModalOpen] = useState(false);

  // Redirect if no content (remains specific)
  useEffect(() => {
    if (!location.state?.fromProcessing && isEmpty) {
      console.log('Redirecting from ResultPage: No content found.');
      navigate('/');
    }
  }, [location.state, isEmpty, navigate]);
  
  // Save function remains specific to this page
  const handleSave = async () => {
    if (!content?.original_markdown || isEmpty) {
      setSaveError("Content missing, cannot save.");
      return;
    }
    
    
    // Get the most current image selections (handles async state updates)
    const currentSelections = getCurrentImageSelections();
    
    
    // Construct the JSON to save, including the selected image path from the current selections
    const dataToSave = currentEasyReadContent.map((item, index) => {
      let finalSelectedPath = currentSelections[index] || imageState[index]?.selectedPath || null;
      
      // Ensure finalSelectedPath is a string, not an object
      if (finalSelectedPath && typeof finalSelectedPath === 'object') {
        finalSelectedPath = finalSelectedPath.url || finalSelectedPath.path || null;
      }
      
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
      const response = await saveContent(content.title, content.original_markdown, dataToSave);
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
      navigate(`/easyread/saved/${token}`);
    } catch (err) {
      console.error("Error saving content:", err);
      setSaveError(err.response?.data?.error || 'Failed to save content.');
    } finally {
      setIsSaving(false);
    }
  };

  // Editing handlers are now provided by useContentManager hook
  
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
    if (!content?.original_markdown || isEmpty) {
      setExportError("Content missing, cannot export.");
      return;
    }

    setIsExporting(true);
    setExportError(null);

    try {
      // Get current image selections
      const currentSelections = getCurrentImageSelections();
      
      // Prepare content with selected images
      const contentToExport = currentEasyReadContent.map((item, index) => {
        let finalSelectedPath = currentSelections[index] || imageState[index]?.selectedPath || null;
        
        // Ensure finalSelectedPath is a string, not an object
        if (finalSelectedPath && typeof finalSelectedPath === 'object') {
          finalSelectedPath = finalSelectedPath.url || finalSelectedPath.path || null;
        }
        
        return {
          ...item,
          selected_image_path: finalSelectedPath
        };
      });

      const response = await exportCurrentContentDocx(content.title, contentToExport, content.original_markdown);
      
      // Create download link
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Generate filename
      const safeTitle = (content.title || 'easyread_document').replace(/[^a-zA-Z0-9\-_]/g, '_').toLowerCase();
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

  // Revision handlers - now using shared component
  const handleOpenRevisionModal = () => {
    setIsRevisionModalOpen(true);
  };

  const handleCloseRevisionModal = () => {
    setIsRevisionModalOpen(false);
  };

  const handleRevisionComplete = (revisedSentences) => {
    // Update the content using the unified content manager
    updateEasyReadContent(revisedSentences);
  };

  
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
                {content?.title || 'Untitled Content'}
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
              easyReadContent={currentEasyReadContent}
              imageState={imageState} // From hook
              userKeywords={userKeywords} // From hook
              imageSearchSource={imageSearchSource} // From hook
              onImageSelectionChange={handleImageSelectionChange} // From hook
              onGenerateImage={handleGenerateImage} // From hook
              onSearchWithCustomKeywords={handleSearchWithCustomKeywords} // From hook
              onSentenceChange={handleSentenceChange} // From unified content manager
              onHighlightChange={handleHighlightChange} // From unified content manager
              onReorderSentences={handleReorderSentences} // From unified content manager
              onSentenceDelete={handleSentenceDelete} // From unified content manager
              onSentenceAdd={handleSentenceAdd} // From unified content manager
            />

            {/* Try Again Button */}
            <Box sx={{ 
              mt: 4, 
              pt: 3, 
              borderTop: '1px solid var(--lighter-gray)',
              textAlign: 'center',
              mb: 3
            }}>
              <Button
                variant="outlined"
                onClick={handleOpenRevisionModal}
                disabled={isSaving || isExporting}
                sx={{
                  borderColor: 'var(--color-primary)',
                  color: 'var(--color-primary)',
                  borderRadius: 'var(--border-radius-md)',
                  px: 3,
                  py: 1,
                  '&:hover': {
                    borderColor: '#357ae8',
                    backgroundColor: 'rgba(74, 144, 226, 0.04)',
                  }
                }}
              >
                Try again with custom feedback
              </Button>
            </Box>

            {/* Disclaimer and Acknowledgements */}
            <Box sx={{ 
              mt: 2, 
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
                {DISCLAIMER_TEXT}
              </Typography>
              
              {/* GlobalSymbols Acknowledgement */}
              <Typography variant="body2" sx={{ 
                color: 'var(--medium-gray)', 
                fontSize: '0.875rem',
                fontStyle: 'italic'
              }}>
                🌍 <strong>Symbols kindly provided by <a 
                  href={GLOBALSYMBOLS_URL} 
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

      {/* Shared revision modal */}
      <RevisionModal
        open={isRevisionModalOpen}
        onClose={handleCloseRevisionModal}
        content={content}
        onRevisionComplete={handleRevisionComplete}
      />
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