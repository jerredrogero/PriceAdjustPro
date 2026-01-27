import React, { useState } from 'react';
import { useLocation, Link, useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Paper,
  Alert,
  Button,
  CircularProgress,
  TextField,
} from '@mui/material';
import EmailIcon from '@mui/icons-material/Email';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import axios from 'axios';

const VerificationPending: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const email = location.state?.email || '';
  const username = location.state?.username || '';
  
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [verifyMessage, setVerifyMessage] = useState('');
  
  const [resending, setResending] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [resendMessage, setResendMessage] = useState('');

  const handleVerifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!code || code.length !== 6) {
      setVerifyStatus('error');
      setVerifyMessage('Please enter a valid 6-digit code');
      return;
    }

    setVerifying(true);
    setVerifyStatus('idle');

    try {
      const response = await axios.post('/api/auth/verify-code/', {
        username,
        email,
        code,
      });
      
      setVerifyStatus('success');
      setVerifyMessage(response.data.message || 'Email verified successfully!');
      
      // Redirect to login after 2 seconds
      setTimeout(() => {
        navigate('/login', { state: { verified: true, username: response.data.username } });
      }, 2000);
    } catch (error: any) {
      setVerifyStatus('error');
      if (error.response?.data?.error) {
        setVerifyMessage(error.response.data.error);
      } else {
        setVerifyMessage('Failed to verify code. Please try again.');
      }
    } finally {
      setVerifying(false);
    }
  };

  const handleResendEmail = async () => {
    if (!email) {
      setResendStatus('error');
      setResendMessage('Email address not found. Please register again.');
      return;
    }

    setResending(true);
    setResendStatus('idle');

    try {
      const response = await axios.post('/api/auth/resend-verification/', { email });
      setResendStatus('success');
      setResendMessage(response.data.message || 'Verification code sent!');
    } catch (error: any) {
      setResendStatus('error');
      if (error.response?.data?.error) {
        setResendMessage(error.response.data.error);
      } else {
        setResendMessage('Failed to resend code. Please try again later.');
      }
    } finally {
      setResending(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
          {verifyStatus === 'success' ? (
            <>
              <CheckCircleIcon sx={{ fontSize: 80, color: 'success.main', mb: 2 }} />
              <Typography variant="h4" gutterBottom color="success.main">
                Email Verified!
              </Typography>
              <Alert severity="success" sx={{ mb: 2 }}>
                {verifyMessage}
              </Alert>
              <Typography variant="body2" color="text.secondary">
                Logging in...
              </Typography>
            </>
          ) : (
            <>
              <EmailIcon sx={{ fontSize: 80, color: 'primary.main', mb: 2 }} />
              
              <Typography variant="h4" gutterBottom>
                Enter Verification Code
              </Typography>

              <Typography variant="body1" color="text.secondary" sx={{ mb: 1 }}>
                We've sent a 6-digit code to:
              </Typography>

              <Typography variant="h6" color="primary" sx={{ mb: 3 }}>
                {email || 'your email address'}
              </Typography>

              {verifyStatus === 'error' && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {verifyMessage}
                </Alert>
              )}

              {resendStatus === 'success' && (
                <Alert severity="success" sx={{ mb: 2 }}>
                  {resendMessage}
                </Alert>
              )}

              {resendStatus === 'error' && (
                <Alert severity="error" sx={{ mb: 2 }}>
                  {resendMessage}
                </Alert>
              )}

              <Box component="form" onSubmit={handleVerifyCode} sx={{ mb: 3 }}>
                <TextField
                  fullWidth
                  label="Verification Code"
                  value={code}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                    setCode(value);
                  }}
                  placeholder="000000"
                  inputProps={{
                    maxLength: 6,
                    style: { textAlign: 'center', fontSize: '24px', letterSpacing: '8px' }
                  }}
                  sx={{ mb: 2 }}
                  autoFocus
                  helperText="Enter the 6-digit code from your email"
                />
                
                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={verifying || code.length !== 6}
                  startIcon={verifying ? <CircularProgress size={20} /> : null}
                >
                  {verifying ? 'Verifying...' : 'Verify Email'}
                </Button>
              </Box>

              <Alert severity="info" sx={{ mb: 2, textAlign: 'left' }}>
                <Typography variant="body2">
                  <strong>Didn't receive the code?</strong>
                </Typography>
                <Typography variant="body2" sx={{ mt: 1 }}>
                  • Check your spam folder<br />
                  • Make sure you entered the correct email<br />
                  • The code expires in 30 minutes
                </Typography>
              </Alert>

              <Box sx={{ mt: 3 }}>
                <Button
                  variant="outlined"
                  onClick={handleResendEmail}
                  disabled={resending || !email}
                  startIcon={resending ? <CircularProgress size={20} /> : <EmailIcon />}
                  sx={{ mb: 2, width: '100%' }}
                >
                  {resending ? 'Sending...' : 'Resend Code'}
                </Button>

                <Button
                  variant="text"
                  component={Link}
                  to="/login"
                  sx={{ width: '100%' }}
                >
                  Back to Login
                </Button>
              </Box>
            </>
          )}
        </Paper>
      </Box>
    </Container>
  );
};

export default VerificationPending;

