import React, { useState, useEffect } from 'react';
import { Box, CircularProgress, Typography, Button } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import AdminLogin from './AdminLogin';
import ImageManagementPage from './ImageManagementPage';
import LogoutIcon from '@mui/icons-material/Logout';
import apiClient from '../apiClient';

const AdminRoute = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [username, setUsername] = useState('');
  const navigate = useNavigate();

  // Check authentication status on component mount
  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await apiClient.get('/admin/check-auth/', {
        withCredentials: true,
      });
      const data = response.data;
      
      console.log('Auth check response:', data);
      
      setIsAuthenticated(data.authenticated);
      setUsername(data.username || '');
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoginSuccess = (username) => {
    setIsAuthenticated(true);
    setUsername(username);
  };

  const handleLogout = async () => {
    try {
      const response = await apiClient.post('/admin/api/logout/', {}, {
        withCredentials: true,
      });
      
      if (response.status === 200) {
        setIsAuthenticated(false);
        setUsername('');
        // Optionally redirect to home page
        navigate('/');
      }
    } catch (error) {
      console.error('Logout failed:', error);
      // Force logout on frontend even if backend call fails
      setIsAuthenticated(false);
      setUsername('');
      navigate('/');
    }
  };


  console.log('AdminRoute render - isLoading:', isLoading, 'isAuthenticated:', isAuthenticated);

  if (isLoading) {
    console.log('Rendering loading state');
    return (
      <Box 
        display="flex" 
        justifyContent="center" 
        alignItems="center" 
        minHeight="400px"
        flexDirection="column"
      >
        <CircularProgress size={40} />
        <Typography variant="body1" sx={{ mt: 2 }}>
          Checking authentication...
        </Typography>
      </Box>
    );
  }

  if (!isAuthenticated) {
    console.log('Rendering login form');
    return <AdminLogin onLoginSuccess={handleLoginSuccess} />;
  }

  console.log('Rendering authenticated admin interface');

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, px: 2 }}>
        <Typography variant="h4" component="h1">
          Image Management
        </Typography>
        <Button
          variant="outlined"
          onClick={handleLogout}
          startIcon={<LogoutIcon />}
          sx={{
            borderColor: '#667eea',
            color: '#667eea',
            '&:hover': {
              backgroundColor: 'rgba(102, 126, 234, 0.1)',
              borderColor: '#5a6fd8',
            }
          }}
        >
          Logout
        </Button>
      </Box>
      <ImageManagementPage />
    </Box>
  );
};

export default AdminRoute;