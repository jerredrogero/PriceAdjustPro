import React, { useState, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Card,
  CardContent,
  TextField,
  Button,
  Typography,
  Alert,
  Box,
} from '@mui/material';
import { LockReset } from '@mui/icons-material';
import api from '../api/axios';
import { UserContext } from './Layout';

const PasswordResetConfirm: React.FC = () => {
  const { uid, token } = useParams<{ uid: string; token: string }>();
  const navigate = useNavigate();
  const user = useContext(UserContext);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match');
      setLoading(false);
      return;
    }

    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long');
      setLoading(false);
      return;
    }

    try {
      const response = await api.post('/api/auth/password-reset-confirm/', {
        uid,
        token,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      
      setSuccess(response.data.message);
      // Redirect after 2 seconds - to dashboard if logged in, login if not
      setTimeout(() => {
        navigate(user ? '/dashboard' : '/login');
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to reset password');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="sm" sx={{ py: 4 }}>
      <Card elevation={3}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <LockReset sx={{ fontSize: 40, color: 'primary.main', mb: 2 }} />
            <Typography variant="h4" component="h1" gutterBottom>
              Set New Password
            </Typography>
            <Typography color="text.secondary">
              Enter your new password below
            </Typography>
          </Box>

          {user && (
            <Alert severity="info" sx={{ mb: 3 }}>
              You are already logged in as {user.username}. You can still reset your password if needed.
            </Alert>
          )}

          {error && (
            <Alert severity="error" sx={{ mb: 3 }}>
              {error}
            </Alert>
          )}

          {success && (
            <Alert severity="success" sx={{ mb: 3 }}>
              {success} {user ? 'Your password has been updated.' : 'You will be redirected to the login page.'}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              sx={{ mb: 2 }}
              helperText="Password must be at least 8 characters long"
            />
            <TextField
              fullWidth
              label="Confirm New Password"
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
              disabled={loading || success !== ''}
              startIcon={<LockReset />}
            >
              Reset Password
            </Button>
          </form>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Button
              onClick={() => navigate(user ? '/dashboard' : '/login')}
              variant="text"
            >
              {user ? 'Back to Dashboard' : 'Back to Login'}
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Container>
  );
};

export default PasswordResetConfirm; 