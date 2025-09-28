import React, { useState, useEffect, useCallback } from 'react';
import { DISCLAIMER_TEXT, GLOBALSYMBOLS_ACKNOWLEDGEMENT_TEXT, GLOBALSYMBOLS_URL } from '../constants';
import PropTypes from 'prop-types';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Container,
  Paper,
  CircularProgress,
  Alert,
  IconButton,
  Snackbar,
  Collapse,
  Button
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import SaveIcon from '@mui/icons-material/Save';
import DownloadIcon from '@mui/icons-material/Download';
import ShareIcon from '@mui/icons-material/Share';
// Removed unused import: format from 'date-fns'
import apiClient, { exportSavedContentDocx, updateSavedContentFull } from '../apiClient';
import EasyReadContentList from './EasyReadContentList';
import useEasyReadImageManager from '../hooks/useEasyReadImageManager';
import RevisionModal from './RevisionModal'; // Import the shared revision modal
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

const SavedContentDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  
  // State specific to this page
  const [content, setContent] = useState(null); // Holds the full fetched content object
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [originalContentExpanded, setOriginalContentExpanded] = useState(false);
  
  // Save functionality state
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState(null);
  
  // Export functionality state
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState(null);
  
  // Share functionality state
  const [shareSuccess, setShareSuccess] = useState(false);
  
  // Revision modal state
  const [isRevisionModalOpen, setIsRevisionModalOpen] = useState(false);

  // Numeric ID for API calls
  const [numericId, setNumericId] = useState(null);

  // Access control state - check if user owns this content
  const [canEdit, setCanEdit] = useState(false);

  // Check if user has access to edit this content (has the token in LocalStorage)
  const checkEditAccess = useCallback((contentId) => {
    try {
      const raw = localStorage.getItem('easyread_saved_tokens');
      const tokens = raw ? JSON.parse(raw) : [];
      return Array.isArray(tokens) && tokens.includes(contentId);
    } catch (e) {
      console.warn('Failed to read tokens from LocalStorage:', e);
      return false;
    }
  }, []);

  // Fetch the saved content details (remains specific to this page)
  const fetchSavedContentDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/saved-content/by-token/${id}/`);
      setContent(response.data);
      // Store numeric ID for subsequent operations
      setNumericId(response.data?.id);
      // Check if user has edit access
      setCanEdit(checkEditAccess(id));
      // The hook's useEffect will handle initializing imageState when content updates
    } catch (err) {
      console.error('Error fetching saved content details:', err);
      setError('Failed to load content details. Please try again later.');
      setContent(null); // Clear content on error
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Export function
  const handleExport = async () => {
    if (!content || !numericId) {
      setExportError('Unable to export: content not loaded');
      return;
    }

    setIsExporting(true);
    setExportError(null);

    try {
      const response = await exportSavedContentDocx(numericId);
      
      // Create download link
      const blob = new Blob([response.data], { 
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      // Generate filename
      const safeTitle = (content.title || `saved_content_${id}`).replace(/[^a-zA-Z0-9\-_]/g, '_').toLowerCase();
      link.download = `${safeTitle}.docx`;
      
      document.body.appendChild(link);
      link.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(link);
      
    } catch (err) {
      console.error('Error exporting saved content:', err);
      setExportError(err.response?.data?.error || 'Failed to export content');
    } finally {
      setIsExporting(false);
    }
  };

  // Share function to copy URL to clipboard
  const handleShare = async () => {
    try {
      const currentUrl = window.location.href;
      await navigator.clipboard.writeText(currentUrl);
      setShareSuccess(true);
    } catch (err) {
      console.error('Failed to copy URL to clipboard:', err);
      // Fallback for browsers that don't support clipboard API
      try {
        const textArea = document.createElement('textarea');
        textArea.value = window.location.href;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        setShareSuccess(true);
      } catch (fallbackErr) {
        console.error('Fallback copy also failed:', fallbackErr);
      }
    }
  };

  // Handle sentence changes from inline editing
  const handleSentenceChange = (index, newSentence) => {
    if (!canEdit) return; // Prevent editing if user doesn't have permission
    
    // Update the content state directly
    setContent(prevContent => {
      if (!prevContent?.easy_read_content) return prevContent;
      
      const updatedEasyReadContent = [...prevContent.easy_read_content];
      updatedEasyReadContent[index] = {
        ...updatedEasyReadContent[index],
        sentence: newSentence
      };
      
      return {
        ...prevContent,
        easy_read_content: updatedEasyReadContent
      };
    });
    
    console.log(`Sentence at index ${index} changed to: "${newSentence}"`);
  };

  // Handle sentence reordering from drag and drop
  const handleReorderSentences = (newOrder) => {
    if (!canEdit) return; // Prevent reordering if user doesn't have permission
    
    // Find which item was moved by comparing with current content
    const currentContent = content?.easy_read_content || [];
    let oldIndex = -1;
    let newIndex = -1;
    
    // Find the item that changed position
    for (let i = 0; i < newOrder.length; i++) {
      if (i < currentContent.length && newOrder[i] !== currentContent[i]) {
        // Found a difference, now find where this item came from
        const movedItem = newOrder[i];
        oldIndex = currentContent.findIndex(item => item === movedItem);
        newIndex = i;
        break;
      }
    }
    
    // Reorder keywords and image state BEFORE updating content to avoid race conditions
    if (oldIndex !== -1 && newIndex !== -1 && oldIndex !== newIndex) {
      handleReorderContent(oldIndex, newIndex, newOrder.length);
    }
    
    // Update the content state with the new order
    setContent(prevContent => {
      if (!prevContent?.easy_read_content) return prevContent;
      
      return {
        ...prevContent,
        easy_read_content: newOrder
      };
    });
    
    console.log('Sentences reordered in saved content');
  };

  // Handle highlight changes for sentences
  const handleHighlightChange = (index, highlighted) => {
    if (!canEdit) return; // Prevent highlighting if user doesn't have permission
    
    // Update the content state with the highlight change
    setContent(prevContent => {
      if (!prevContent?.easy_read_content) return prevContent;
      
      const updatedEasyReadContent = [...prevContent.easy_read_content];
      updatedEasyReadContent[index] = {
        ...updatedEasyReadContent[index],
        highlighted: highlighted
      };
      
      return {
        ...prevContent,
        easy_read_content: updatedEasyReadContent
      };
    });
    
    console.log(`Sentence at index ${index} highlight changed to: ${highlighted}`);
  };

  // Revision handlers - using shared RevisionModal
  const handleOpenRevisionModal = () => {
    setIsRevisionModalOpen(true);
  };

  const handleCloseRevisionModal = () => {
    setIsRevisionModalOpen(false);
  };

  const handleRevisionComplete = (revisedSentences) => {
    // Update the content with revised sentences
    setContent(prevContent => ({
      ...prevContent,
      easy_read_content: revisedSentences
    }));
  };

  // Save function to update the saved content
  const handleSave = async () => {
    if (!content || !getCurrentImageSelections || !numericId) {
      setSaveError('Unable to save: content not loaded');
      return;
    }

    if (!canEdit) {
      setSaveError('You do not have permission to edit this content. Only the creator can save changes.');
      return;
    }

    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
      // Get current image selections
      const currentSelections = getCurrentImageSelections();
      
      // Prepare the full content update including both images and user keywords
      const updatedContent = (content?.easy_read_content || []).map((item, index) => {
        let finalSelectedPath = currentSelections[index] !== undefined 
          ? currentSelections[index] 
          : item.selected_image_path;
        
        // Ensure finalSelectedPath is a string, not an object
        if (finalSelectedPath && typeof finalSelectedPath === 'object') {
          finalSelectedPath = finalSelectedPath.url || finalSelectedPath.path || null;
        }
        
        // Ensure alternative_images are also strings, not objects
        let alternativeImages = item.alternative_images;
        if (alternativeImages && Array.isArray(alternativeImages)) {
          alternativeImages = alternativeImages.map(img => {
            if (img && typeof img === 'object') {
              return img.url || img.path || null;
            }
            return img;
          }).filter(Boolean); // Remove null/undefined values
        }

        return {
          ...item,
          selected_image_path: finalSelectedPath,
          alternative_images: alternativeImages,
          user_keywords: userKeywords[index] || item.user_keywords || null
        };
      });
      

      // Call the full update API with error handling
      const response = await updateSavedContentFull(numericId, updatedContent);
      
      // Log successful update for debugging
      if (import.meta.env.DEV) {
        console.log('Content updated successfully:', response.data);
      }
      
      setSaveSuccess(true);
      
      // Refresh content to ensure consistency with server
      setTimeout(() => {
        fetchSavedContentDetail();
      }, 1000); // Small delay to let the success message show
      
    } catch (err) {
      console.error('Error saving updated content:', err);
      setSaveError(err.response?.data?.error || 'Failed to save content updates');
    } finally {
      setIsSaving(false);
    }
  };

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
  } = useEasyReadImageManager(content?.easy_read_content || [], id); // Pass content and id to the hook

  // Call fetch function after hook is initialized
  useEffect(() => {
    fetchSavedContentDetail();
  }, [fetchSavedContentDetail]);

  // Handlers related to image state (selection, generation, refresh) are now provided by the hook.
  // handleImageSelectionChange - from hook
  // handleGenerateImage - from hook
  // handleRefreshAllImages - from hook
  // handleCloseNotification - from hook


  // Show loading spinner while content is being fetched
  if (loading) {
    return (
      <Container maxWidth="md" sx={{ mt: 4, mb: 4, textAlign: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={2} sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <IconButton
            onClick={() => navigate('/saved')}
            sx={{ mr: 2 }}
            aria-label="back"
          >
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h5" component="h1" sx={{ flexGrow: 1 }}>
            {content?.title || `Saved Conversion #${id}`}
          </Typography>
          
          <Box sx={{ display: 'flex', gap: 2 }}>
            <IconButton
              onClick={handleShare}
              disabled={loading}
              sx={{
                color: 'var(--color-primary)',
                '&:hover': {
                  backgroundColor: 'rgba(74, 144, 226, 0.04)',
                }
              }}
              title="Share - Copy URL to clipboard"
            >
              <ShareIcon />
            </IconButton>
            
            <Button
              startIcon={isExporting ? <CircularProgress size={20}/> : <DownloadIcon />}
              variant="outlined"
              onClick={handleExport}
              disabled={isExporting || isSaving || loading}
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
              onClick={handleSave}
              disabled={isSaving || isExporting || loading || !canEdit}
              title={!canEdit ? "You can only edit content that you created" : ""}
              sx={{
                backgroundColor: canEdit ? 'var(--color-accent)' : 'rgba(0, 0, 0, 0.12)',
                borderRadius: 'var(--border-radius-md)',
                '&:hover': {
                  backgroundColor: canEdit ? '#0b8043' : 'rgba(0, 0, 0, 0.12)',
                },
                '&.Mui-disabled': {
                  color: !canEdit ? 'rgba(0, 0, 0, 0.26)' : undefined,
                }
              }}
            >
              {isSaving ? 'Saving...' : (canEdit ? 'Save Changes' : 'View Only')}
            </Button>
          </Box>
        </Box>


        {error ? (
          <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>
        ) : (
          <>
            {!canEdit && (
              <Alert severity="info" sx={{ my: 2 }}>
                You are viewing shared content. Only the creator can make changes.
              </Alert>
            )}
            <EasyReadContentList 
              easyReadContent={content?.easy_read_content || []} 
              imageState={imageState} // From hook
              userKeywords={userKeywords} // From hook
              imageSearchSource={imageSearchSource} // From hook
              onImageSelectionChange={handleImageSelectionChange} // From hook
              onGenerateImage={handleGenerateImage} // From hook
              onSearchWithCustomKeywords={handleSearchWithCustomKeywords} // From hook
              onSentenceChange={handleSentenceChange} // For inline editing
              onHighlightChange={handleHighlightChange} // For highlight toggle
              onReorderSentences={handleReorderSentences} // For drag and drop reordering
              readOnly={!canEdit} // Disable editing if user doesn't have access
              // isLoading prop might not be needed if hook handles initial loading state internally
            />

            {/* Try Again Button */}
            {canEdit && (
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
                  disabled={!content}
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
            )}

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
          </>
        )}

        {/* Original content collapse remains page-specific */}
        {content?.original_markdown && (
          <Box sx={{ mt: 4, pt: 3, borderTop: '1px solid #e0e0e0' }}>
            <Box 
              sx={{ display: 'flex', alignItems: 'center', cursor: 'pointer', mb: 1 }}
              onClick={() => setOriginalContentExpanded(!originalContentExpanded)}
            >
              <Typography variant="h6" sx={{ flexGrow: 1 }}>
                Original Content
              </Typography>
              <IconButton size="small">
                <ExpandMoreIcon 
                  sx={{ 
                    transform: originalContentExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s'
                  }}
                />
              </IconButton>
            </Box>
            <Collapse in={originalContentExpanded} timeout="auto" unmountOnExit>
              <Paper variant="outlined" sx={{ p: 2, bgcolor: 'rgba(0, 0, 0, 0.02)' }}>
                <Typography 
                  variant="body2" 
                  component="pre" 
                  sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.875rem' }}
                >
                  {content.original_markdown}
                </Typography>
              </Paper>
            </Collapse>
          </Box>
        )}

        {/* Snackbar from hook */}
        <Snackbar
          open={notification.open}
          autoHideDuration={6000}
          onClose={handleCloseNotification}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={handleCloseNotification} severity={notification.severity} sx={{ width: '100%' }}>
            {notification.message}
          </Alert>
        </Snackbar>

        {/* Save success/error snackbars */}
        <Snackbar 
          open={saveSuccess} 
          autoHideDuration={6000} 
          onClose={() => setSaveSuccess(false)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setSaveSuccess(false)} severity="success" sx={{ width: '100%' }}>
            Content saved successfully!
          </Alert>
        </Snackbar>
        
        <Snackbar 
          open={saveError !== null} 
          autoHideDuration={6000} 
          onClose={() => setSaveError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setSaveError(null)} severity="error" sx={{ width: '100%' }}>
            {saveError}
          </Alert>
        </Snackbar>
        
        <Snackbar 
          open={exportError !== null} 
          autoHideDuration={6000} 
          onClose={() => setExportError(null)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setExportError(null)} severity="error" sx={{ width: '100%' }}>
            {exportError}
          </Alert>
        </Snackbar>
        
        <Snackbar 
          open={shareSuccess} 
          autoHideDuration={3000} 
          onClose={() => setShareSuccess(false)}
          anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        >
          <Alert onClose={() => setShareSuccess(false)} severity="success" sx={{ width: '100%' }}>
            URL copied to clipboard!
          </Alert>
        </Snackbar>

        {/* Shared revision modal */}
        <RevisionModal
          open={isRevisionModalOpen}
          onClose={handleCloseRevisionModal}
          content={content}
          onRevisionComplete={handleRevisionComplete}
          disabled={!canEdit}
        />
      </Paper>
    </Container>
  );
};

// PropTypes for type safety
SavedContentDetailPage.propTypes = {
  // No props as this component gets data from URL params
};

export default SavedContentDetailPage; 