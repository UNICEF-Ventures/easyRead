import React from 'react';
import { Box, Typography, Container, Button, Paper } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import logo from '../assets/logo.png';

function IntroPage() {
  const navigate = useNavigate();

  const handleContinue = () => {
    navigate('/easyread/convert');
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        bgcolor: '#f5f7fa',
        py: 4,
      }}
    >
      <Container maxWidth="md">
        <Paper
          elevation={3}
          sx={{
            p: 6,
            textAlign: 'center',
            borderRadius: 3,
            bgcolor: 'white',
          }}
        >
          {/* Logo */}
          <Box sx={{ mb: 4 }}>
            <img 
              src={logo} 
              alt="EasyRead Logo" 
              style={{
                maxWidth: '400px',
                height: 'auto',
                maxHeight: '220px',
                objectFit: 'contain'
              }}
            />
          </Box>

          {/* Description */}
          <Typography
            variant="h6"
            component="div"
            sx={{
              mb: 4,
              color: '#333',
              lineHeight: 1.6,
              fontWeight: 300,
            }}
          >
            <p><strong>Easy Read</strong> is a way of writing that makes information easier to understand for people who may find standard text difficult. It uses short sentences, simple words, and supportive images to explain ideas step by step. The focus is on clarity and inclusion, so that everyone can access and engage with important information.</p>
            <br />
            <p>The EasyRead prototype from UNICEF’s Office of Innovation applies this approach with the help of AI. It automatically transforms complex documents—like policies, reports, or guides—into Easy Read format, simplifying language and restructuring content to improve accessibility. The aim is to ensure that vital information is available to all, regardless of reading ability or background.</p>
          </Typography>

          {/* Disclaimers */}
          <Typography
            variant="body2"
            sx={{
              mb: 6,
              color: '#666',
              lineHeight: 1.7,
              textAlign: 'left',
              maxWidth: '600px',
              mx: 'auto',
            }}
          >
            <strong>Please note:</strong> This prototype is provided for exploration and testing purposes only and is not intended for use in UNICEF programs or by program partners. It uses artificial intelligence to simplify text and suggest images. While we strive for accuracy, all content should be carefully reviewed before use. The generated output must be verified for appropriateness and accuracy in your specific context. 
          </Typography>

          {/* Continue Button */}
          <Button
            variant="contained"
            size="large"
            onClick={handleContinue}
            sx={{
              px: 6,
              py: 2,
              fontSize: '1.2rem',
              borderRadius: 2,
              textTransform: 'none',
              fontWeight: 'bold',
              boxShadow: 3,
              '&:hover': {
                transform: 'translateY(-2px)',
                boxShadow: 6,
              },
              transition: 'all 0.3s ease',
            }}
          >
            Continue
          </Button>
        </Paper>
      </Container>
    </Box>
  );
}

export default IntroPage;