import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { ThemeContextProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import Login from './components/Login';
import Register from './components/Register';
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
    const checkAuth = async () => {
      console.log('App.tsx: Checking authentication for path:', location.pathname);
      try {
        const response = await api.get('/api/auth/user/');
        console.log('App.tsx: Authentication successful:', response.data);
        setUser(response.data);
      } catch (error) {
        console.log('App.tsx: Authentication failed:', error);
        setUser(null);
      } finally {
        setLoading(false);
        setAuthChecked(true);
      }
    };

    checkAuth();
  }, [location.pathname]);

  if (loading) {
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
        <Route path="/" element={<Box component="main" sx={{ pt: 8, pb: 4 }}><Landing /></Box>} />
        <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Login />} />
        <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <Register />} />
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