import React from 'react';
import { Box, CircularProgress, Typography, Backdrop } from '@mui/material';
import { styled } from '@mui/material/styles';

const StyledBackdrop = styled(Backdrop)(({ theme }) => ({
  zIndex: theme.zIndex.modal + 1,
  backdropFilter: 'blur(8px)',
  backgroundColor: 'rgba(0, 0, 0, 0.5)',
}));

const LoadingContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: theme.spacing(3),
  padding: theme.spacing(4),
  backgroundColor: 'white',
  borderRadius: theme.shape.borderRadius * 2,
  boxShadow: theme.shadows[10],
}));

/**
 * LoadingOverlay Component
 *
 * Displays a full-screen loading overlay with a blur effect, spinner, and progress message
 *
 * @param {boolean} open - Controls visibility of the overlay
 * @param {string} message - Progress message to display
 */
const LoadingOverlay = ({ open, message }) => {
  return (
    <StyledBackdrop open={open}>
      <LoadingContainer>
        <CircularProgress size={60} thickness={4} />
        <Typography
          variant="h6"
          component="div"
          sx={{
            color: 'text.primary',
            textAlign: 'center',
            fontWeight: 500,
          }}
        >
          {message || 'Processing...'}
        </Typography>
      </LoadingContainer>
    </StyledBackdrop>
  );
};

export default LoadingOverlay;
