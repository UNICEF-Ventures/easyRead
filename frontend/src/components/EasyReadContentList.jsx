import React, { useMemo, useCallback } from 'react';
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
  // If it's a relative URL, prepend MEDIA_BASE_URL + /media/
  return `${MEDIA_BASE_URL}/media/${url}`;
};

// Reusable component to display the list of Easy Read sentences and image selectors
function EasyReadContentList({ 
  easyReadContent = [], 
  imageState = {}, 
  onImageSelectionChange, 
  onGenerateImage,
  isLoading = false // Prop to indicate parent loading state
}) {
  
  // Memoize the image selection change handler to prevent unnecessary re-renders
  const handleImageSelectionChange = useCallback((index, value) => {
    if (onImageSelectionChange) {
      onImageSelectionChange(index, value);
    }
  }, [onImageSelectionChange]);
  
  // Memoize the generate image handler to prevent unnecessary re-renders
  const handleGenerateImage = useCallback((index, retrieval) => {
    if (onGenerateImage) {
      onGenerateImage(index, retrieval);
    }
  }, [onGenerateImage]);
  
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
                  
                  {!itemIsLoading && (selectedPath || images.length > 0) && (
                    <Tooltip 
                      title={item.image_retrieval || 'No retrieval query'} 
                      enterDelay={500}
                      arrow
                    >
                      {/* Adjust FormControl to not be fullWidth unnecessarily */}
                      <FormControl size="small" variant="outlined" sx={{ width: '100%' }}> 
                        <Select
                          value={selectedPath || ''}
                          onChange={(e) => {
                            handleImageSelectionChange(index, e.target.value);
                          }}
                          displayEmpty
                          renderValue={(selected) => {
                            if (!selected) {
                              return <Box sx={{ height: 60, width: '100%', bgcolor: 'rgba(0,0,0,0.04)', borderRadius: 1 }} />;
                            }
                            return (
                              <Box 
                                component="img"
                                src={normalizeImageUrl(selected)}
                                alt="Selected"
                                sx={{ 
                                  height: 60, 
                                  width: '100%', // Take full width of the select box display area
                                  objectFit: 'contain',
                                  borderRadius: 1
                                }}
                                onError={(e) => { 
                                  e.target.src = 'https://via.placeholder.com/60x60?text=Error';
                                  console.error('Image load error:', selected);
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
                          {!selectedPath && images.length > 0 && (
                            <MenuItem value="" disabled sx={{ display: 'none' }}>
                              Select Image
                            </MenuItem>
                          )}
                          {images.map((imgResult, imgIndex) => (
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
                                  e.target.src = 'https://via.placeholder.com/100x100?text=Error';
                                  console.error('Image load error:', imgResult.url);
                                }}
                              />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </Tooltip>
                  )}
                  
                  {!itemIsLoading && !selectedPath && images.length === 0 && (
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
                  {canGenerate && onGenerateImage && (
                    <Box sx={{ textAlign: 'center', mt: 1 }}>
                      <Tooltip title={isGenerating ? "Generating..." : "Generate Image"}>
                        <span> 
                          <IconButton 
                            size="small"
                            onClick={() => handleGenerateImage(index, item.image_retrieval)}
                            disabled={isGenerating || itemIsLoading}
                            color="primary"
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
                   primary={item.sentence} 
                   sx={{ m: 0 }}
                />
              </Box>
            </ListItem>
            {index < easyReadContent.length - 1 && <Divider component="li" />}
          </React.Fragment>
        );
      })}
    </List>
  );
}

export default React.memo(EasyReadContentList); 