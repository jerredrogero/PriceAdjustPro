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
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await api.get('/api/auth/user/');
        setUser(response.data);
      } catch (error) {
        setUser(null);
        // Don't redirect if on public paths or accessing static files
        const publicPaths = ['/', '/login', '/register'];
        const isPublicPath = publicPaths.includes(location.pathname);
        const isStaticFile = location.pathname.startsWith('/static/') || 
                           location.pathname.includes('favicon.ico') ||
                           location.pathname.includes('manifest.json') ||
                           location.pathname.includes('logo192.png');
        
        // Only redirect to login if trying to access a protected route
        if (!isPublicPath && !isStaticFile && !location.pathname.startsWith('/api/')) {
          navigate('/login', { state: { from: location.pathname } });
        }
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [navigate, location.pathname]);

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
      <Routes>
        <Route path="/" element={user ? <Navigate to="/dashboard" /> : <Landing />} />
        <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <Login />} />
        <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <Register />} />
        <Route element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/receipts" element={<ReceiptList />} />
          <Route path="/receipts/:transactionNumber" element={<ReceiptDetail />} />
          <Route path="/upload" element={<ReceiptUpload />} />
          <Route path="/price-adjustments" element={<PriceAdjustments />} />
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