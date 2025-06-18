import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { ThemeContextProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import Login from './components/Login';
import Register from './components/Register';
import PasswordReset from './components/PasswordReset';
import PasswordResetConfirm from './components/PasswordResetConfirm';
import Dashboard from './pages/Dashboard';
import ReceiptList from './pages/ReceiptList';
import ReceiptUpload from './pages/ReceiptUpload';
import PriceAdjustments from './pages/PriceAdjustments';
import Analytics from './pages/Analytics';
import OnSale from './pages/OnSale';
import Landing from './pages/Landing';
import Navigation from './components/Navigation';
import ReceiptDetail from './pages/ReceiptDetail';
import api from './api/axios';
import { UserContext } from './components/Layout';

// Define User interface directly in this file
interface User {
  id: number;
  username: string;
  email?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
}

// Wrapper component to handle auth check
const AppContent: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const location = useLocation();

  useEffect(() => {
    console.log('App.tsx: useEffect triggered for path:', location.pathname);
    
    // Check if this might be coming from a hijack or existing session
    const maybeFromHijack = document.referrer.includes('/admin/') || document.referrer.includes('/hijack/');
    
    // Public pages that don't require authentication check
    const publicPages = ['/', '/login', '/register', '/reset-password'];
    const isPublicPage = publicPages.some(page => 
      location.pathname === page || location.pathname.startsWith('/reset-password/')
    );

    console.log('App.tsx: isPublicPage check:', isPublicPage, 'for path:', location.pathname);
    console.log('App.tsx: maybeFromHijack:', maybeFromHijack);

    if (isPublicPage) {
      console.log('App.tsx: On public page, skipping auth check:', location.pathname);
      setLoading(false);
      setAuthChecked(true);
      setUser(null);
      return;
    }

    console.log('App.tsx: On protected page, running auth check for:', location.pathname);

    const checkAuth = async () => {
      console.log('App.tsx: Checking authentication for path:', location.pathname);
      console.log('App.tsx: Current user state:', user);
      try {
        const response = await api.get('/api/auth/user/');
        console.log('App.tsx: Authentication successful:', response.data);
        setUser(response.data);
      } catch (error) {
        console.log('App.tsx: Authentication failed:', error);
        setUser(null);
      } finally {
        console.log('App.tsx: Setting loading to false and authChecked to true');
        setLoading(false);
        setAuthChecked(true);
      }
    };

    // Add a timeout to prevent infinite loading
    const timeoutId = setTimeout(() => {
      console.log('App.tsx: Authentication check timeout - setting loading to false');
      setLoading(false);
      setAuthChecked(true);
      setUser(null);
    }, 5000); // 5 second timeout

    checkAuth().finally(() => {
      clearTimeout(timeoutId);
    });

    return () => clearTimeout(timeoutId);
  }, [location.pathname]);

  if (loading) {
    console.log('App.tsx: Showing loading screen, loading:', loading, 'authChecked:', authChecked);
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  return (
    <UserContext.Provider value={user}>
        <Navigation user={user} />
        <Routes>
        <Route path="/" element={
          user ? <Navigate to="/dashboard" replace /> : <Box component="main" sx={{ pt: 8, pb: 4 }}><Landing /></Box>
        } />
        <Route path="/reset-password/:uid/:token" element={
          <Box component="main" sx={{ pt: 8, pb: 4 }}><PasswordResetConfirm /></Box>
        } />
        <Route path="/reset-password" element={
          user ? <Navigate to="/dashboard" /> : <Box component="main" sx={{ pt: 8, pb: 4 }}><PasswordReset /></Box>
        } />
        <Route path="/login" element={
          user ? <Navigate to="/dashboard" /> : <Box component="main" sx={{ pt: 8, pb: 4 }}><Login /></Box>
        } />
        <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <Box component="main" sx={{ pt: 8, pb: 4 }}><Register /></Box>} />
        <Route element={<PrivateRoute authChecked={authChecked}><Layout /></PrivateRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/receipts" element={<ReceiptList />} />
          <Route path="/receipts/:transactionNumber" element={<ReceiptDetail />} />
          <Route path="/upload" element={<ReceiptUpload />} />
          <Route path="/price-adjustments" element={<PriceAdjustments />} />
          <Route path="/on-sale" element={<OnSale />} />
          <Route path="/analytics" element={<Analytics />} />
          </Route>
        </Routes>
    </UserContext.Provider>
  );
};

const App: React.FC = () => {
  return (
    <ThemeContextProvider>
      <Router>
        <AppContent />
      </Router>
    </ThemeContextProvider>
  );
};

export default App; 