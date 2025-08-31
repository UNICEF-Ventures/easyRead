import React, { useMemo, useCallback, useState, useRef } from 'react';
import PropTypes from 'prop-types';
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
  IconButton,
  Chip,
  Stack
} from '@mui/material';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import SearchIcon from '@mui/icons-material/Search';
import EditIcon from '@mui/icons-material/Edit';
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
  onSearchWithCustomKeywords, // New prop for searching with custom keywords
  onSentenceChange, // New prop for handling sentence text changes
  userKeywords = {}, // Receive userKeywords from hook
  isLoading = false, // Prop to indicate parent loading state
  readOnly = false // Prop to disable editing capabilities
}) {
  const [promptModalOpen, setPromptModalOpen] = useState(false);
  const [activeSentenceIndex, setActiveSentenceIndex] = useState(null);
  const [editablePrompt, setEditablePrompt] = useState('');
  const [editingSentences, setEditingSentences] = useState({}); // Track which sentences are being edited
  const [editedSentenceTexts, setEditedSentenceTexts] = useState({}); // Store edited sentence content
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
  }, [userKeywords]);

  const closeModal = useCallback(() => {
    setPromptModalOpen(false);
    // Restore focus to the generator button that opened the modal
    if (activeSentenceIndex !== null && generatorButtonRefs.current[activeSentenceIndex]) {
      try { 
        generatorButtonRefs.current[activeSentenceIndex].focus(); 
      } catch (error) {
        // Focus may fail if element is no longer available
        console.debug('Failed to restore focus:', error);
      }
    }
    setActiveSentenceIndex(null);
    setEditablePrompt('');
  }, [activeSentenceIndex]);

  const handleSearchImages = useCallback(() => {
    const value = (editablePrompt || '').trim();
    if (!value) {
      return;
    }
    if (onSearchWithCustomKeywords && activeSentenceIndex !== null) {
      onSearchWithCustomKeywords(activeSentenceIndex, value);
    }
    closeModal();
  }, [editablePrompt, onSearchWithCustomKeywords, activeSentenceIndex, closeModal]);
  
  const handleGenerateImageSubmit = useCallback(() => {
    const value = (editablePrompt || '').trim();
    if (!value) {
      return;
    }
    if (onGenerateImage && activeSentenceIndex !== null) {
      onGenerateImage(activeSentenceIndex, value);
    }
    closeModal();
  }, [editablePrompt, onGenerateImage, activeSentenceIndex, closeModal]);
  
  // Helper function to generate informative tooltip text
  const getTooltipText = useCallback((index, item) => {
    const customKeywords = userKeywords[index];
    const originalKeywords = item.image_retrieval;
    
    if (!customKeywords && !originalKeywords) {
      return 'No keywords available';
    }
    
    // If user has custom keywords that differ from original, show as "Custom: ..."
    if (customKeywords && originalKeywords && customKeywords !== originalKeywords) {
      return `Custom: "${customKeywords}"`;
    }
    
    // Otherwise, just show the keywords (whether custom or original)
    const keywords = customKeywords || originalKeywords;
    return `"${keywords}"`;
  }, [userKeywords]);
  
  // Handlers for inline sentence editing
  const handleSentenceClick = useCallback((index, currentSentence) => {
    if (readOnly) return; // Don't allow editing in read-only mode
    
    setEditingSentences(prev => ({ ...prev, [index]: true }));
    setEditedSentenceTexts(prev => ({ ...prev, [index]: currentSentence }));
  }, [readOnly]);
  
  const handleSentenceKeyDown = useCallback((event, index) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      // Save the edited sentence
      const newText = editedSentenceTexts[index]?.trim();
      if (newText && newText !== easyReadContent[index]?.sentence) {
        if (onSentenceChange) {
          onSentenceChange(index, newText);
        }
      }
      
      // Exit editing mode
      setEditingSentences(prev => ({ ...prev, [index]: false }));
      setEditedSentenceTexts(prev => ({ ...prev, [index]: undefined }));
    } else if (event.key === 'Escape') {
      event.preventDefault();
      // Cancel editing
      setEditingSentences(prev => ({ ...prev, [index]: false }));
      setEditedSentenceTexts(prev => ({ ...prev, [index]: undefined }));
    }
  }, [editedSentenceTexts, easyReadContent, onSentenceChange]);
  
  const handleSentenceChange = useCallback((index, value) => {
    setEditedSentenceTexts(prev => ({ ...prev, [index]: value }));
  }, []);
  
  const handleSentenceBlur = useCallback((index) => {
    // Cancel editing on blur without saving
    setEditingSentences(prev => ({ ...prev, [index]: false }));
    setEditedSentenceTexts(prev => ({ ...prev, [index]: undefined }));
  }, []);
  
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
      {/* Instructions for users */}
      {!readOnly && (
        <Box 
          sx={{ 
            mb: 2, 
            p: 2, 
            backgroundColor: 'rgba(25, 118, 210, 0.05)',
            borderRadius: 1,
            border: '1px solid rgba(25, 118, 210, 0.2)'
          }}
        >
          <Typography variant="body2" color="text.secondary">
            💡 <strong>Tip:</strong> Click on any sentence to edit the text. Click on the edit icon next to images to search for different images or generate new ones.
          </Typography>
        </Box>
      )}

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
                    <Box>
                      <Tooltip 
                        title={getTooltipText(index, item)}
                        enterDelay={500}
                        arrow
                        componentsProps={{
                          tooltip: {
                            sx: {
                              whiteSpace: 'pre-line', // Allow line breaks in tooltip
                              maxWidth: 300,
                              fontSize: '0.75rem'
                            }
                          }
                        }}
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
                      
                    </Box>
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
                  
                  {/* Visual indicator for customized keywords */}
                  {userKeywords[index] && userKeywords[index] !== item.image_retrieval && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 0.5 }}>
                      <Chip 
                        size="small" 
                        label="Custom Keywords" 
                        color="primary" 
                        variant="outlined"
                        sx={{ 
                          fontSize: '0.65rem', 
                          height: 18,
                          '& .MuiChip-label': {
                            px: 1
                          }
                        }}
                      />
                    </Box>
                  )}
                  
                  {/* Center the generate icon below the image area */}
                  {canGenerate && onGenerateImage && !readOnly && (
                    <Box sx={{ textAlign: 'center', mt: 1 }}>
                      <Tooltip title={isGenerating ? "Generating..." : "Edit Keywords"}>
                        <span> 
                          <IconButton 
                            size="small"
                            onClick={() => handleGenerateImage(index, item.image_retrieval)}
                            disabled={isGenerating || itemIsLoading}
                            color="primary"
                            aria-label="Edit keywords"
                            ref={(el) => { generatorButtonRefs.current[index] = el; }}
                          >
                            {isGenerating ? <CircularProgress size={20} color="inherit" /> : <EditIcon />}
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Box>
                  )}
              </Box>
              
              {/* Sentence Column (takes remaining space) */}
              <Box sx={{ flexGrow: 1, minWidth: 0 }}> {/* minWidth: 0 prevents overflow issues */}
                {editingSentences[index] ? (
                  <TextField
                    fullWidth
                    value={editedSentenceTexts[index] || item.sentence}
                    onChange={(e) => handleSentenceChange(index, e.target.value)}
                    onKeyDown={(e) => handleSentenceKeyDown(e, index)}
                    onBlur={() => handleSentenceBlur(index)}
                    autoFocus
                    variant="outlined"
                    size="small"
                    multiline
                    rows={2}
                    sx={{ 
                      '& .MuiOutlinedInput-root': {
                        backgroundColor: 'rgba(25, 118, 210, 0.08)',
                      }
                    }}
                  />
                ) : (
                  <ListItemText 
                     primary={
                       <Typography 
                         variant="body1" 
                         onClick={() => handleSentenceClick(index)}
                         sx={{ 
                           fontWeight: item.highlighted ? 'bold' : 'normal',
                           cursor: 'pointer',
                           '&:hover': {
                             backgroundColor: 'rgba(0, 0, 0, 0.04)',
                             borderRadius: 1,
                             padding: '4px 8px',
                             margin: '-4px -8px'
                           },
                           ...(item.highlighted && { 
                             color: 'primary.main',
                             fontSize: '1.05em'
                           })
                         }}
                         title="Click to edit sentence"
                       >
                         {item.sentence}
                       </Typography>
                     }
                     sx={{ m: 0 }}
                  />
                )}
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
      <div>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Keywords / prompt"
            type="text"
            fullWidth
            multiline
            maxRows={3}
            value={editablePrompt}
            onChange={(e) => setEditablePrompt(e.target.value)}
            inputProps={{ maxLength: 500 }}
            helperText={`${editablePrompt.length}/500 characters`}
          />
          <Typography variant="caption" color="text.secondary">
            These keywords will be used to search image sets or generate new images. You can adjust them.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeModal}>Cancel</Button>
          <Button
            onClick={handleSearchImages}
            disabled={!editablePrompt || editablePrompt.trim() === ''}
            startIcon={<SearchIcon />}
          >
            Search Image Sets
          </Button>
          <Button
            variant="contained"
            onClick={handleGenerateImageSubmit}
            disabled={!editablePrompt || editablePrompt.trim() === ''}
            startIcon={<AutoFixHighIcon />}
          >
            Generate New Image
          </Button>
        </DialogActions>
      </div>
    </Dialog>
    </React.Fragment>
  );
}

// PropTypes for type safety
EasyReadContentList.propTypes = {
  easyReadContent: PropTypes.arrayOf(PropTypes.shape({
    sentence: PropTypes.string.isRequired,
    image_retrieval: PropTypes.string,
    selected_image_path: PropTypes.string,
    alternative_images: PropTypes.arrayOf(PropTypes.string),
    user_keywords: PropTypes.string
  })),
  imageState: PropTypes.objectOf(PropTypes.shape({
    images: PropTypes.arrayOf(PropTypes.shape({
      url: PropTypes.string.isRequired,
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number])
    })),
    selectedPath: PropTypes.string,
    isLoading: PropTypes.bool,
    isGenerating: PropTypes.bool,
    error: PropTypes.string
  })),
  userKeywords: PropTypes.objectOf(PropTypes.string),
  onImageSelectionChange: PropTypes.func,
  onGenerateImage: PropTypes.func,
  onSearchWithCustomKeywords: PropTypes.func,
  isLoading: PropTypes.bool,
  readOnly: PropTypes.bool
};

// Default props
EasyReadContentList.defaultProps = {
  easyReadContent: [],
  imageState: {},
  userKeywords: {},
  onImageSelectionChange: null,
  onGenerateImage: null,
  onSearchWithCustomKeywords: null,
  isLoading: false,
  readOnly: false
};

export default React.memo(EasyReadContentList); 