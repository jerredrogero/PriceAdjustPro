import React, { useState } from 'react';
import { useLocation, Link } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Paper,
  Alert,
  Button,
  CircularProgress,
} from '@mui/material';
import EmailIcon from '@mui/icons-material/Email';
import axios from 'axios';

const VerificationPending: React.FC = () => {
  const location = useLocation();
  const email = location.state?.email || '';
  const [resending, setResending] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [resendMessage, setResendMessage] = useState('');

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
      setResendMessage(response.data.message || 'Verification email sent!');
    } catch (error: any) {
      setResendStatus('error');
      if (error.response?.data?.error) {
        setResendMessage(error.response.data.error);
      } else {
        setResendMessage('Failed to resend email. Please try again later.');
      }
    } finally {
      setResending(false);
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, mb: 4 }}>
        <Paper elevation={3} sx={{ p: 4, textAlign: 'center' }}>
          <EmailIcon sx={{ fontSize: 80, color: 'primary.main', mb: 2 }} />
          
          <Typography variant="h4" gutterBottom>
            Verify Your Email
          </Typography>

          <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
            We've sent a verification link to:
          </Typography>

          <Typography variant="h6" color="primary" sx={{ mb: 3 }}>
            {email || 'your email address'}
          </Typography>

          <Alert severity="info" sx={{ mb: 3, textAlign: 'left' }}>
            <Typography variant="body2" gutterBottom>
              <strong>What's next?</strong>
            </Typography>
            <Typography variant="body2" component="div">
              <ol style={{ margin: '8px 0', paddingLeft: '20px' }}>
                <li>Check your email inbox (and spam folder)</li>
                <li>Click the verification link in the email</li>
                <li>Return here to log in</li>
              </ol>
            </Typography>
            <Typography variant="body2" sx={{ mt: 1 }}>
              The verification link will expire in 24 hours.
            </Typography>
          </Alert>

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

          <Box sx={{ mt: 3 }}>
            <Button
              variant="outlined"
              onClick={handleResendEmail}
              disabled={resending || !email}
              startIcon={resending ? <CircularProgress size={20} /> : <EmailIcon />}
              sx={{ mb: 2, width: '100%' }}
            >
              {resending ? 'Sending...' : 'Resend Verification Email'}
            </Button>

            <Button
              variant="contained"
              component={Link}
              to="/login"
              sx={{ width: '100%' }}
            >
              Go to Login
            </Button>
          </Box>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
            Already verified?{' '}
            <Link to="/login" style={{ textDecoration: 'none' }}>
              Log in here
            </Link>
          </Typography>
        </Paper>
      </Box>
    </Container>
  );
};

export default VerificationPending;

