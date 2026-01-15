import React, { useState } from 'react';
import {
  Box,
  Container,
  Paper,
  Typography,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Stepper,
  Step,
  StepLabel,
} from '@mui/material';
import EmailIcon from '@mui/icons-material/Email';
import LockIcon from '@mui/icons-material/Lock';
import LoginIcon from '@mui/icons-material/Login';
import { requestOTP, verifyOTP } from '../apiClient';
import { useAuth } from '../contexts/AuthContext';
import { config } from '../config';

const steps = ['Enter Email', 'Enter Code'];

function LoginPage() {
  const { login, loginWithOAuth, error: authError, authMethod } = useAuth();
  const [activeStep, setActiveStep] = useState(0);
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  // Show auth error (e.g., session expired) if present
  const displayError = error || authError;

  const handleRequestOTP = async (e) => {
    e.preventDefault();
    if (!email.trim()) {
      setError('Please enter your email address');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await requestOTP(email.trim().toLowerCase());
      setMessage(response.data.message);
      setActiveStep(1);
    } catch (err) {
      console.error('OTP request failed:', err);
      setError(err.response?.data?.error || 'Failed to send login code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async (e) => {
    e.preventDefault();
    if (!otp.trim()) {
      setError('Please enter the 6-digit code');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await verifyOTP(email.trim().toLowerCase(), otp.trim());
      login(response.data.email);
    } catch (err) {
      console.error('OTP verification failed:', err);
      setError(err.response?.data?.error || 'Invalid code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    setActiveStep(0);
    setOtp('');
    setError('');
    setMessage('');
  };

  const handleResendOTP = async () => {
    setLoading(true);
    setError('');

    try {
      await requestOTP(email.trim().toLowerCase());
      setMessage('A new code has been sent to your email.');
      setOtp('');
    } catch (err) {
      setError('Failed to resend code. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthLogin = () => {
    setLoading(true);
    loginWithOAuth();
    // Note: This will redirect, so loading state won't matter
  };

  // OAuth Login UI
  if (authMethod === 'oauth') {
    return (
      <Container maxWidth="sm">
        <Box
          sx={{
            minHeight: '100vh',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            py: 4,
          }}
        >
          <Paper elevation={3} sx={{ p: 4, borderRadius: 2 }}>
            {/* Header */}
            <Box sx={{ textAlign: 'center', mb: 4 }}>
              <Typography variant="h4" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
                EasyRead
              </Typography>
              <Typography variant="body1" color="text.secondary">
                Sign in with your OOI Playground account
              </Typography>
            </Box>

            {/* Error Display */}
            {displayError && (
              <Alert severity="error" sx={{ mb: 3 }}>
                {displayError}
              </Alert>
            )}

            {/* OAuth Login Button */}
            <Button
              fullWidth
              variant="contained"
              size="large"
              onClick={handleOAuthLogin}
              disabled={loading}
              startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <LoginIcon />}
              sx={{ py: 1.5, fontSize: '1rem' }}
            >
              {loading ? 'Redirecting...' : 'Sign in with Playground'}
            </Button>

            {/* Footer */}
            <Box sx={{ mt: 4, textAlign: 'center' }}>
              <Typography variant="caption" color="text.secondary">
                You will be redirected to the OOI Playground login page.
                <br />
                After signing in, you will be returned to EasyRead.
              </Typography>
            </Box>
          </Paper>
        </Box>
      </Container>
    );
  }

  // OTP Login UI (default)
  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          py: 4,
        }}
      >
        <Paper elevation={3} sx={{ p: 4, borderRadius: 2 }}>
          {/* Header */}
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Typography variant="h4" component="h1" gutterBottom sx={{ fontWeight: 600 }}>
              EasyRead
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Sign in with your email
            </Typography>
          </Box>

          {/* Stepper */}
          <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>

          {/* Error/Message Display */}
          {displayError && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {displayError}
            </Alert>
          )}
          {message && !displayError && (
            <Alert severity="success" sx={{ mb: 2 }}>
              {message}
            </Alert>
          )}

          {/* Step 1: Email Input */}
          {activeStep === 0 && (
            <form onSubmit={handleRequestOTP}>
              <Alert severity="info" sx={{ mb: 2, fontSize: '0.875rem' }}>
                The login code will be sent from <strong>noreply@ooi.ventures</strong>.
                Please check your spam folder if you don't receive it.
              </Alert>
              <TextField
                fullWidth
                label="Email Address"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={loading}
                autoFocus
                InputProps={{
                  startAdornment: <EmailIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
                sx={{ mb: 3 }}
              />
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading || !email.trim()}
                sx={{ py: 1.5 }}
              >
                {loading ? (
                  <CircularProgress size={24} color="inherit" />
                ) : (
                  'Send Login Code'
                )}
              </Button>
            </form>
          )}

          {/* Step 2: OTP Input */}
          {activeStep === 1 && (
            <form onSubmit={handleVerifyOTP}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2, textAlign: 'center' }}>
                We sent a 6-digit code to <strong>{email}</strong>
              </Typography>
              <TextField
                fullWidth
                label="Login Code"
                value={otp}
                onChange={(e) => {
                  // Only allow digits, max 6 characters
                  const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                  setOtp(value);
                }}
                placeholder="000000"
                disabled={loading}
                autoFocus
                inputProps={{
                  maxLength: 6,
                  style: { textAlign: 'center', letterSpacing: '0.5em', fontSize: '1.5rem' },
                }}
                InputProps={{
                  startAdornment: <LockIcon sx={{ mr: 1, color: 'text.secondary' }} />,
                }}
                sx={{ mb: 3 }}
              />
              <Button
                type="submit"
                fullWidth
                variant="contained"
                size="large"
                disabled={loading || otp.length !== 6}
                sx={{ py: 1.5, mb: 2 }}
              >
                {loading ? (
                  <CircularProgress size={24} color="inherit" />
                ) : (
                  'Verify & Sign In'
                )}
              </Button>
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Button onClick={handleBack} disabled={loading}>
                  Back
                </Button>
                <Button onClick={handleResendOTP} disabled={loading}>
                  Resend Code
                </Button>
              </Box>
            </form>
          )}

          {/* Footer */}
          <Box sx={{ mt: 4, textAlign: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              Only whitelisted email addresses can sign in.
              <br />
              Contact your administrator if you need access.
            </Typography>
          </Box>
        </Paper>
      </Box>
    </Container>
  );
}

export default LoginPage;
