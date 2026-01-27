import React, { useState, useEffect } from 'react';
import { Link as RouterLink, useNavigate, useLocation } from 'react-router-dom';
import {
  Container,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Link,
  Box,
  Alert,
  Checkbox,
  FormControlLabel,
  Fade,
} from '@mui/material';
import { Login as LoginIcon, CheckCircle as CheckCircleIcon } from '@mui/icons-material';
import api from '../api/axios';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showVerifiedMessage, setShowVerifiedMessage] = useState(false);
  const [rememberMe, setRememberMe] = useState<boolean>(() => {
    if (typeof window === 'undefined') return true;
    const stored = window.localStorage.getItem('rememberMe');
    return stored === null ? true : stored === 'true';
  });

  useEffect(() => {
    // Check if we just came from a successful verification
    const params = new URLSearchParams(location.search);
    if (params.get('verified') === 'true') {
      setShowVerifiedMessage(true);
      // Clean up the URL
      navigate('/login', { replace: true });
    }
  }, [location, navigate]);

  const persistRememberMe = (value: boolean) => {
    try {
      window.localStorage.setItem('rememberMe', value ? 'true' : 'false');
    } catch (storageError) {
      console.warn('Unable to persist rememberMe preference', storageError);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.post('/api/auth/login/', {
        email,
        password,
        remember_me: rememberMe,
      });
      
      // Give a small delay to ensure session cookies are properly set
      setTimeout(() => {
        // After successful login, force a page reload to trigger auth check in App.tsx
        window.location.href = '/dashboard';
      }, 100);
      
      // Don't set loading to false here since we're redirecting
    } catch (err: any) {
      console.error('Login error:', err);
      
      // Handle other errors
      let message = 'Invalid email or password';
      if (err.response?.data?.message) {
        message = err.response.data.message;
      } else if (err.response?.data?.error) {
        message = err.response.data.error;
      }
      
      setError(message);
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Card elevation={3}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <LoginIcon sx={{ fontSize: 40, color: 'primary.main', mb: 2 }} />
            <Typography variant="h4" component="h1" gutterBottom>
              Welcome Back
            </Typography>
            <Typography color="text.secondary">
              Sign in to continue to PriceAdjustPro
            </Typography>
          </Box>

          {showVerifiedMessage && (
            <Fade in={showVerifiedMessage} timeout={800}>
              <Box sx={{ mb: 4, textAlign: 'center' }}>
                <CheckCircleIcon sx={{ fontSize: 60, color: 'success.main', mb: 1 }} />
                <Typography variant="h5" color="success.main" gutterBottom sx={{ fontWeight: 'bold' }}>
                  Email Verified!
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  Congratulations! Your account is now fully active. 
                  Please sign in below to start saving.
                </Typography>
              </Box>
            </Fade>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              helperText="Note: Emails are case sensitive"
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              sx={{ mb: 3 }}
            />
            <FormControlLabel
              control={
                <Checkbox
                  checked={rememberMe}
                  onChange={(e) => {
                    setRememberMe(e.target.checked);
                    persistRememberMe(e.target.checked);
                  }}
                  color="primary"
                />
              }
              label="Remember me on this device"
              sx={{ mb: 3 }}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={loading}
              startIcon={<LoginIcon />}
            >
              Sign In
            </Button>
          </form>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Don't have an account?{' '}
              <Link component={RouterLink} to="/register">
                Create one here
              </Link>
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Login; 