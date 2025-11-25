import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  LinearProgress,
  Card,
  CardContent,
  Chip,
  Stack,
  Divider
} from '@mui/material';
import {
  CloudUpload as CloudUploadIcon,
  CheckCircle as CheckCircleIcon,
  Error as ErrorIcon,
  Cancel as CancelIcon
} from '@mui/icons-material';
import { getUploadProgress } from '../apiClient';

const UploadProgressDialog = ({ 
  open, 
  onClose, 
  sessionId, 
  onComplete 
}) => {
  const [progress, setProgress] = useState(null);
  const [isCompleted, setIsCompleted] = useState(false);
  const [intervalId, setIntervalId] = useState(null);

  // Poll for progress updates
  useEffect(() => {
    if (open && sessionId && !isCompleted) {
      const pollProgress = async () => {
        try {
          const response = await getUploadProgress(sessionId);
          const progressData = response.data.progress;
          setProgress(progressData);

          // Check if upload is completed
          if (progressData.status === 'completed' || progressData.status === 'failed') {
            setIsCompleted(true);
            if (intervalId) {
              clearInterval(intervalId);
              setIntervalId(null);
            }
            if (onComplete) {
              onComplete(progressData);
            }
          }
        } catch (error) {
          console.error('Error fetching upload progress:', error);
          // Continue polling on error - might be temporary
        }
      };

      // Initial poll
      pollProgress();

      // Set up polling interval
      const id = setInterval(pollProgress, 2000); // Poll every 2 seconds
      setIntervalId(id);

      return () => {
        if (id) clearInterval(id);
      };
    }
  }, [open, sessionId, isCompleted, onComplete, intervalId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [intervalId]);

  const handleClose = () => {
    if (intervalId) {
      clearInterval(intervalId);
      setIntervalId(null);
    }
    setProgress(null);
    setIsCompleted(false);
    onClose();
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'processing': return 'primary';
      default: return 'default';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircleIcon />;
      case 'failed': return <ErrorIcon />;
      case 'processing': return <CloudUploadIcon />;
      default: return <CloudUploadIcon />;
    }
  };

  if (!progress) {
    return (
      <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
        <DialogTitle>Upload Progress</DialogTitle>
        <DialogContent>
          <Box display="flex" flexDirection="column" alignItems="center" py={3}>
            <CloudUploadIcon sx={{ fontSize: 48, mb: 2, color: 'primary.main' }} />
            <Typography>Initializing upload...</Typography>
            <LinearProgress sx={{ width: '100%', mt: 2 }} />
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  const progressPercentage = Math.min(progress.percentage || 0, 100);
  const isUploadActive = progress.status === 'processing' || progress.status === 'starting';

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={2}>
          {getStatusIcon(progress.status)}
          <Typography variant="h6">
            Batch Upload Progress
          </Typography>
          <Chip 
            label={progress.status.toUpperCase()} 
            color={getStatusColor(progress.status)}
            size="small"
          />
        </Stack>
      </DialogTitle>
      
      <DialogContent>
        <Card variant="outlined">
          <CardContent>
            {/* Overall Progress */}
            <Box mb={3}>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
                <Typography variant="body1" fontWeight="bold">
                  Overall Progress
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {progressPercentage.toFixed(1)}%
                </Typography>
              </Stack>
              
              <LinearProgress 
                variant="determinate" 
                value={progressPercentage}
                sx={{ height: 8, borderRadius: 4 }}
                color={progress.status === 'failed' ? 'error' : 'primary'}
              />
              
              <Stack direction="row" justifyContent="space-between" mt={1}>
                <Typography variant="body2" color="text.secondary">
                  {progress.processed} / {progress.total_images} images processed
                </Typography>
                {isUploadActive && (
                  <Typography variant="body2" color="primary">
                    Batch {progress.current_batch} processing...
                  </Typography>
                )}
              </Stack>
            </Box>

            <Divider />

            {/* Statistics */}
            <Box mt={3}>
              <Stack direction="row" spacing={2} flexWrap="wrap">
                <Chip
                  icon={<CheckCircleIcon />}
                  label={`${progress.successful} Successful`}
                  color="success"
                  variant="outlined"
                  size="small"
                />
                <Chip
                  icon={<ErrorIcon />}
                  label={`${progress.failed} Failed`}
                  color="error"
                  variant="outlined"
                  size="small"
                />
                <Chip
                  label={`${progress.total_images} Total`}
                  variant="outlined"
                  size="small"
                />
                <Chip
                  label={`Batch ${progress.current_batch}`}
                  color="primary"
                  variant="outlined"
                  size="small"
                />
              </Stack>
            </Box>

            {/* Status Messages */}
            {progress.status === 'completed' && (
              <Box mt={2}>
                <Typography variant="body2" color="success.main">
                  ✅ Upload completed successfully!
                </Typography>
              </Box>
            )}

            {progress.status === 'failed' && (
              <Box mt={2}>
                <Typography variant="body2" color="error.main">
                  ❌ Upload failed. Check the logs for details.
                </Typography>
              </Box>
            )}

            {isUploadActive && (
              <Box mt={2}>
                <Typography variant="body2" color="primary">
                  🔄 Processing images in optimized batches for better performance...
                </Typography>
              </Box>
            )}
          </CardContent>
        </Card>
      </DialogContent>

      <DialogActions>
        {!isUploadActive && (
          <Button onClick={handleClose} variant="contained">
            Close
          </Button>
        )}
        {isUploadActive && (
          <Button 
            onClick={handleClose} 
            variant="outlined"
            startIcon={<CancelIcon />}
          >
            Close (Background Upload)
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
};

export default UploadProgressDialog;