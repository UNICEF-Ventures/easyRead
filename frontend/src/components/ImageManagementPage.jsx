import React, { useState, useEffect, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { 
  Box, 
  Typography, 
  Button, 
  TextField, 
  Grid, 
  Card, 
  CardMedia, 
  CardContent, 
  Chip,
  CircularProgress, 
  Snackbar, 
  Alert,
  Paper,
  Container,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemAvatar,
  Avatar,
  IconButton,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from '@mui/material';
import { styled } from '@mui/material/styles';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import { listImages, uploadImage, batchUploadImages, getImageSets } from '../apiClient';

// Maximum file size in bytes (5MB)
const MAX_FILE_SIZE = 5 * 1024 * 1024;

// Styled component for file input
const VisuallyHiddenInput = styled('input')({
  clip: 'rect(0 0 0 0)',
  clipPath: 'inset(50%)',
  height: 1,
  overflow: 'hidden',
  position: 'absolute',
  bottom: 0,
  left: 0,
  whiteSpace: 'nowrap',
  width: 1,
});

// Styled component for drop zone
const DropZone = styled(Box)(({ theme, isDragging }) => ({
  border: `2px dashed ${isDragging ? theme.palette.primary.main : theme.palette.divider}`,
  borderRadius: theme.shape.borderRadius,
  padding: theme.spacing(4),
  backgroundColor: isDragging ? theme.palette.action.hover : 'transparent',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  transition: 'all 0.2s',
  cursor: 'pointer',
  minHeight: 150,
}));

const ImageManagementPage = () => {
  // Separate state for uploaded and generated images
  const [uploadedImages, setUploadedImages] = useState({}); // Now stores images by set
  const [generatedImages, setGeneratedImages] = useState([]);
  
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [imageLabels, setImageLabels] = useState({}); // Track individual image labels
  const [imageSets, setImageSets] = useState([]);
  const [selectedSet, setSelectedSet] = useState('');
  const [newSetName, setNewSetName] = useState('');
  const [showNewSetDialog, setShowNewSetDialog] = useState(false);
  const [alert, setAlert] = useState({ open: false, message: '', severity: 'success' });

  // Clean up object URLs when component unmounts
  useEffect(() => {
    return () => {
      // Revoke any object URLs to avoid memory leaks
      selectedFiles.forEach(file => {
        if (file.preview) {
          URL.revokeObjectURL(file.preview);
        }
      });
    };
  }, [selectedFiles]);

  const fetchImages = useCallback(async () => {
    setLoading(true);
    try {
      const response = await listImages();
      console.log('API Response:', response.data);
      
      // Process the new API response structure - images_by_set
      const imagesBySet = response.data.images_by_set || {};
      
      // Store images grouped by set
      setUploadedImages(imagesBySet);
      
      // For backward compatibility, also store generated images separately
      const generatedImages = imagesBySet.Generated || [];
      setGeneratedImages(generatedImages); 
    } catch (error) {
      console.error('Error fetching images:', error);
      showAlert('Error loading images', 'error');
      setUploadedImages({}); // Clear on error
      setGeneratedImages([]); // Clear on error
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchImageSets = useCallback(async () => {
    try {
      const response = await getImageSets();
      setImageSets(response.data.sets);
    } catch (error) {
      console.error('Error fetching image sets:', error);
    }
  }, []);

  // Fetch all images and sets on component mount
  useEffect(() => {
    fetchImages();
    fetchImageSets();
  }, [fetchImages, fetchImageSets]);

  // Generate default label from filename
  const generateDefaultLabel = (filename) => {
    const nameWithoutExtension = filename.replace(/\.[^/.]+$/, '');
    if (nameWithoutExtension.includes('_')) {
      return nameWithoutExtension.split('_')[0];
    }
    return nameWithoutExtension;
  };

  const onDrop = (acceptedFiles) => {
    // Filter out files over the size limit
    const validFiles = acceptedFiles.filter(file => {
      if (file.size > MAX_FILE_SIZE) {
        showAlert(`File ${file.name} is too large (max: 5MB)`, 'warning');
        return false;
      }
      return true;
    });

    // Create preview URLs and default labels for valid files
    const filesWithPreviews = validFiles.map((file, index) => {
      const fileWithPreview = Object.assign(file, {
        preview: URL.createObjectURL(file),
        id: Date.now() + index // Unique ID for tracking
      });
      
      // Set default label
      setImageLabels(prev => ({
        ...prev,
        [fileWithPreview.id]: generateDefaultLabel(file.name)
      }));
      
      return fileWithPreview;
    });

    setSelectedFiles(prev => [...prev, ...filesWithPreviews]);
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/jpeg': [],
      'image/png': [],
      'image/gif': [],
      'image/webp': []
    },
    maxSize: MAX_FILE_SIZE
  });

  const handleRemoveFile = (index) => {
    setSelectedFiles(prev => {
      const newFiles = [...prev];
      const fileToRemove = newFiles[index];
      
      // Revoke the URL to prevent memory leaks
      if (fileToRemove.preview) {
        URL.revokeObjectURL(fileToRemove.preview);
      }
      
      // Remove the label for this file
      setImageLabels(prevLabels => {
        const newLabels = { ...prevLabels };
        delete newLabels[fileToRemove.id];
        return newLabels;
      });
      
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleLabelChange = (fileId, newLabel) => {
    setImageLabels(prev => ({
      ...prev,
      [fileId]: newLabel
    }));
  };

  const handleSetChange = (event) => {
    const value = event.target.value;
    if (value === 'CREATE_NEW') {
      setShowNewSetDialog(true);
    } else {
      setSelectedSet(value);
    }
  };

  const handleCreateNewSet = () => {
    if (newSetName.trim()) {
      setSelectedSet(newSetName.trim());
      setImageSets(prev => [...prev, { name: newSetName.trim(), imageCount: 0 }]);
      setNewSetName('');
      setShowNewSetDialog(false);
    }
  };

  const handleCancelNewSet = () => {
    setNewSetName('');
    setShowNewSetDialog(false);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      showAlert('Please select at least one file', 'warning');
      return;
    }

    if (!selectedSet) {
      showAlert('Please select an image set', 'warning');
      return;
    }

    setUploading(true);
    setUploadingCount(0);
    
    try {
      // Upload each file individually with its specific label and set
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        const label = imageLabels[file.id] || generateDefaultLabel(file.name);
        
        // Create a clean File object to avoid issues with react-dropzone properties
        const cleanFile = new File([file], file.name, { type: file.type });
        
        await uploadImage(cleanFile, label, selectedSet);
        setUploadingCount(i + 1);
      }
      
      showAlert(`Successfully uploaded ${selectedFiles.length} image(s)`, 'success');
      
      // Reset form
      selectedFiles.forEach(file => {
        if (file.preview) URL.revokeObjectURL(file.preview);
      });
      setSelectedFiles([]);
      setImageLabels({});
      setSelectedSet('');
      
      // Refresh image list and sets
      fetchImages();
      fetchImageSets();
    } catch (error) {
      console.error('Error uploading images:', error);
      showAlert('Error uploading images', 'error');
    } finally {
      setUploading(false);
      setUploadingCount(0);
    }
  };

  const showAlert = (message, severity) => {
    setAlert({
      open: true,
      message,
      severity
    });
  };

  const handleCloseAlert = () => {
    setAlert({ ...alert, open: false });
  };

  // Helper function to render an image list section
  const renderImageList = (title, imageList) => (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" component="h2" gutterBottom sx={{ 
        borderBottom: '2px solid #e0e0e0', 
        pb: 1,
        display: 'flex',
        alignItems: 'center',
        gap: 1
      }}>
        {title}
      </Typography>
      {loading ? (
        <CircularProgress />
      ) : imageList.length === 0 ? (
        <Typography color="textSecondary">No {title.toLowerCase()} found.</Typography>
      ) : (
        <Grid container spacing={2}>
          {imageList.map((image) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={image.id || image.db_id}> {/* Use db_id as fallback key */}
              <Card sx={{ height: '100%' }}>
                <CardMedia
                  component="img"
                  height="160"
                  image={image.image_url || 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="160"><rect width="300" height="160" fill="%23f0f0f0"/><text x="150" y="85" text-anchor="middle" fill="%23666" font-family="Arial" font-size="14">No Preview</text></svg>'}
                  alt={image.description || 'Image'}
                  sx={{ objectFit: 'contain' }}
                  onError={(e) => { 
                    // Prevent infinite loop by hiding the image instead of loading another URL
                    e.target.style.display = 'none';
                  }}
                />
                <CardContent>
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {image.description || 'No description'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Uploaded: {image.created_at ? new Date(image.created_at).toLocaleString() : 'N/A'}
                  </Typography>
                   {/* Optional: Add delete button here if needed */}
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  );

  const renderImagesBySet = (imagesBySet) => {
    if (loading) {
      return <CircularProgress />;
    }

    const setNames = Object.keys(imagesBySet);
    if (setNames.length === 0) {
      return <Typography color="textSecondary">No images found.</Typography>;
    }

    return setNames.map((setName) => {
      const images = imagesBySet[setName];
      return (
        <Box key={setName}>
          {renderImageList(`${setName} (${images.length} images)`, images)}
        </Box>
      );
    });
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Paper sx={{ p: 3, mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Image Management
        </Typography>
        
        {/* Upload Section */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="h5" component="h2" gutterBottom>
            Add New Images
          </Typography>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* React Dropzone */}
                <Box 
                  {...getRootProps()} 
                  sx={{
                    border: '2px dashed',
                    borderColor: isDragActive ? 'primary.main' : 'divider',
                    borderRadius: 1,
                    p: 3,
                    bgcolor: isDragActive ? 'action.hover' : 'transparent',
                    textAlign: 'center',
                    cursor: 'pointer',
                    minHeight: 120,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    transition: 'all 0.2s',
                    '&:hover': {
                      borderColor: 'primary.light',
                      bgcolor: 'rgba(0, 0, 0, 0.02)'
                    }
                  }}
                >
                  <input {...getInputProps()} />
                  <CloudUploadIcon fontSize="large" color="primary" sx={{ mb: 1 }} />
                  <Typography variant="body1">
                    {isDragActive 
                      ? 'Drop your images here...' 
                      : 'Drag and drop images here, or click to select files'}
                  </Typography>
                  <Typography variant="caption" color="textSecondary" sx={{ mt: 1 }}>
                    Supported formats: JPG, PNG, GIF, WEBP (Max: 5MB per file)
                  </Typography>
                </Box>
                
                <FormControl fullWidth sx={{ mb: 2 }}>
                  <InputLabel>Select Image Set</InputLabel>
                  <Select
                    value={selectedSet}
                    onChange={handleSetChange}
                    disabled={uploading}
                    label="Select Image Set"
                  >
                    {imageSets.map((set) => (
                      <MenuItem key={set.name} value={set.name}>
                        {set.name} ({set.imageCount} images)
                      </MenuItem>
                    ))}
                    <MenuItem value="CREATE_NEW">
                      <em>Create New Set...</em>
                    </MenuItem>
                  </Select>
                </FormControl>
                
                <Button 
                  variant="contained" 
                  color="primary" 
                  onClick={handleUpload}
                  disabled={selectedFiles.length === 0 || !selectedSet || uploading}
                  startIcon={uploading ? <CircularProgress size={20} /> : null}
                >
                  {uploading 
                    ? `Uploading (${uploadingCount}/${selectedFiles.length})` 
                    : `Upload ${selectedFiles.length} Image${selectedFiles.length !== 1 ? 's' : ''} to ${selectedSet || 'Set'}`}
                </Button>
              </Box>
            </Grid>
            
            <Grid item xs={12} md={6}>
              {selectedFiles.length > 0 && (
                <Box sx={{ height: '100%', overflowY: 'auto' }}>
                  <Typography variant="subtitle1" gutterBottom>
                    Selected Files ({selectedFiles.length}):
                  </Typography>
                  <List dense>
                    {selectedFiles.map((file, index) => (
                      <ListItem 
                        key={file.id || index}
                        sx={{ 
                          display: 'flex', 
                          flexDirection: 'column', 
                          alignItems: 'stretch', 
                          py: 2 
                        }}
                      >
                        <Box sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          width: '100%', 
                          mb: 1
                        }}>
                          <Box sx={{ 
                            width: 60, 
                            height: 60, 
                            mr: 2, 
                            backgroundImage: `url(${file.preview})`,
                            backgroundSize: 'cover',
                            backgroundPosition: 'center',
                            borderRadius: 1,
                            border: '1px solid #ddd'
                          }} />
                          <Box sx={{ flexGrow: 1 }}>
                            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                              {file.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {`${(file.size / 1024).toFixed(1)} KB`}
                            </Typography>
                          </Box>
                          <IconButton 
                            edge="end" 
                            aria-label="delete" 
                            onClick={() => handleRemoveFile(index)}
                            disabled={uploading}
                            sx={{ ml: 1 }}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </Box>
                        <TextField
                          label="Image Label"
                          value={imageLabels[file.id] || ''}
                          onChange={(e) => handleLabelChange(file.id, e.target.value)}
                          disabled={uploading}
                          size="small"
                          fullWidth
                          sx={{ mt: 1 }}
                          helperText="This will be used as the image description"
                        />
                      </ListItem>
                    ))}
                  </List>
                </Box>
              )}
            </Grid>
          </Grid>
        </Box>
        
        <Divider sx={{ my: 4 }} />
        
        {/* Image Gallery Section - Now uses renderImageList */}
        <Paper sx={{ p: 3 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Image Gallery
          </Typography>
          
          {renderImagesBySet(uploadedImages)}
        </Paper>
      </Paper>
      
      {/* New Set Creation Dialog */}
      <Dialog open={showNewSetDialog} onClose={handleCancelNewSet}>
        <DialogTitle>Create New Image Set</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Set Name"
            fullWidth
            variant="outlined"
            value={newSetName}
            onChange={(e) => setNewSetName(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                handleCreateNewSet();
              }
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelNewSet}>Cancel</Button>
          <Button 
            onClick={handleCreateNewSet} 
            variant="contained"
            disabled={!newSetName.trim()}
          >
            Create Set
          </Button>
        </DialogActions>
      </Dialog>
      
      {/* Alert Snackbar */}
      <Snackbar 
        open={alert.open} 
        autoHideDuration={6000} 
        onClose={handleCloseAlert}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseAlert} severity={alert.severity}>
          {alert.message}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default ImageManagementPage; 