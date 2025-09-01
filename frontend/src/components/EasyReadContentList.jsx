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
  Stack,
  Checkbox,
  FormControlLabel
} from '@mui/material';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import SearchIcon from '@mui/icons-material/Search';
import EditIcon from '@mui/icons-material/Edit';
import DragIndicatorIcon from '@mui/icons-material/DragIndicator';
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

// Sortable Item Component
const SortableItem = ({ 
  item, 
  index, 
  readOnly, 
  onImageSelectionChange, 
  onGenerateImage,
  onSentenceClick,
  onSentenceKeyDown,
  onSentenceChange,
  onSentenceBlur,
  onHighlightChange,
  editingSentences,
  editedSentenceTexts,
  userKeywords,
  generatorButtonRefs,
  normalizeImageUrl,
  getTooltipText
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ 
    id: index,
    animateLayoutChanges: ({ isSorting, wasDragging }) => {
      // Don't animate layout changes after sorting is complete
      return isSorting && !wasDragging;
    }
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const { 
    images, 
    selectedPath, 
    isLoading: itemIsLoading, 
    error 
  } = item.imageData || {};

  return (
    <React.Fragment>
      <ListItem 
        ref={setNodeRef}
        style={style}
        sx={{ 
          py: 3, 
          display: 'flex', 
          flexDirection: 'row',
          alignItems: 'center',
          gap: 2
        }}
      >
        {/* Drag Handle and Edit Button Column */}
        {!readOnly && (
          <Box 
            sx={{ 
              display: 'flex', 
              flexDirection: 'column',
              alignItems: 'center',
              gap: 0.5,
              mr: 1
            }}
          >
            {/* Drag Handle */}
            <Box 
              {...attributes} 
              {...listeners}
              sx={{ 
                display: 'flex', 
                alignItems: 'center',
                cursor: isDragging ? 'grabbing' : 'grab',
                color: 'text.secondary',
                '&:hover': { color: 'primary.main' }
              }}
            >
              <DragIndicatorIcon />
            </Box>
            
            {/* Edit Button */}
            {item.canGenerate && (
              <Tooltip title={itemIsLoading ? "Generating..." : "Edit Keywords"}>
                <span> 
                  <IconButton
                    size="small"
                    onClick={() => onGenerateImage(index)}
                    disabled={itemIsLoading}
                    color="primary"
                    aria-label="Edit keywords"
                    ref={(el) => { generatorButtonRefs.current[index] = el; }}
                    sx={{ minWidth: 'auto', p: 0.5 }}
                  >
                    {itemIsLoading ? <CircularProgress size={16} color="inherit" /> : <EditIcon fontSize="small" />}
                  </IconButton>
                </span>
              </Tooltip>
            )}
          </Box>
        )}

        {/* Image Column */}
        <Box sx={{ flexShrink: 0, width: 120 }}>
          {itemIsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 100 }}>
              <CircularProgress size={30} />
            </Box>
          ) : error ? (
            <Typography variant="caption" color="error" sx={{ textAlign: 'center', display: 'block' }}>
              Error loading images
            </Typography>
          ) : (
            <Grid container direction="column" spacing={1}>
              <Grid item>
                <Tooltip 
                  title={getTooltipText(index, item)}
                  enterDelay={500}
                  arrow
                  componentsProps={{
                    tooltip: {
                      sx: {
                        whiteSpace: 'pre-line',
                        maxWidth: 300,
                        fontSize: '0.75rem'
                      }
                    }
                  }}
                >
                  <FormControl fullWidth size="small">
                    <Select
                    value={selectedPath || ''}
                    onChange={(e) => onImageSelectionChange(index, e.target.value)}
                    displayEmpty
                    disabled={readOnly}
                    renderValue={(selected) => {
                      if (!selected) return <em>No image selected</em>;
                      return (
                        <Box component="img"
                          src={normalizeImageUrl(selected)}
                          alt="Selected"
                          sx={{ width: '100%', height: 60, objectFit: 'contain' }}
                        />
                      );
                    }}
                    MenuProps={{
                      PaperProps: {
                        sx: { maxHeight: 300, width: 'auto' },
                      },
                    }}
                  >
                    {!selectedPath && images && images.length > 0 && (
                      <MenuItem value="" disabled sx={{ display: 'none' }}>
                        Select Image
                      </MenuItem>
                    )}
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
                            e.target.style.display = 'none';
                            console.error('Image load error:', selectedPath);
                          }}
                        />
                      </MenuItem>
                    )}
                    {images && images.length > 0 && images.map((image) => (
                      <MenuItem key={`${index}-${image.url}`} value={image.url} sx={{ display: 'flex', justifyContent: 'center', p: 0.5 }}>
                        <Tooltip 
                          title={userKeywords[index] ? userKeywords[index] : (image.description || 'No description')}
                          placement="right"
                          arrow
                        >
                          <Box 
                            component="img"
                            src={normalizeImageUrl(image.url)}
                            alt={image.description || 'Image option'}
                            sx={{ 
                              width: 100, 
                              height: 100, 
                              objectFit: 'contain'
                            }}
                            onError={(e) => { 
                              e.target.style.display = 'none';
                              console.error('Image load error:', image.url);
                            }}
                          />
                        </Tooltip>
                      </MenuItem>
                    ))}
                  </Select>
                  </FormControl>
                </Tooltip>
              </Grid>
            </Grid>
          )}
        </Box>
        
        {/* Sentence Column */}
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          {editingSentences[index] ? (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <TextField
                fullWidth
                value={editedSentenceTexts[index] || item.sentence}
                onChange={(e) => onSentenceChange(index, e.target.value)}
                onKeyDown={(e) => onSentenceKeyDown(e, index)}
                onBlur={(e) => {
                  // Don't close editing if the user clicked on the checkbox or its container
                  const isCheckboxClick = e.relatedTarget && (
                    e.relatedTarget.type === 'checkbox' ||
                    e.relatedTarget.closest('.MuiFormControlLabel-root')
                  );
                  if (!isCheckboxClick) {
                    onSentenceBlur(index);
                  }
                }}
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
              <Box 
                sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                onMouseDown={(e) => e.preventDefault()} // Prevent blur when clicking
              >
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={item.highlighted || false}
                      onChange={(e) => onHighlightChange && onHighlightChange(index, e.target.checked)}
                      size="small"
                      color="primary"
                    />
                  }
                  label="Highlight this sentence"
                  sx={{ fontSize: '0.875rem' }}
                />
                <Typography variant="caption" color="text.secondary">
                  Press Enter to save, Escape to cancel
                </Typography>
              </Box>
            </Box>
          ) : (
            <ListItemText 
               primary={
                 <Typography 
                   variant="body1" 
                   onClick={() => onSentenceClick(index)}
                   sx={{ 
                     fontWeight: item.highlighted ? 'bold' : 'normal',
                     cursor: readOnly ? 'default' : 'pointer',
                     '&:hover': !readOnly && {
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
                   title={readOnly ? undefined : "Click to edit sentence"}
                 >
                   {item.sentence}
                 </Typography>
               }
               sx={{ m: 0 }}
            />
          )}
        </Box>
      </ListItem>
      {index < item.totalLength - 1 && <Divider component="li" />}
    </React.Fragment>
  );
};

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
  onHighlightChange, // New prop for handling highlight changes
  onReorderSentences, // New prop for handling sentence reordering
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

  // Sensors for drag and drop
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );
  
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

  // Handle drag end for sentence reordering
  const handleDragEnd = useCallback((event) => {
    const { active, over } = event;

    if (active.id !== over?.id && onReorderSentences) {
      const oldIndex = easyReadContent.findIndex((_, index) => index === active.id);
      const newIndex = easyReadContent.findIndex((_, index) => index === over.id);
      
      const newOrder = arrayMove(easyReadContent, oldIndex, newIndex);
      onReorderSentences(newOrder);
    }
  }, [easyReadContent, onReorderSentences]);
  
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
            💡 <strong>Tip:</strong> Click on any sentence to edit the text. Drag the grip handle to reorder sentences. Click on the edit icon next to images to search for different images or generate new ones.
          </Typography>
        </Box>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext 
          items={memoizedContentList.map((_, index) => index)}
          strategy={verticalListSortingStrategy}
        >
          <List disablePadding>
          {memoizedContentList.map((item) => {
        const { index } = item;

        const itemData = {
          ...item,
          imageData: item.currentImageState,
          totalLength: easyReadContent.length
        };

        return (
          <SortableItem
            key={index}
            item={itemData}
            index={index}
            readOnly={readOnly}
            onImageSelectionChange={handleImageSelectionChange}
            onGenerateImage={handleGenerateImage}
            onSentenceClick={handleSentenceClick}
            onSentenceKeyDown={handleSentenceKeyDown}
            onSentenceChange={handleSentenceChange}
            onSentenceBlur={handleSentenceBlur}
            onHighlightChange={onHighlightChange}
            editingSentences={editingSentences}
            editedSentenceTexts={editedSentenceTexts}
            userKeywords={userKeywords}
            generatorButtonRefs={generatorButtonRefs}
            normalizeImageUrl={normalizeImageUrl}
            getTooltipText={getTooltipText}
          />
        );
      })}
          </List>
        </SortableContext>
      </DndContext>
    
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
  onSentenceChange: PropTypes.func,
  onHighlightChange: PropTypes.func,
  onReorderSentences: PropTypes.func,
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
  onSentenceChange: null,
  onHighlightChange: null,
  onReorderSentences: null,
  isLoading: false,
  readOnly: false
};

export default React.memo(EasyReadContentList); 