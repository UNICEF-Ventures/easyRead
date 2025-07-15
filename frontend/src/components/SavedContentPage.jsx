import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Container,
  Paper,
  List,
  ListItem,
  ListItemText,
  Divider,
  CircularProgress,
  Button,
  Card,
  CardContent,
  CardActions,
  Grid,
  Alert,
  IconButton,
  Snackbar
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import { format } from 'date-fns';
import { getSavedContent, deleteSavedContent } from '../apiClient';
import { config } from '../config.js';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = config.MEDIA_BASE_URL;

const SavedContentPage = () => {
  const [savedContent, setSavedContent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [deleteFeedback, setDeleteFeedback] = useState({ open: false, message: '', severity: 'success' });
  const navigate = useNavigate();

  useEffect(() => {
    fetchSavedContent();
  }, []);

  const fetchSavedContent = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getSavedContent();
      setSavedContent(response.data.content || []);
    } catch (err) {
      console.error('Error fetching saved content:', err);
      setError('Failed to load saved content. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  const handleViewContent = (id) => {
    navigate(`/saved/${id}`);
  };

  const handleDeleteContent = async (id, event) => {
    event.stopPropagation();
    
    if (!window.confirm('Are you sure you want to delete this item?')) {
        return;
    }

    try {
      await deleteSavedContent(id);
      setSavedContent(prevContent => prevContent.filter(item => item.id !== id));
      setDeleteFeedback({ open: true, message: 'Content deleted successfully', severity: 'success' });
    } catch (err) {
      console.error('Error deleting content:', err);
      setDeleteFeedback({ open: true, message: 'Failed to delete content', severity: 'error' });
    }
  };

  const handleCloseSnackbar = (event, reason) => {
    if (reason === 'clickaway') {
      return;
    }
    setDeleteFeedback(prev => ({ ...prev, open: false }));
  };

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={2} sx={{ p: 3 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Saved Easy Read Conversions
        </Typography>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>
        ) : savedContent.length === 0 ? (
          <Box sx={{ textAlign: 'center', my: 4 }}>
            <Typography variant="body1" color="text.secondary">
              No saved conversions found. 
            </Typography>
            <Button 
              variant="contained" 
              color="primary" 
              sx={{ mt: 2 }}
              onClick={() => navigate('/')}
            >
              Create a new conversion
            </Button>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {savedContent.map((item) => (
              <Grid item xs={12} sm={6} md={4} key={item.id}>
                <Card 
                  sx={{ 
                    height: '100%', 
                    display: 'flex', 
                    flexDirection: 'column',
                  }}
                >
                  <CardContent sx={{ flexGrow: 1 }} onClick={() => handleViewContent(item.id)} style={{cursor: 'pointer'}}>
                    <Typography variant="h6" component="h2" gutterBottom noWrap>
                      {item.title || `Conversion #${item.id}`}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Created: {format(new Date(item.created_at), 'PPP p')}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {item.sentence_count} sentences
                    </Typography>
                  </CardContent>
                  <CardActions sx={{ justifyContent: 'flex-end', pt: 0 }}>
                    <IconButton 
                      aria-label="delete"
                      onClick={(e) => handleDeleteContent(item.id, e)}
                      color="error"
                      size="small"
                    >
                      <DeleteIcon fontSize="small"/>
                    </IconButton>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Paper>
      <Snackbar 
        open={deleteFeedback.open} 
        autoHideDuration={4000} 
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity={deleteFeedback.severity} sx={{ width: '100%' }}>
          {deleteFeedback.message}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default SavedContentPage; 