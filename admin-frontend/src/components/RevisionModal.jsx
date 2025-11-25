import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  CircularProgress,
  Backdrop,
  LinearProgress,
} from '@mui/material';
import { reviseSentencesWithFeedback } from '../apiClient';

/**
 * Reusable revision modal component for both saved and new content
 */
const RevisionModal = ({ 
  open, 
  onClose, 
  content, 
  onRevisionComplete,
  disabled = false 
}) => {
  const [revisionFeedback, setRevisionFeedback] = useState('');
  const [previousFeedback, setPreviousFeedback] = useState('');
  const [isRevising, setIsRevising] = useState(false);
  const [revisionError, setRevisionError] = useState(null);
  const [revisionStep, setRevisionStep] = useState('');

  // Handle opening modal - pre-populate with previous feedback
  const handleOpen = () => {
    setRevisionFeedback(previousFeedback || '');
    setRevisionError(null);
  };

  // Handle closing modal
  const handleClose = () => {
    if (isRevising) return; // Prevent closing during revision
    onClose();
    setRevisionError(null);
  };

  // Handle feedback text change with character limit
  const handleFeedbackChange = (event) => {
    const value = event.target.value;
    if (value.length <= 800) {
      setRevisionFeedback(value);
    }
  };

  // Handle revision submission
  const handleSubmitRevision = async () => {
    if (!revisionFeedback.trim()) {
      setRevisionError('Please provide feedback for revision.');
      return;
    }

    if (!content?.original_markdown || !content?.easy_read_content) {
      setRevisionError('Missing content data for revision.');
      return;
    }

    setIsRevising(true);
    setRevisionError(null);
    setRevisionStep('Revising sentences based on your feedback...');

    try {
      console.log('Starting revision with feedback:', revisionFeedback.trim());
      console.log('Original content length:', content.easy_read_content.length);

      // Transform content to match API expectations (only sentence and image_retrieval fields)
      const currentSentences = content.easy_read_content.map(item => ({
        sentence: item.sentence,
        image_retrieval: item.image_retrieval
      }));

      // Call the revision API
      const response = await reviseSentencesWithFeedback(
        content.original_markdown,
        currentSentences,
        revisionFeedback.trim()
      );

      console.log('Revision API response:', response);

      // Validate response structure
      if (!response || !response.data || !response.data.easy_read_sentences) {
        throw new Error('Invalid response structure: missing easy_read_sentences');
      }

      const revisedSentences = response.data.easy_read_sentences;
      
      // Validate that we got sentences back
      if (!Array.isArray(revisedSentences) || revisedSentences.length === 0) {
        throw new Error('No revised sentences received from the server');
      }

      console.log('Revision successful:', {
        originalLength: content.easy_read_content.length,
        revisedLength: revisedSentences.length,
        firstRevisedSentence: revisedSentences[0]?.sentence || 'N/A'
      });

      // Store the feedback for next time
      setPreviousFeedback(revisionFeedback.trim());

      // Log feedback for future inspection
      console.log('User feedback for content revision:', {
        feedback: revisionFeedback.trim(),
        originalContentLength: content.easy_read_content.length,
        revisedContentLength: revisedSentences.length,
        timestamp: new Date().toISOString(),
        title: content.title || 'Untitled'
      });
      
      setRevisionStep('Updating content and refetching images...');
      
      // Notify parent component of successful revision
      if (onRevisionComplete) {
        onRevisionComplete(revisedSentences);
      }

      console.log('Revision completed, new length:', revisedSentences.length);

      // Wait a moment for the content to update, then close the modal
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      handleClose();

    } catch (err) {
      console.error('Revision failed:', err);
      console.error('Error details:', {
        message: err.message,
        response: err.response?.data,
        status: err.response?.status
      });
      
      let errorMessage = 'Failed to revise content. Please try again.';
      
      if (err.response?.data?.error) {
        errorMessage = err.response.data.error;
      } else if (err.message) {
        errorMessage = err.message;
      } else if (err.response?.status === 500) {
        errorMessage = 'Server error occurred during revision. Please try again later.';
      } else if (err.response?.status === 400) {
        errorMessage = 'Invalid request. Please check your feedback and try again.';
      }
      
      setRevisionError(errorMessage);
    } finally {
      setIsRevising(false);
      setRevisionStep('');
    }
  };

  // Update feedback when modal opens
  React.useEffect(() => {
    if (open) {
      handleOpen();
    }
  }, [open]);

  return (
    <>
      {/* Revision feedback modal */}
      <Dialog
        open={open}
        onClose={handleClose}
        maxWidth="md"
        fullWidth
        disableEscapeKeyDown={isRevising}
        sx={{
          '& .MuiDialog-paper': {
            borderRadius: 'var(--border-radius-md)',
          }
        }}
      >
        <DialogTitle sx={{ 
          color: 'var(--dark-gray)', 
          fontWeight: 600,
          borderBottom: '1px solid var(--lighter-gray)',
          pb: 2
        }}>
          Try again with custom feedback
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          <Typography variant="body2" sx={{ 
            color: 'var(--medium-gray)', 
            mb: 2 
          }}>
            Describe what you'd like to improve or change about the current easy-read content. Your feedback will help generate better sentences.
          </Typography>
          <TextField
            autoFocus
            multiline
            rows={6}
            fullWidth
            variant="outlined"
            placeholder="For example: 'The content is missing information about safety procedures' or 'Some sentences are too complex and could be simplified further'"
            value={revisionFeedback}
            onChange={handleFeedbackChange}
            disabled={isRevising || disabled}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 'var(--border-radius-md)',
              }
            }}
          />
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            mt: 1 
          }}>
            <Typography variant="caption" sx={{ color: 'var(--medium-gray)' }}>
              {revisionFeedback.length}/800 characters
            </Typography>
          </Box>
          {revisionError && (
            <Box sx={{ 
              mt: 2, 
              p: 2, 
              bgcolor: 'error.main', 
              color: 'white', 
              borderRadius: 1,
              fontSize: '0.875rem'
            }}>
              <Typography variant="body2" sx={{ color: 'inherit' }}>
                ⚠️ {revisionError}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 3, pt: 1 }}>
          <Button 
            onClick={handleClose}
            disabled={isRevising || disabled}
            sx={{
              color: 'var(--medium-gray)',
              borderRadius: 'var(--border-radius-md)',
            }}
          >
            Cancel
          </Button>
          <Button 
            onClick={handleSubmitRevision}
            variant="contained"
            disabled={isRevising || !revisionFeedback.trim() || disabled}
            startIcon={isRevising ? <CircularProgress size={20} /> : null}
            sx={{
              backgroundColor: 'var(--color-primary)',
              borderRadius: 'var(--border-radius-md)',
              '&:hover': {
                backgroundColor: '#357ae8',
              }
            }}
          >
            {isRevising ? 'Revising...' : 'Revise Content'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Progress overlay during revision */}
      <Backdrop
        open={isRevising}
        sx={{ 
          color: '#fff', 
          zIndex: (theme) => theme.zIndex.modal + 1,
          backdropFilter: 'blur(4px)',
        }}
      >
        <Box sx={{ 
          width: '80%', 
          maxWidth: 'md', 
          p: 3, 
          bgcolor: '#f5f5f5', 
          borderRadius: 'var(--border-radius-md)',
          textAlign: 'center'
        }}>
          <Typography variant="body1" sx={{ 
            mb: 2, 
            fontWeight: 'bold',
            color: 'var(--dark-gray)'
          }}>
            Revising content with your feedback...
          </Typography>
          {revisionStep && (
            <Typography variant="body2" sx={{ 
              mb: 2, 
              color: 'var(--color-primary)', 
              fontStyle: 'italic' 
            }}>
              {revisionStep}
            </Typography>
          )}
          <LinearProgress 
            sx={{ 
              height: 10, 
              borderRadius: 5,
              '& .MuiLinearProgress-bar': {
                backgroundColor: 'var(--color-primary)'
              }
            }}
          />
        </Box>
      </Backdrop>
    </>
  );
};

RevisionModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  content: PropTypes.shape({
    title: PropTypes.string,
    original_markdown: PropTypes.string,
    easy_read_content: PropTypes.array
  }),
  onRevisionComplete: PropTypes.func.isRequired,
  disabled: PropTypes.bool
};

export default RevisionModal;