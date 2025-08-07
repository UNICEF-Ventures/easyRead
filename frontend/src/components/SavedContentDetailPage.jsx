import React, { useState, useEffect, useCallback } from 'react';
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
// Removed unused import: format from 'date-fns'
import apiClient, { bulkUpdateSavedContentImages, exportSavedContentDocx } from '../apiClient';
import EasyReadContentList from './EasyReadContentList';
import useEasyReadImageManager from '../hooks/useEasyReadImageManager';
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
  }, [id, checkEditAccess]);

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
      
      // Convert to the format expected by the API (string keys)
      const imageSelections = {};
      Object.keys(currentSelections).forEach(index => {
        if (currentSelections[index] !== null && currentSelections[index] !== undefined) {
          imageSelections[index.toString()] = currentSelections[index];
        }
      });

      // Call the bulk update API using numeric ID
      await bulkUpdateSavedContentImages(numericId, imageSelections);
      
      setSaveSuccess(true);
      
      // Optionally refresh the content to ensure consistency
      // await fetchSavedContentDetail();
      
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
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleCloseNotification,
    getCurrentImageSelections
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
              onImageSelectionChange={handleImageSelectionChange} // From hook
              onGenerateImage={handleGenerateImage} // From hook
              readOnly={!canEdit} // Disable editing if user doesn't have access
              // isLoading prop might not be needed if hook handles initial loading state internally
            />
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
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
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
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={() => setSaveSuccess(false)} severity="success" sx={{ width: '100%' }}>
            Content saved successfully!
          </Alert>
        </Snackbar>
        
        <Snackbar 
          open={saveError !== null} 
          autoHideDuration={6000} 
          onClose={() => setSaveError(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={() => setSaveError(null)} severity="error" sx={{ width: '100%' }}>
            {saveError}
          </Alert>
        </Snackbar>
        
        <Snackbar 
          open={exportError !== null} 
          autoHideDuration={6000} 
          onClose={() => setExportError(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert onClose={() => setExportError(null)} severity="error" sx={{ width: '100%' }}>
            {exportError}
          </Alert>
        </Snackbar>
      </Paper>
    </Container>
  );
};

export default SavedContentDetailPage; 