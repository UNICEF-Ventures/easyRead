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
  Collapse
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
// Removed unused import: format from 'date-fns'
import apiClient from '../apiClient';
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

  // Fetch the saved content details (remains specific to this page)
  const fetchSavedContentDetail = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/saved-content/${id}/`);
      setContent(response.data);
      // The hook's useEffect will handle initializing imageState when content updates
    } catch (err) {
      console.error('Error fetching saved content details:', err);
      setError('Failed to load content details. Please try again later.');
      setContent(null); // Clear content on error
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Use the custom hook for image management
  const {
    imageState,
    notification,
    handleImageSelectionChange,
    handleGenerateImage,
    handleCloseNotification
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

  console.log('SavedContentDetailPage render:', { loading, contentId: id, imageState });

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
        </Box>


        {error ? (
          <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>
        ) : (
          <EasyReadContentList 
            easyReadContent={content?.easy_read_content || []} 
            imageState={imageState} // From hook
            onImageSelectionChange={handleImageSelectionChange} // From hook
            onGenerateImage={handleGenerateImage} // From hook
            // isLoading prop might not be needed if hook handles initial loading state internally
          />
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
      </Paper>
    </Container>
  );
};

export default SavedContentDetailPage; 