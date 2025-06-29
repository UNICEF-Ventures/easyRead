import React, { useState, useEffect } from 'react';
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
  IconButton
} from '@mui/material';
import { styled } from '@mui/material/styles';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import DeleteIcon from '@mui/icons-material/Delete';
import { listImages, uploadImage, batchUploadImages } from '../apiClient';

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
  const [uploadedImages, setUploadedImages] = useState([]);
  const [generatedImages, setGeneratedImages] = useState([]);
  
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadingCount, setUploadingCount] = useState(0);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [description, setDescription] = useState('');
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

  // Fetch all images on component mount
  useEffect(() => {
    fetchImages();
  }, []);

  const fetchImages = async () => {
    setLoading(true);
    try {
      const response = await listImages();
      // Set state based on the new API response structure
      setUploadedImages(response.data.uploaded_images || []);
      setGeneratedImages(response.data.generated_images || []); 
    } catch (error) {
      console.error('Error fetching images:', error);
      showAlert('Error loading images', 'error');
      setUploadedImages([]); // Clear on error
      setGeneratedImages([]); // Clear on error
    } finally {
      setLoading(false);
    }
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

    // Create preview URLs for valid files
    const filesWithPreviews = validFiles.map(file => Object.assign(file, {
      preview: URL.createObjectURL(file)
    }));

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
      // Revoke the URL to prevent memory leaks
      if (newFiles[index].preview) {
        URL.revokeObjectURL(newFiles[index].preview);
      }
      newFiles.splice(index, 1);
      return newFiles;
    });
  };

  const handleDescriptionChange = (event) => {
    setDescription(event.target.value);
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      showAlert('Please select at least one file', 'warning');
      return;
    }

    setUploading(true);
    setUploadingCount(0);
    
    try {
      // If only one file, use single upload
      if (selectedFiles.length === 1) {
        await uploadImage(selectedFiles[0], description);
        setUploadingCount(1);
      } else {
        // For multiple files, use batch upload
        await batchUploadImages(selectedFiles, description);
        setUploadingCount(selectedFiles.length);
      }
      
      showAlert(`Successfully uploaded ${selectedFiles.length} image(s)`, 'success');
      
      // Reset form
      selectedFiles.forEach(file => {
        if (file.preview) URL.revokeObjectURL(file.preview);
      });
      setSelectedFiles([]);
      setDescription('');
      
      // Refresh image list
      fetchImages();
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
      <Typography variant="h5" component="h2" gutterBottom>
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
                  image={image.image_url || 'https://via.placeholder.com/300x160?text=No+Preview'}
                  alt={image.description || 'Image'}
                  sx={{ objectFit: 'contain' }}
                  onError={(e) => { e.target.src = 'https://via.placeholder.com/300x160?text=Error'; }}
                />
                <CardContent>
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {image.description || 'No description'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    Uploaded: {image.uploaded_at ? new Date(image.uploaded_at).toLocaleString() : 'N/A'}
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
                
                <TextField
                  fullWidth
                  label="Image Description (applies to all uploads)"
                  variant="outlined"
                  value={description}
                  onChange={handleDescriptionChange}
                  disabled={uploading}
                  multiline
                  rows={3}
                />
                
                <Button 
                  variant="contained" 
                  color="primary" 
                  onClick={handleUpload}
                  disabled={selectedFiles.length === 0 || uploading}
                  startIcon={uploading ? <CircularProgress size={20} /> : null}
                >
                  {uploading 
                    ? `Uploading (${uploadingCount}/${selectedFiles.length})` 
                    : `Upload ${selectedFiles.length} Image${selectedFiles.length !== 1 ? 's' : ''}`}
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
                        key={index}
                        secondaryAction={
                          <IconButton 
                            edge="end" 
                            aria-label="delete" 
                            onClick={() => handleRemoveFile(index)}
                            disabled={uploading}
                          >
                            <DeleteIcon />
                          </IconButton>
                        }
                      >
                        <Box sx={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          width: '100%', 
                          pr: 2
                        }}>
                          <Box sx={{ 
                            width: 40, 
                            height: 40, 
                            mr: 2, 
                            backgroundImage: `url(${file.preview})`,
                            backgroundSize: 'cover',
                            backgroundPosition: 'center',
                            borderRadius: 1
                          }} />
                          <ListItemText 
                            primary={file.name} 
                            secondary={`${(file.size / 1024).toFixed(1)} KB`} 
                            sx={{ 
                              overflow: 'hidden',
                              '& .MuiListItemText-primary': {
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis'
                              }
                            }}
                          />
                        </Box>
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
          
          {renderImageList("Generated Images", generatedImages)}
          
          <Divider sx={{ my: 4 }} />
          
          {renderImageList("Uploaded Images", uploadedImages)}
        </Paper>
      </Paper>
      
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