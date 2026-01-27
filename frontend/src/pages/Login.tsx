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
  useTheme,
  alpha,
  Grid,
} from '@mui/material';
import { 
  Login as LoginIcon, 
  CheckCircle as CheckCircleIcon,
  ArrowForward as ArrowForwardIcon,
  Check as CheckIcon,
} from '@mui/icons-material';
import api from '../api/axios';

const Login: React.FC = () => {
  const theme = useTheme();
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
    const params = new URLSearchParams(location.search);
    if (params.get('verified') === 'true') {
      setShowVerifiedMessage(true);
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
      
      setTimeout(() => {
        window.location.href = '/dashboard';
      }, 100);
    } catch (err: any) {
      console.error('Login error:', err);
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
              Welcome Back.
            </Typography>
            <Typography variant="h6" sx={{ mb: 4, opacity: 0.9 }}>
              Sign in to see how much you've saved this month.
            </Typography>
            
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CheckIcon sx={{ mr: 2, color: 'secondary.light' }} />
              <Typography variant="body1">Real-time Sale Monitoring</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CheckIcon sx={{ mr: 2, color: 'secondary.light' }} />
              <Typography variant="body1">AI Receipt History</Typography>
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <CheckIcon sx={{ mr: 2, color: 'secondary.light' }} />
              <Typography variant="body1">Premium Sale Directory</Typography>
            </Box>
          </Grid>

          {/* Right Column - Form */}
          <Grid item xs={12} md={7} sx={{ bgcolor: 'background.paper' }}>
            <CardContent sx={{ p: { xs: 4, md: 6 } }}>
              <Box sx={{ mb: 4 }}>
                <Typography variant="h4" component="h1" gutterBottom fontWeight="900">
                  Sign In
                </Typography>
                <Typography color="text.secondary">
                  Access your PriceAdjustPro dashboard
                </Typography>
              </Box>

              {showVerifiedMessage && (
                <Fade in={showVerifiedMessage} timeout={800}>
                  <Alert severity="success" sx={{ mb: 4, borderRadius: 3 }}>
                    <Typography variant="body2">
                      <strong>Email Verified!</strong> Your account is now fully active. 
                      Please sign in to start saving.
                    </Typography>
                  </Alert>
                </Fade>
              )}

              {error && (
                <Alert severity="error" sx={{ mb: 4, borderRadius: 3 }}>
                  {error}
                </Alert>
              )}

              <form onSubmit={handleSubmit}>
                <TextField
                  fullWidth
                  label="Email Address"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  sx={{ mb: 3 }}
                  InputProps={{ sx: { borderRadius: 3 } }}
                />
                <TextField
                  fullWidth
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  sx={{ mb: 2 }}
                  InputProps={{ sx: { borderRadius: 3 } }}
                />
                
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
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
                    label={<Typography variant="body2">Remember me</Typography>}
                  />
                  <Link 
                    component={RouterLink} 
                    to="/reset-password" 
                    variant="body2"
                    sx={{ fontWeight: 'bold' }}
                  >
                    Forgot password?
                  </Link>
                </Box>

                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={loading}
                  sx={{ 
                    borderRadius: '50px', 
                    py: 2, 
                    fontWeight: 'bold',
                    fontSize: '1.1rem',
                    boxShadow: theme.shadows[4]
                  }}
                >
                  {loading ? 'Signing in...' : 'Sign In'}
                </Button>
              </form>

              <Box sx={{ mt: 4, textAlign: 'center' }}>
                <Typography variant="body2" color="text.secondary">
                  Don't have an account?{' '}
                  <Link 
                    component={RouterLink} 
                    to="/register" 
                    sx={{ fontWeight: 'bold' }}
                  >
                    Create one for free
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

export default Login;
