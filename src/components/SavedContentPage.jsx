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
  Grid,
  Alert
} from '@mui/material';
import { format } from 'date-fns';
import { getSavedContent } from '../apiClient';

// Base URL for serving media files from Django dev server
const MEDIA_BASE_URL = 'http://localhost:8000';

const SavedContentPage = () => {
  const [savedContent, setSavedContent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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
                    transition: 'transform 0.2s, box-shadow 0.2s',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 4,
                      cursor: 'pointer'
                    }
                  }}
                  onClick={() => handleViewContent(item.id)}
                >
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Typography variant="h6" component="h2" gutterBottom noWrap>
                      Conversion #{item.id}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Created: {format(new Date(item.created_at), 'PPP p')}
                    </Typography>
                    <Typography variant="body2" sx={{ mt: 1 }}>
                      {item.sentence_count} sentences
                    </Typography>
                    
                    {item.preview_image && (
                      <Box 
                        component="img" 
                        src={`${MEDIA_BASE_URL}/media/${item.preview_image}`}
                        alt="Preview"
                        sx={{ 
                          mt: 2, 
                          width: '100%', 
                          height: 120, 
                          objectFit: 'contain',
                          borderRadius: 1,
                          bgcolor: 'rgba(0, 0, 0, 0.03)'
                        }}
                      />
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Paper>
    </Container>
  );
};

export default SavedContentPage; 