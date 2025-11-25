import React, { useState, useEffect } from 'react';
import { Box, CircularProgress, Typography, Button, Tabs, Tab } from '@mui/material';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AdminLogin from './AdminLogin';
import ImageManagementPage from './ImageManagementPage';
import AdminDashboard from './AdminDashboard';
import ImageSetManager from './ImageSetManager';
import LogoutIcon from '@mui/icons-material/Logout';
import DashboardIcon from '@mui/icons-material/Dashboard';
import ImageIcon from '@mui/icons-material/Image';
import FolderIcon from '@mui/icons-material/Folder';
import apiClient from '../apiClient';

const AdminRoute = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [username, setUsername] = useState('');
  const [currentTab, setCurrentTab] = useState(0);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Check authentication status on component mount
  useEffect(() => {
    checkAuthStatus();
    // Set initial tab from URL params
    const tab = searchParams.get('tab');
    if (tab === 'dashboard') {
      setCurrentTab(0);
    } else if (tab === 'images') {
      setCurrentTab(1);
    } else if (tab === 'sets') {
      setCurrentTab(2);
    }
  }, [searchParams]);

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

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
    const tabNames = ['dashboard', 'images', 'sets'];
    setSearchParams({ tab: tabNames[newValue] });
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
          Admin Panel
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
          Logout ({username})
        </Button>
      </Box>

      <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tabs value={currentTab} onChange={handleTabChange} aria-label="admin tabs">
          <Tab 
            icon={<DashboardIcon />} 
            label="Analytics Dashboard" 
            id="tab-0" 
            aria-controls="tabpanel-0"
          />
          <Tab 
            icon={<ImageIcon />} 
            label="Image Management" 
            id="tab-1" 
            aria-controls="tabpanel-1"
          />
          <Tab 
            icon={<FolderIcon />} 
            label="Image Sets" 
            id="tab-2" 
            aria-controls="tabpanel-2"
          />
        </Tabs>
      </Box>

      <Box sx={{ mt: 2 }}>
        {currentTab === 0 && (
          <Box role="tabpanel" id="tabpanel-0" aria-labelledby="tab-0">
            <AdminDashboard />
          </Box>
        )}
        {currentTab === 1 && (
          <Box role="tabpanel" id="tabpanel-1" aria-labelledby="tab-1">
            <ImageManagementPage />
          </Box>
        )}
        {currentTab === 2 && (
          <Box role="tabpanel" id="tabpanel-2" aria-labelledby="tab-2" sx={{ px: 2 }}>
            <ImageSetManager 
              onSetDeleted={(setId, setName) => {
                console.log(`Image set "${setName}" (ID: ${setId}) was deleted`);
              }}
            />
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default AdminRoute;