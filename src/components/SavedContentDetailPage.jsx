import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  Grid,
  Alert,
  IconButton
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { format } from 'date-fns';
import { apiClient } from '../apiClient';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = 'http://localhost:8000';

const SavedContentDetailPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchSavedContentDetail();
  }, [id]);

  const fetchSavedContentDetail = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.get(`/saved-content/${id}/`);
      setContent(response.data);
    } catch (err) {
      console.error('Error fetching saved content details:', err);
      setError('Failed to load content details. Please try again later.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Paper elevation={2} sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
          <IconButton
            onClick={() => navigate('/saved')}
            sx={{ mr: 2 }}
            aria-label="back"
          >
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h5" component="h1">
            Saved Conversion #{id}
          </Typography>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error" sx={{ my: 2 }}>{error}</Alert>
        ) : content ? (
          <>
            <Box sx={{ mb: 4 }}>
              <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                Created: {format(new Date(content.created_at), 'PPP p')}
              </Typography>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="h6" gutterBottom>
                Easy Read Content
              </Typography>
              
              <List disablePadding>
                {content.easy_read_content.map((item, index) => (
                  <React.Fragment key={index}>
                    <ListItem sx={{ py: 2, alignItems: 'flex-start' }}>
                      <Grid container spacing={2}>
                        {/* Image */}
                        {item.selected_image_path && (
                          <Grid item xs={12} sm={3} md={2}>
                            <Box 
                              component="img"
                              src={`${MEDIA_BASE_URL}/media/${item.selected_image_path}`}
                              alt={`Image for sentence ${index + 1}`}
                              sx={{ 
                                width: '100%', 
                                height: 'auto', 
                                objectFit: 'contain',
                                borderRadius: 1
                              }}
                            />
                          </Grid>
                        )}
                        
                        {/* Sentence */}
                        <Grid item xs={12} sm={item.selected_image_path ? 9 : 12} md={item.selected_image_path ? 10 : 12}>
                          <ListItemText primary={item.sentence} />
                        </Grid>
                      </Grid>
                    </ListItem>
                    {index < content.easy_read_content.length - 1 && <Divider component="li" />}
                  </React.Fragment>
                ))}
              </List>
            </Box>
            
            {content.original_markdown && (
              <Box sx={{ mt: 4 }}>
                <Typography variant="h6" gutterBottom>
                  Original Content
                </Typography>
                <Paper variant="outlined" sx={{ p: 2, bgcolor: 'rgba(0, 0, 0, 0.02)' }}>
                  <Typography 
                    variant="body2" 
                    component="pre" 
                    sx={{ 
                      whiteSpace: 'pre-wrap',
                      fontFamily: 'monospace',
                      fontSize: '0.875rem'
                    }}
                  >
                    {content.original_markdown}
                  </Typography>
                </Paper>
              </Box>
            )}
          </>
        ) : (
          <Alert severity="warning">
            Content not found or has been deleted.
          </Alert>
        )}
      </Paper>
    </Container>
  );
};

export default SavedContentDetailPage; 