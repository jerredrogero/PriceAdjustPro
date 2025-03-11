import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { ThemeProvider, createTheme, Box } from '@mui/material';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './pages/Dashboard';
import ReceiptList from './pages/ReceiptList';
import ReceiptUpload from './pages/ReceiptUpload';
import PriceAdjustments from './pages/PriceAdjustments';
import Analytics from './pages/Analytics';
import Landing from './pages/Landing';
import Navigation from './components/Navigation';
import ReceiptDetail from './pages/ReceiptDetail';
import api from './api/axios';
import { User } from './types/User';

const theme = createTheme({
  palette: {
    primary: {
      main: '#CF0A2C', // Costco red
      light: '#E63950',
      dark: '#B00020',
    },
    secondary: {
      main: '#005DAA', // Costco blue
      light: '#4286C5',
      dark: '#003C7D',
    },
  },
});

// Wrapper component to handle auth check
const AppContent: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await api.get('/auth/user/');
        setUser(response.data);
      } catch (error) {
        // Don't redirect to login if already on landing page or login/register pages
        const publicPaths = ['/', '/login', '/register'];
        if (!publicPaths.includes(location.pathname) && 
            !location.pathname.startsWith('/static/') && 
            !location.pathname.includes('favicon.ico')) {
          navigate('/login');
        }
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [navigate, location.pathname]);

  if (loading) {
    return <Box sx={{ p: 4 }}>Loading...</Box>;
  }

  return (
    <>
      <Navigation user={user} />
      <Box sx={{ mt: 8 }}>
        <Routes>
          {/* Public Routes */}
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected Routes */}
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
            <Route path="/receipts" element={<PrivateRoute><ReceiptList /></PrivateRoute>} />
            <Route path="/receipts/:transactionNumber" element={<PrivateRoute><ReceiptDetail /></PrivateRoute>} />
            <Route path="/upload" element={<PrivateRoute><ReceiptUpload /></PrivateRoute>} />
            <Route path="/price-adjustments" element={<PrivateRoute><PriceAdjustments /></PrivateRoute>} />
            <Route path="/analytics" element={<PrivateRoute><Analytics /></PrivateRoute>} />
          </Route>

          {/* Redirect unmatched routes to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Box>
    </>
  );
};

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <Router>
        <AppContent />
      </Router>
    </ThemeProvider>
  );
};

export default App; 