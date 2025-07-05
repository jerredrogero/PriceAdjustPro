import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Card,
  CardHeader,
  CardContent,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  FormControlLabel,
  Switch,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Paper,
  Chip,
} from '@mui/material';
import {
  Save as SaveIcon,
  Lock as LockIcon,
  DeleteForever as DeleteIcon,
  Palette as PaletteIcon,
  Notifications as NotificationsIcon,
  Download as DownloadIcon,
  Security as SecurityIcon,
  Account as AccountIcon,
} from '@mui/icons-material';
import { UserContext } from '../components/Layout';
import { useThemeContext } from '../contexts/ThemeContext';

const Settings: React.FC = () => {
  const navigate = useNavigate();
  const user = useContext(UserContext);
  const { mode, toggleTheme } = useThemeContext();
  
  // Profile settings
  const [email, setEmail] = useState(user?.email || '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [deletePassword, setDeletePassword] = useState('');
  
  // Notification settings
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [pushNotifications, setPushNotifications] = useState(true);
  const [priceAlerts, setPriceAlerts] = useState(true);
  const [weeklyReports, setWeeklyReports] = useState(false);
  
  // Data settings
  const [dataRetention, setDataRetention] = useState('1year');
  
  // UI state
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleUpdateNotifications = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/auth/update-notifications/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email_notifications: emailNotifications,
          push_notifications: pushNotifications,
          price_alerts: priceAlerts,
          weekly_reports: weeklyReports,
        }),
      });

      if (!response.ok) throw new Error('Failed to update notifications');
      setSuccess('Notification preferences updated successfully');
    } catch (err) {
      setError('Failed to update notification preferences');
    } finally {
      setLoading(false);
    }
  };

  const handleExportData = async (format: 'csv' | 'json') => {
    setLoading(true);
    try {
      const response = await fetch(`/api/auth/export-data/?format=${format}`, {
        method: 'GET',
      });

      if (!response.ok) throw new Error('Failed to export data');
      
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `priceadjustpro-data.${format}`;
      a.click();
      window.URL.revokeObjectURL(url);
      
      setSuccess(`Data exported successfully as ${format.toUpperCase()}`);
    } catch (err) {
      setError('Failed to export data');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    try {
      const response = await fetch('/api/auth/update-profile/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) throw new Error('Failed to update profile');
      setSuccess('Profile updated successfully');
    } catch (err) {
      setError('Failed to update profile');
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }

    try {
      const response = await fetch('/api/auth/change-password/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          old_password: currentPassword,
          new_password1: newPassword,
          new_password2: confirmPassword,
        }),
      });

      if (!response.ok) throw new Error('Failed to change password');
      
      setSuccess('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      setError('Failed to change password');
    }
  };

  const handleDeleteAccount = async () => {
    try {
      const response = await fetch('/api/auth/delete-account/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          confirm_password: deletePassword,
        }),
      });

      if (!response.ok) throw new Error('Failed to delete account');

      // Force a full page reload to clear React state and redirect to login
      window.location.href = '/login';
    } catch (err) {
      setError('Failed to delete account');
      setDeleteDialogOpen(false);
    }
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Account Settings
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Profile Information" />
            <CardContent>
              <form onSubmit={handleUpdateProfile}>
                <TextField
                  fullWidth
                  label="Username"
                  value={user?.username}
                  disabled
                  sx={{ mb: 3 }}
                />
                <TextField
                  fullWidth
                  label="Email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  sx={{ mb: 3 }}
                />
                <Button
                  type="submit"
                  variant="contained"
                  startIcon={<SaveIcon />}
                >
                  Update Profile
                </Button>
              </form>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader title="Change Password" />
            <CardContent>
              <form onSubmit={handleChangePassword}>
                <TextField
                  fullWidth
                  label="Current Password"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  sx={{ mb: 3 }}
                />
                <TextField
                  fullWidth
                  label="New Password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  sx={{ mb: 3 }}
                />
                <TextField
                  fullWidth
                  label="Confirm New Password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  sx={{ mb: 3 }}
                />
                <Button
                  type="submit"
                  variant="contained"
                  startIcon={<LockIcon />}
                >
                  Change Password
                </Button>
              </form>
            </CardContent>
          </Card>
        </Grid>

        {/* Theme Settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader 
              title="Theme Preferences" 
              avatar={<PaletteIcon color="primary" />}
            />
            <CardContent>
              <FormControlLabel
                control={
                  <Switch
                    checked={mode === 'dark'}
                    onChange={toggleTheme}
                    color="primary"
                  />
                }
                label="Dark Mode"
              />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                Switch between light and dark themes for better viewing comfort.
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Notification Settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader 
              title="Notifications" 
              avatar={<NotificationsIcon color="primary" />}
            />
            <CardContent>
              <List>
                <ListItem>
                  <ListItemText 
                    primary="Email Notifications" 
                    secondary="Receive updates via email"
                  />
                  <ListItemSecondaryAction>
                    <Switch
                      checked={emailNotifications}
                      onChange={(e) => setEmailNotifications(e.target.checked)}
                      color="primary"
                    />
                  </ListItemSecondaryAction>
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Push Notifications" 
                    secondary="Browser push notifications"
                  />
                  <ListItemSecondaryAction>
                    <Switch
                      checked={pushNotifications}
                      onChange={(e) => setPushNotifications(e.target.checked)}
                      color="primary"
                    />
                  </ListItemSecondaryAction>
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Price Alerts" 
                    secondary="Alerts for new price adjustments"
                  />
                  <ListItemSecondaryAction>
                    <Switch
                      checked={priceAlerts}
                      onChange={(e) => setPriceAlerts(e.target.checked)}
                      color="primary"
                    />
                  </ListItemSecondaryAction>
                </ListItem>
                <ListItem>
                  <ListItemText 
                    primary="Weekly Reports" 
                    secondary="Weekly summary emails"
                  />
                  <ListItemSecondaryAction>
                    <Switch
                      checked={weeklyReports}
                      onChange={(e) => setWeeklyReports(e.target.checked)}
                      color="primary"
                    />
                  </ListItemSecondaryAction>
                </ListItem>
              </List>
              <Box sx={{ mt: 2 }}>
                <Button
                  variant="contained"
                  onClick={handleUpdateNotifications}
                  disabled={loading}
                  startIcon={<SaveIcon />}
                >
                  Save Preferences
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Data Management */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader 
              title="Data Management" 
              avatar={<DownloadIcon color="primary" />}
            />
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Export Your Data
              </Typography>
              <Typography variant="body2" color="text.secondary" paragraph>
                Download all your receipt data, price adjustments, and analytics.
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
                <Button
                  variant="outlined"
                  onClick={() => handleExportData('csv')}
                  disabled={loading}
                >
                  Export CSV
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => handleExportData('json')}
                  disabled={loading}
                >
                  Export JSON
                </Button>
              </Box>
              
              <Divider sx={{ my: 2 }} />
              
              <Typography variant="h6" gutterBottom>
                Data Retention
              </Typography>
              <FormControl fullWidth sx={{ mb: 2 }}>
                <InputLabel>Keep data for</InputLabel>
                <Select
                  value={dataRetention}
                  onChange={(e) => setDataRetention(e.target.value)}
                  label="Keep data for"
                >
                  <MenuItem value="6months">6 months</MenuItem>
                  <MenuItem value="1year">1 year</MenuItem>
                  <MenuItem value="2years">2 years</MenuItem>
                  <MenuItem value="forever">Forever</MenuItem>
                </Select>
              </FormControl>
            </CardContent>
          </Card>
        </Grid>

        {/* Account Information */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardHeader 
              title="Account Information" 
              avatar={<AccountIcon color="primary" />}
            />
            <CardContent>
              <Paper elevation={0} sx={{ p: 2, bgcolor: 'background.default' }}>
                <Typography variant="body2" color="text.secondary">
                  <strong>Username:</strong> {user?.username}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  <strong>Email:</strong> {user?.email || 'Not set'}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                  <strong>Account Type:</strong> 
                  <Chip 
                    label={user?.is_superuser ? 'Admin' : 'User'} 
                    size="small" 
                    color={user?.is_superuser ? 'primary' : 'default'}
                    sx={{ ml: 1 }}
                  />
                </Typography>
              </Paper>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Box sx={{ mt: 3 }}>
            <Divider sx={{ mb: 3 }} />
            <Typography variant="h6" color="error" gutterBottom>
              Danger Zone
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Once you delete your account, there is no going back. Please be certain.
            </Typography>
            <Button
              variant="outlined"
              color="error"
              startIcon={<DeleteIcon />}
              onClick={() => setDeleteDialogOpen(true)}
            >
              Delete Account
            </Button>
          </Box>
        </Grid>
      </Grid>

      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Delete Account</DialogTitle>
        <DialogContent>
          <Typography paragraph>
            Are you sure you want to delete your account? This action cannot be undone.
          </Typography>
          <TextField
            fullWidth
            label="Enter your password to confirm"
            type="password"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleDeleteAccount}
            color="error"
            variant="contained"
          >
            Delete Account
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default Settings; 