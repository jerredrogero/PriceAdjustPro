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
} from '@mui/material';
import { PersonAdd as RegisterIcon } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const Register: React.FC = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
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
      
      // Check session state before registration
      const sessionCheck = await axios.get('/api/debug/session/', { withCredentials: true });
      console.log('Pre-registration session state:', sessionCheck.data);
      
      // Use axios instead of fetch to ensure cookies are handled properly
      const response = await axios.post('/api/auth/register/', {
        username,
        email,
        password1: password,
        password2: confirmPassword,
      }, { 
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
        }
      });
      
      console.log('Registration successful:', response.data);
      
      // Check session state after registration
      const postRegSession = await axios.get('/api/debug/session/', { withCredentials: true });
      console.log('Post-registration session state:', postRegSession.data);

      // Wait 1 second to ensure session is established
      await new Promise(resolve => setTimeout(resolve, 1000));

      try {
        // Log in the user after successful registration
        console.log('Attempting login after registration');
        await login(username, password);
        
        // Check session after login
        const postLoginSession = await axios.get('/api/debug/session/', { withCredentials: true });
        console.log('Post-login session state:', postLoginSession.data);
        
        console.log('Login successful, navigating to dashboard');
        navigate('/dashboard');
      } catch (loginErr) {
        console.error('Post-registration login failed:', loginErr);
        // If login fails, try to continue with registration success
        navigate('/dashboard');
      }
    } catch (err) {
      console.error('Registration error:', err);
      let message = 'Failed to create account';
      
      if (axios.isAxiosError(err) && err.response) {
        message = err.response.data.error || message;
        console.error('Server response:', err.response.data);
      }
      
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ mt: 8 }}>
      <Card elevation={3}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <RegisterIcon sx={{ fontSize: 40, color: 'primary.main', mb: 2 }} />
            <Typography variant="h4" component="h1" gutterBottom>
              Create Account
            </Typography>
            <Typography color="text.secondary">
              Join PriceAdjustPro to start tracking your receipts
            </Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="Username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              sx={{ mb: 2 }}
            />
            <TextField
              fullWidth
              label="Confirm Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              sx={{ mb: 3 }}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={loading}
              startIcon={<RegisterIcon />}
            >
              Create Account
            </Button>
          </form>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Already have an account?{' '}
              <Link component={RouterLink} to="/login">
                Sign in here
              </Link>
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Container>
  );
};

export default Register; 