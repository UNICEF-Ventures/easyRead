import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  Grid,
  Button,
  IconButton,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Alert,
  Stack,
  Avatar,
  Tooltip,
  Paper,
  Divider,
  Checkbox,
  Snackbar
} from '@mui/material';
import { styled } from '@mui/material/styles';
import DeleteIcon from '@mui/icons-material/Delete';
import FolderIcon from '@mui/icons-material/Folder';
import ImageIcon from '@mui/icons-material/Image';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import WarningIcon from '@mui/icons-material/Warning';
import RefreshIcon from '@mui/icons-material/Refresh';
import SelectAllIcon from '@mui/icons-material/SelectAll';
import CheckIcon from '@mui/icons-material/Check';
import { listImageSets, deleteImageSet } from '../apiClient';
import config from '../config';

const SetCard = styled(Card)(({ theme }) => ({
  height: '100%',
  display: 'flex',
  flexDirection: 'column',
  transition: 'all 0.3s ease',
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: theme.shadows[8],
  }
}));

const PreviewGrid = styled(Box)(({ theme }) => ({
  display: 'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap: theme.spacing(0.5),
  marginTop: theme.spacing(2),
  marginBottom: theme.spacing(2),
}));

const PreviewImage = styled('img')({
  width: '100%',
  height: 80,
  objectFit: 'cover',
  borderRadius: 4,
  border: '1px solid #e0e0e0'
});

const ImageSetManager = ({ onSetDeleted }) => {
  const [sets, setSets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [setToDelete, setSetToDelete] = useState(null);
  const [setsToDelete, setSetsToDelete] = useState([]);
  const [deleting, setDeleting] = useState(false);
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedSets, setSelectedSets] = useState(new Set());
  const [snackbar, setSnackbar] = useState({ open: false, message: '', severity: 'success' });

  const fetchSets = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await listImageSets();
      
      if (response.data.success) {
        setSets(response.data.sets);
      } else {
        setError(response.data.error || 'Failed to fetch image sets');
      }
    } catch (err) {
      console.error('Error fetching image sets:', err);
      setError(err.response?.data?.error || 'Failed to fetch image sets');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSets();
  }, []);

  const handleDeleteClick = (set) => {
    setSetToDelete(set);
    setSetsToDelete([set]);
    setDeleteConfirmOpen(true);
  };

  const handleDeleteSelected = () => {
    const setsToRemove = sets.filter(s => selectedSets.has(s.id));
    setSetsToDelete(setsToRemove);
    setSetToDelete(null);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = async () => {
    const itemsToDelete = setsToDelete.length > 0 ? setsToDelete : (setToDelete ? [setToDelete] : []);
    if (itemsToDelete.length === 0) return;
    
    try {
      setDeleting(true);
      let successCount = 0;
      let failCount = 0;
      const deletedIds = [];
      
      // Delete each set
      for (const set of itemsToDelete) {
        try {
          const response = await deleteImageSet(set.id);
          if (response.data.success) {
            successCount++;
            deletedIds.push(set.id);
            // Notify parent component
            if (onSetDeleted) {
              onSetDeleted(set.id, set.name);
            }
          } else {
            failCount++;
          }
        } catch (err) {
          failCount++;
          console.error(`Error deleting set ${set.name}:`, err);
        }
      }
      
      // Update the sets list by removing deleted ones
      if (successCount > 0) {
        setSets(sets.filter(s => !deletedIds.includes(s.id)));
        setSelectedSets(new Set());
        
        // Show success message
        const message = itemsToDelete.length === 1
          ? `Successfully deleted "${itemsToDelete[0].name}"`
          : `Successfully deleted ${successCount} image set${successCount > 1 ? 's' : ''}`;
        
        setSnackbar({
          open: true,
          message: failCount > 0 ? `${message}, but ${failCount} failed` : message,
          severity: failCount > 0 ? 'warning' : 'success'
        });
      } else {
        setSnackbar({
          open: true,
          message: 'Failed to delete image sets',
          severity: 'error'
        });
      }
      
      setDeleteConfirmOpen(false);
      setSetToDelete(null);
      setSetsToDelete([]);
      
    } catch (err) {
      console.error('Error deleting image sets:', err);
      setSnackbar({
        open: true,
        message: 'Failed to delete image sets',
        severity: 'error'
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleToggleSelection = (setId) => {
    const newSelected = new Set(selectedSets);
    if (newSelected.has(setId)) {
      newSelected.delete(setId);
    } else {
      newSelected.add(setId);
    }
    setSelectedSets(newSelected);
  };

  const handleSelectAll = () => {
    if (selectedSets.size === sets.length) {
      setSelectedSets(new Set());
    } else {
      setSelectedSets(new Set(sets.map(s => s.id)));
    }
  };

  const handleToggleSelectionMode = () => {
    setSelectionMode(!selectionMode);
    if (selectionMode) {
      setSelectedSets(new Set());
    }
  };

  const buildImageUrl = (imageUrl) => {
    if (!imageUrl) return '';
    if (imageUrl.startsWith('http')) return imageUrl;
    return `${config.MEDIA_BASE_URL}${imageUrl}`;
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
        <CircularProgress size={60} />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        {error}
      </Alert>
    );
  }

  if (sets.length === 0) {
    return (
      <Paper sx={{ p: 4, textAlign: 'center' }}>
        <FolderIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
        <Typography variant="h6" color="text.secondary" gutterBottom>
          No Image Sets Found
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Upload images in folders to create image sets
        </Typography>
      </Paper>
    );
  }

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h5" component="h2">
          Image Sets ({sets.length})
        </Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          {selectionMode && selectedSets.size > 0 && (
            <>
              <Button
                size="small"
                variant="outlined"
                startIcon={<SelectAllIcon />}
                onClick={handleSelectAll}
              >
                {selectedSets.size === sets.length ? 'Deselect All' : 'Select All'}
              </Button>
              <Button
                size="small"
                variant="contained"
                color="error"
                startIcon={<DeleteIcon />}
                onClick={handleDeleteSelected}
              >
                Delete ({selectedSets.size})
              </Button>
            </>
          )}
          {selectionMode && selectedSets.size === 0 && (
            <Button
              size="small"
              variant="outlined"
              startIcon={<SelectAllIcon />}
              onClick={handleSelectAll}
            >
              Select All
            </Button>
          )}
          <Button
            variant={selectionMode ? 'contained' : 'outlined'}
            color={selectionMode ? 'secondary' : 'primary'}
            startIcon={selectionMode ? <CheckIcon /> : <DeleteIcon />}
            onClick={handleToggleSelectionMode}
          >
            {selectionMode ? 'Exit Selection' : 'Bulk Delete'}
          </Button>
          <Tooltip title="Refresh">
            <IconButton onClick={fetchSets} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Stack>
      </Box>

      {/* Sets Grid */}
      <Grid container spacing={3}>
        {sets.map((set) => {
          const isSelected = selectedSets.has(set.id);
          
          return (
            <Grid item xs={12} sm={6} md={4} key={set.id}>
              <SetCard
                sx={{
                  border: isSelected ? '3px solid' : '1px solid',
                  borderColor: isSelected ? 'primary.main' : 'divider',
                  backgroundColor: isSelected ? 'rgba(25, 118, 210, 0.04)' : 'inherit'
                }}
              >
                <CardContent sx={{ flexGrow: 1, position: 'relative' }}>
                  {/* Selection Checkbox */}
                  {selectionMode && (
                    <Checkbox
                      checked={isSelected}
                      onChange={() => handleToggleSelection(set.id)}
                      sx={{
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        zIndex: 2,
                        backgroundColor: 'rgba(255,255,255,0.9)',
                        '&:hover': { backgroundColor: 'rgba(255,255,255,0.8)' }
                      }}
                    />
                  )}
                  
                  {/* Set Header */}
                  <Box 
                    sx={{ 
                      display: 'flex', 
                      alignItems: 'flex-start', 
                      mb: 2,
                      cursor: selectionMode ? 'pointer' : 'default'
                    }}
                    onClick={() => selectionMode && handleToggleSelection(set.id)}
                  >
                    <Avatar 
                      sx={{ 
                        bgcolor: isSelected ? 'primary.dark' : 'primary.main', 
                        width: 48, 
                        height: 48,
                        mr: 2
                      }}
                    >
                      <FolderIcon />
                    </Avatar>
                    <Box sx={{ flexGrow: 1 }}>
                      <Typography variant="h6" component="div" noWrap title={set.name}>
                        {set.name}
                      </Typography>
                      {set.description && (
                        <Typography variant="body2" color="text.secondary" noWrap title={set.description}>
                          {set.description}
                        </Typography>
                      )}
                    </Box>
                  </Box>

                {/* Statistics */}
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
                  <Chip
                    icon={<ImageIcon />}
                    label={`${set.image_count} images`}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                  {set.embedding_coverage_percent >= 80 ? (
                    <Chip
                      icon={<CheckCircleIcon />}
                      label={`${set.embedding_coverage_percent}% searchable`}
                      size="small"
                      color="success"
                      variant="outlined"
                    />
                  ) : (
                    <Chip
                      icon={<WarningIcon />}
                      label={`${set.embedding_coverage_percent}% searchable`}
                      size="small"
                      color="warning"
                      variant="outlined"
                    />
                  )}
                </Stack>

                {/* Image Preview Grid */}
                {set.sample_images && set.sample_images.length > 0 && (
                  <PreviewGrid>
                    {set.sample_images.map((img, idx) => (
                      <Tooltip key={img.id} title={img.description || 'No description'} arrow>
                        <PreviewImage
                          src={buildImageUrl(img.url)}
                          alt={img.description || 'Image'}
                          loading="lazy"
                        />
                      </Tooltip>
                    ))}
                  </PreviewGrid>
                )}

                {/* Created Date */}
                <Typography variant="caption" color="text.secondary">
                  Created: {new Date(set.created_at).toLocaleDateString()}
                </Typography>
              </CardContent>

              <Divider />

              <CardActions sx={{ justifyContent: 'space-between', px: 2 }}>
                <Typography variant="body2" color="text.secondary">
                  ID: {set.id}
                </Typography>
                {!selectionMode && (
                  <Button
                    size="small"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={() => handleDeleteClick(set)}
                  >
                    Delete Set
                  </Button>
                )}
                {selectionMode && (
                  <Chip
                    label={isSelected ? 'Selected' : 'Click to select'}
                    color={isSelected ? 'primary' : 'default'}
                    size="small"
                    variant={isSelected ? 'filled' : 'outlined'}
                  />
                )}
              </CardActions>
            </SetCard>
          </Grid>
        );
        })}
      </Grid>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteConfirmOpen}
        onClose={() => !deleting && setDeleteConfirmOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WarningIcon color="error" />
          {setsToDelete.length > 1 ? 'Confirm Delete Multiple Sets' : 'Confirm Delete Image Set'}
        </DialogTitle>
        <DialogContent>
          {setsToDelete.length > 0 ? (
            <Box>
              <Typography paragraph>
                {setsToDelete.length === 1 ? (
                  <>
                    Are you sure you want to delete the image set <strong>"{setsToDelete[0].name}"</strong>?
                  </>
                ) : (
                  <>
                    Are you sure you want to delete <strong>{setsToDelete.length} image sets</strong>?
                  </>
                )}
              </Typography>
              <Alert severity="warning" sx={{ mb: 2 }}>
                This will permanently delete{' '}
                <strong>
                  {setsToDelete.reduce((sum, s) => sum + s.image_count, 0)} images
                </strong>{' '}
                in total. This action cannot be undone.
              </Alert>
              
              {setsToDelete.length === 1 ? (
                <Stack spacing={1}>
                  <Typography variant="body2" color="text.secondary">
                    • Set name: {setsToDelete[0].name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    • Images: {setsToDelete[0].image_count}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    • Searchable images: {setsToDelete[0].images_with_embeddings}
                  </Typography>
                </Stack>
              ) : (
                <Box>
                  <Typography variant="subtitle2" gutterBottom>
                    Sets to be deleted:
                  </Typography>
                  <Stack spacing={0.5} sx={{ maxHeight: 200, overflowY: 'auto' }}>
                    {setsToDelete.map((set) => (
                      <Paper key={set.id} variant="outlined" sx={{ p: 1 }}>
                        <Typography variant="body2">
                          <strong>{set.name}</strong> - {set.image_count} images
                        </Typography>
                      </Paper>
                    ))}
                  </Stack>
                </Box>
              )}
            </Box>
          ) : setToDelete && (
            <Box>
              <Typography paragraph>
                Are you sure you want to delete the image set <strong>"{setToDelete.name}"</strong>?
              </Typography>
              <Alert severity="warning" sx={{ mb: 2 }}>
                This will permanently delete <strong>{setToDelete.image_count} images</strong> from this set.
                This action cannot be undone.
              </Alert>
              <Stack spacing={1}>
                <Typography variant="body2" color="text.secondary">
                  • Set name: {setToDelete.name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • Images: {setToDelete.image_count}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  • Searchable images: {setToDelete.images_with_embeddings}
                </Typography>
              </Stack>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirmOpen(false)} disabled={deleting}>
            Cancel
          </Button>
          <Button
            onClick={handleConfirmDelete}
            color="error"
            variant="contained"
            startIcon={deleting ? <CircularProgress size={16} /> : <DeleteIcon />}
            disabled={deleting}
          >
            {deleting ? 'Deleting...' : setsToDelete.length > 1 ? `Delete ${setsToDelete.length} Sets` : 'Delete Set'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Success/Error Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ImageSetManager;

