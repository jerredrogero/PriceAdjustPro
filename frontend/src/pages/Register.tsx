import React, { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
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
  useTheme,
  alpha,
  Grid,
} from '@mui/material';
import { 
  PersonAdd as RegisterIcon,
  ArrowForward as ArrowForwardIcon,
  Check as CheckIcon
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/axios';
import axios from 'axios';

const Register: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);

    try {
      console.log('Registration: Sending registration request');
      
      const response = await api.post('/api/auth/register/', {
        email,
        first_name: firstName,
        last_name: lastName,
        password,
      });
      
      console.log('Registration successful:', response.data);
      
      try {
        await api.post('/api/auth/login/', {
          email,
          password,
          remember_me: true,
        });
        window.location.href = '/dashboard';
      } catch (loginErr) {
        console.error('Auto-login failed:', loginErr);
        navigate('/login', { state: { message: 'Account created! Please sign in.' } });
      }
    } catch (err) {
      console.error('Registration error:', err);
      let message = 'Failed to create account';
      if (axios.isAxiosError(err) && err.response) {
        message = err.response.data.error || message;
      }
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box 
      sx={{ 
        minHeight: '100vh', 
        display: 'flex', 
        alignItems: 'center', 
        background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
        py: { xs: 4, md: 8 }
      }}
    >
      <Container maxWidth="md">
        <Grid container spacing={0} sx={{ boxShadow: '0 20px 60px rgba(0,0,0,0.3)', borderRadius: 6, overflow: 'hidden' }}>
          {/* Left Column - Marketing */}
          <Grid item xs={12} md={5} sx={{ bgcolor: alpha(theme.palette.common.white, 0.1), backdropFilter: 'blur(10px)', color: 'white', p: 6, display: { xs: 'none', md: 'flex' }, flexDirection: 'column', justifyContent: 'center' }}>
            <Typography variant="h3" fontWeight="900" gutterBottom>
              Join the Savers.
            </Typography>
            <Typography variant="h6" sx={{ mb: 4, opacity: 0.9 }}>
              Start tracking your Costco receipts today and never miss a refund.
            </Typography>
            
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CheckIcon sx={{ mr: 2, color: 'secondary.light' }} />
              <Typography variant="body1">30-day Price Monitoring</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CheckIcon sx={{ mr: 2, color: 'secondary.light' }} />
              <Typography variant="body1">AI Receipt Scanning</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CheckIcon sx={{ mr: 2, color: 'secondary.light' }} />
              <Typography variant="body1">Instant Refund Alerts</Typography>
            </Box>
          </Grid>

          {/* Right Column - Form */}
          <Grid item xs={12} md={7} sx={{ bgcolor: 'background.paper' }}>
            <CardContent sx={{ p: { xs: 4, md: 6 } }}>
              <Box sx={{ mb: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom fontWeight="900">
                  Create Account
                </Typography>
                <Typography color="text.secondary">
                  Join PriceAdjustPro for free
                </Typography>
              </Box>

              {error && (
                <Alert severity="error" sx={{ mb: 4, borderRadius: 3 }}>
                  {error}
                </Alert>
              )}

              <form onSubmit={handleSubmit}>
                <Grid container spacing={2}>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="First Name"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      required
                      InputProps={{ sx: { borderRadius: 3 } }}
                    />
                  </Grid>
                  <Grid item xs={12} sm={6}>
                    <TextField
                      fullWidth
                      label="Last Name"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      required
                      InputProps={{ sx: { borderRadius: 3 } }}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Email Address"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                      InputProps={{ sx: { borderRadius: 3 } }}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      InputProps={{ sx: { borderRadius: 3 } }}
                    />
                  </Grid>
                  <Grid item xs={12}>
                    <TextField
                      fullWidth
                      label="Confirm Password"
                      type="password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      InputProps={{ sx: { borderRadius: 3 } }}
                    />
                  </Grid>
                </Grid>

                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={loading}
                  sx={{ 
                    mt: 4,
                    borderRadius: '50px', 
                    py: 2, 
                    fontWeight: 'bold',
                    fontSize: '1.1rem',
                    boxShadow: theme.shadows[4]
                  }}
                >
                  {loading ? 'Creating Account...' : 'Create Account'}
                </Button>
              </form>

              <Box sx={{ mt: 4, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  Already have an account?{' '}
                  <Link 
                    component={RouterLink} 
                    to="/login" 
                    sx={{ fontWeight: 'bold' }}
                  >
                    Sign in here
                  </Link>
                </Typography>
              </Box>
            </CardContent>
          </Grid>
        </Grid>
        
        <Box sx={{ mt: 4, textAlign: 'center' }}>
          <Button
            startIcon={<ArrowForwardIcon sx={{ transform: 'rotate(180deg)' }} />}
            component={RouterLink}
            to="/"
            sx={{ color: 'white', opacity: 0.8, '&:hover': { opacity: 1 } }}
          >
            Back to Home
          </Button>
        </Box>
      </Container>
    </Box>
  );
};

export default Register;
