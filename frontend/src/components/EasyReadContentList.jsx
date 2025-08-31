import React, { useMemo, useCallback, useState, useRef } from 'react';
import {
  Box,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress,
  Grid,
  Select,
  MenuItem,
  FormControl,
  Typography,
  Tooltip,
  Button,
  IconButton
} from '@mui/material';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

// Helper function to normalize image URLs
const normalizeImageUrl = (url) => {
  if (!url) return '';
  // If it's already an absolute URL, return it as is
  if (url.startsWith('http://') || url.startsWith('https://')) {
    return url;
  }
  // If it's a relative URL (e.g., /media/...), prepend MEDIA_BASE_URL
  return `${MEDIA_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;
};

// Reusable component to display the list of Easy Read sentences and image selectors
function EasyReadContentList({ 
  easyReadContent = [], 
  imageState = {}, 
  onImageSelectionChange, 
  onGenerateImage,
  isLoading = false, // Prop to indicate parent loading state
  readOnly = false // Prop to disable editing capabilities
}) {
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [activeSentenceIndex, setActiveSentenceIndex] = useState(null);
  const [editablePrompt, setEditablePrompt] = useState('');
  const [userKeywords, setUserKeywords] = useState({}); // Store user-input keywords per sentence
  const generatorButtonRefs = useRef({});
  
  // Memoize the image selection change handler to prevent unnecessary re-renders
  const handleImageSelectionChange = useCallback((index, value) => {
    if (onImageSelectionChange) {
      onImageSelectionChange(index, value);
    }
  }, [onImageSelectionChange]);
  
  // Memoize the generate image handler to prevent unnecessary re-renders
  const handleGenerateImage = useCallback((index, retrieval) => {
    // Open modal allowing user to edit the prompt before generating
    setActiveSentenceIndex(index);
    // Use stored user keywords if available, otherwise use original retrieval
    setEditablePrompt(userKeywords[index] || retrieval || '');
    setPromptModalOpen(true);
  }, [onGenerateImage, userKeywords]);

  const closeModal = useCallback(() => {
    setPromptModalOpen(false);
    // Restore focus to the generator button that opened the modal
    if (activeSentenceIndex !== null && generatorButtonRefs.current[activeSentenceIndex]) {
      try { generatorButtonRefs.current[activeSentenceIndex].focus(); } catch {}
    }
    setActiveSentenceIndex(null);
    setEditablePrompt('');
  }, [activeSentenceIndex]);

  const submitPrompt = useCallback(() => {
    const value = (editablePrompt || '').trim();
    if (!value) return;
    if (onGenerateImage && activeSentenceIndex !== null) {
      // Store the user keywords for this sentence
      setUserKeywords(prev => ({ ...prev, [activeSentenceIndex]: value }));
      onGenerateImage(activeSentenceIndex, value);
    }
    // Close immediately; the per-item icon will show spinner via isGenerating
    closeModal();
  }, [editablePrompt, onGenerateImage, activeSentenceIndex, closeModal]);
  
  // Memoize the content list to prevent unnecessary re-renders when imageState changes
  const memoizedContentList = useMemo(() => {
    if (!easyReadContent || easyReadContent.length === 0) {
      return [];
    }
    
    return easyReadContent.map((item, index) => {
      const currentImageState = imageState[index] || { 
        images: [], 
        selectedPath: item.selected_image_path,
        isLoading: false, 
        isGenerating: false,
        error: null 
      };
      
      
      return {
        ...item,
        index,
        currentImageState,
        canGenerate: item.image_retrieval && item.image_retrieval !== 'error'
      };
    });
  }, [easyReadContent, imageState]);
  
  // If parent is loading, show a single spinner
  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
        <CircularProgress />
      </Box>
    );
  }
  
  // If no content, display message
  if (!easyReadContent || easyReadContent.length === 0) {
    return (
      <Typography color="text.secondary" sx={{ py: 2, textAlign: 'center' }}>
        No Easy Read content available.
      </Typography>
    );
  }

  return (
    <React.Fragment>
      <List disablePadding>
      {memoizedContentList.map((item) => {
        const { 
          images, 
          selectedPath, 
          isLoading: itemIsLoading, 
          isGenerating,
          error 
        } = item.currentImageState;
        const { index, canGenerate } = item;

        return (
          <React.Fragment key={index}>
            {/* Use Flexbox on ListItem for better control */}
            <ListItem sx={{ 
              py: 3, 
              display: 'flex', 
              flexDirection: 'row', // Explicitly row
              alignItems: 'flex-start', // Align items at the top
              gap: 2 // Add gap between image column and text column
            }}>
              {/* Image Controls Column (fixed width) */}
              <Box sx={{ 
                width: { xs: 100, sm: 120, md: 130 }, // Responsive fixed width
                flexShrink: 0 // Prevent this column from shrinking
              }}>
                  {itemIsLoading && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 100 }}>
                      <CircularProgress size={24} />
                    </Box>
                  )}
                  
                  {!itemIsLoading && (selectedPath || (images && images.length > 0)) && (
                    <Tooltip 
                      title={userKeywords[index] || item.image_retrieval || 'No retrieval query'} 
                      enterDelay={500}
                      arrow
                    >
                      {/* Adjust FormControl to not be fullWidth unnecessarily */}
                      <FormControl size="small" variant="outlined" sx={{ width: '100%' }}> 
                        <Select
                          value={selectedPath || ''}
                          onChange={readOnly ? undefined : (e) => {
                            handleImageSelectionChange(index, e.target.value);
                          }}
                          disabled={readOnly}
                          displayEmpty
                          renderValue={(selected) => {
                            if (!selected) {
                              return <Box sx={{ height: 60, width: '100%', bgcolor: 'rgba(0,0,0,0.04)', borderRadius: 1 }} />;
                            }
                            
                            // If selectedPath exists but not in current options, show it anyway
                            // This handles the case where images are still loading but we have a saved selection
                            const displayPath = selected || selectedPath;
                            if (!displayPath) {
                              return <Box sx={{ height: 60, width: '100%', bgcolor: 'rgba(0,0,0,0.04)', borderRadius: 1 }} />;
                            }
                            
                            return (
                              <Box 
                                component="img"
                                src={normalizeImageUrl(displayPath)}
                                alt="Selected"
                                sx={{ 
                                  height: 60, 
                                  width: '100%', // Take full width of the select box display area
                                  objectFit: 'contain',
                                  borderRadius: 1
                                }}
                                onError={(e) => { 
                                  // Prevent infinite loop by hiding the image instead of loading another URL
                                  e.target.style.display = 'none';
                                  console.error('Image load error:', displayPath);
                                }}
                              />
                            );
                          }}
                          MenuProps={{
                            PaperProps: {
                              sx: { maxHeight: 300, width: 'auto' }, // Adjust width if needed
                            },
                          }}
                        >
                          {!selectedPath && images && images.length > 0 && (
                            <MenuItem value="" disabled sx={{ display: 'none' }}>
                              Select Image
                            </MenuItem>
                          )}
                          {/* If selectedPath exists but is not in images array, add it as an option */}
                          {selectedPath && images && !images.some(img => img.url === selectedPath) && (
                            <MenuItem key={`${index}-selected-${selectedPath}`} value={selectedPath} sx={{ display: 'flex', justifyContent: 'center', p: 0.5 }}>
                              <Box 
                                component="img"
                                src={normalizeImageUrl(selectedPath)}
                                alt="Current Selection"
                                sx={{ 
                                  width: 100, 
                                  height: 100, 
                                  objectFit: 'contain'
                                }}
                                onError={(e) => { 
                                  // Prevent infinite loop by hiding the image instead of loading another URL
                                  e.target.style.display = 'none';
                                  console.error('Image load error:', selectedPath);
                                }}
                              />
                            </MenuItem>
                          )}
                          {images && images.map((imgResult, imgIndex) => (
                            <MenuItem key={`${index}-${imgIndex}-${imgResult.url}`} value={imgResult.url} sx={{ display: 'flex', justifyContent: 'center', p: 0.5 }}>
                              <Box 
                                component="img"
                                src={normalizeImageUrl(imgResult.url)}
                                alt={imgResult.description || `Option ${imgIndex + 1}`}
                                sx={{ 
                                  width: 100, 
                                  height: 100, 
                                  objectFit: 'contain'
                                }}
                                onError={(e) => { 
                                  // Prevent infinite loop by hiding the image instead of loading another URL
                                  e.target.style.display = 'none';
                                  console.error('Image load error:', imgResult.url);
                                }}
                              />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Tooltip>
                  )}
                  
                  {!itemIsLoading && !selectedPath && (!images || images.length === 0) && (
                    <Box sx={{
                      width: '100%', // Take full width of the column
                      height: 60,
                      display: 'flex',
                      justifyContent: 'center',
                      alignItems: 'center',
                      bgcolor: 'rgba(0, 0, 0, 0.04)',
                      borderRadius: 1,
                      mb: 1
                    }}>
                      <Typography variant="caption" color="text.secondary" align="center" sx={{ px: 1 }}>
                        {error || 'No image'}
                      </Typography>
                    </Box>
                  )}
                  
                  {/* Center the generate icon below the image area */}
                  {canGenerate && onGenerateImage && !readOnly && (
                    <Box sx={{ textAlign: 'center', mt: 1 }}>
                      <Tooltip title={isGenerating ? "Generating..." : "Generate Image"}>
                        <span> 
                          <IconButton 
                            size="small"
                            onClick={() => handleGenerateImage(index, item.image_retrieval)}
                            disabled={isGenerating || itemIsLoading}
                            color="primary"
                            aria-label="Generate image"
                            ref={(el) => { generatorButtonRefs.current[index] = el; }}
                          >
                            {isGenerating ? <CircularProgress size={20} color="inherit" /> : <AutoFixHighIcon />}
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Box>
                  )}
              </Box>
              
              {/* Sentence Column (takes remaining space) */}
              <Box sx={{ flexGrow: 1, minWidth: 0 }}> {/* minWidth: 0 prevents overflow issues */}
                <ListItemText 
                   primary={
                     <Typography 
                       variant="body1" 
                       sx={{ 
                         fontWeight: item.highlighted ? 'bold' : 'normal',
                         ...(item.highlighted && { 
                           color: 'primary.main',
                           fontSize: '1.05em'
                         })
                       }}
                     >
                       {item.sentence}
                     </Typography>
                   }
                   sx={{ m: 0 }}
                />
              </Box>
            </ListItem>
            {index < easyReadContent.length - 1 && <Divider component="li" />}
          </React.Fragment>
        );
      })}
    </List>
    
    {/* Prompt Edit Modal */}
    <Dialog open={promptModalOpen} onClose={closeModal} fullWidth maxWidth="sm" aria-labelledby="edit-prompt-title">
      <DialogTitle id="edit-prompt-title">
        Edit keywords for sentence: "{activeSentenceIndex !== null && easyReadContent[activeSentenceIndex] ? easyReadContent[activeSentenceIndex].sentence : ''}"
      </DialogTitle>
      <form onSubmit={(e) => { e.preventDefault(); submitPrompt(); }}>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Keywords / prompt"
            type="text"
            fullWidth
            value={editablePrompt}
            onChange={(e) => setEditablePrompt(e.target.value)}
          />
          <Typography variant="caption" color="text.secondary">
            These keywords will be used to generate the image. You can adjust them.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeModal}>Cancel</Button>
          <Button
            variant="contained"
            type="submit"
            disabled={!editablePrompt || editablePrompt.trim() === ''}
          >
            Generate
          </Button>
        </DialogActions>
      </form>
    </Dialog>
    </React.Fragment>
  );
}

export default React.memo(EasyReadContentList); 