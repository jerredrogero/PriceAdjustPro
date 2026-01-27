import React, { useState, useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { ThemeContextProvider } from './contexts/ThemeContext';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import Login from './components/Login';
import Register from './pages/Register';
import PasswordReset from './components/PasswordReset';
import PasswordResetConfirm from './components/PasswordResetConfirm';
import Dashboard from './pages/Dashboard';
import ReceiptList from './pages/ReceiptList';
import ReceiptUpload from './pages/ReceiptUpload';
import PriceAdjustments from './pages/PriceAdjustments';
import Analytics from './pages/Analytics';
import OnSale from './pages/OnSale';
import Landing from './pages/Landing';
import Subscription from './pages/Subscription';
import Settings from './pages/Settings';
import Navigation from './components/Navigation';
import Footer from './components/Footer';
import ReceiptDetail from './pages/ReceiptDetail';
import PrivacyPolicy from './pages/PrivacyPolicy';
import TermsOfService from './pages/TermsOfService';
import Support from './pages/Support';
import VerifyEmail from './pages/VerifyEmail';
import VerificationPending from './pages/VerificationPending';
import api from './api/axios';
import { UserContext } from './components/Layout';

// Define User interface directly in this file
interface User {
  id: number;
  username: string;
  email?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  account_type?: 'free' | 'paid';
}

// Wrapper component to handle auth check
const AppContent: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const location = useLocation();
  const hasCheckedAuthRef = useRef(false);

  useEffect(() => {
    console.log('App.tsx: useEffect triggered for path:', location.pathname);
    
    // Check if this might be coming from a hijack or existing session
    const maybeFromHijack = document.referrer.includes('/admin/') || document.referrer.includes('/hijack/');
    
    // Public pages that don't require authentication check
    const publicPages = ['/', '/login', '/register', '/reset-password', '/privacy-policy', '/terms-of-service', '/support', '/verification-pending'];
    const isPublicPage = publicPages.some(page => 
      location.pathname === page || 
      location.pathname.startsWith('/reset-password/') ||
      location.pathname.startsWith('/verify-email/')
    );

    console.log('App.tsx: isPublicPage check:', isPublicPage, 'for path:', location.pathname);
    console.log('App.tsx: maybeFromHijack:', maybeFromHijack);

    const shouldSkipAuthCheck = isPublicPage && hasCheckedAuthRef.current;
    if (shouldSkipAuthCheck) {
      console.log('App.tsx: Public page with prior auth state, skipping check.');
      setLoading(false);
      setAuthChecked(true);
      return;
    }

    console.log('App.tsx: Running auth check for path:', location.pathname);

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

    hasCheckedAuthRef.current = true;
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

  const PublicPageLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Box component="main" sx={{ pt: 8, pb: 4, flexGrow: 1 }}>
        {children}
      </Box>
      <Footer />
    </Box>
  );

  return (
    <UserContext.Provider value={user}>
        <Navigation user={user} />
        <Routes>
        <Route path="/" element={<PublicPageLayout><Landing /></PublicPageLayout>} />
        <Route path="/support" element={<PublicPageLayout><Support /></PublicPageLayout>} />
        <Route path="/privacy-policy" element={<PublicPageLayout><PrivacyPolicy /></PublicPageLayout>} />
        <Route path="/terms-of-service" element={<PublicPageLayout><TermsOfService /></PublicPageLayout>} />
        <Route path="/reset-password/:uid/:token" element={
          <PublicPageLayout><PasswordResetConfirm /></PublicPageLayout>
        } />
        <Route path="/reset-password" element={
          user ? <Navigate to="/dashboard" /> : <PublicPageLayout><PasswordReset /></PublicPageLayout>
        } />
        <Route path="/verify-email/:token" element={
          <PublicPageLayout><VerifyEmail /></PublicPageLayout>
        } />
        <Route path="/verification-pending" element={
          <PublicPageLayout><VerificationPending /></PublicPageLayout>
        } />
        <Route path="/login" element={
          user ? <Navigate to="/dashboard" /> : <PublicPageLayout><Login /></PublicPageLayout>
        } />
        <Route path="/register" element={user ? <Navigate to="/dashboard" /> : <PublicPageLayout><Register /></PublicPageLayout>} />
        <Route element={<PrivateRoute authChecked={authChecked}><Layout /></PrivateRoute>}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/receipts" element={<ReceiptList />} />
          <Route path="/receipts/:transactionNumber" element={<ReceiptDetail />} />
          <Route path="/upload" element={<ReceiptUpload />} />
          <Route path="/price-adjustments" element={<PriceAdjustments />} />
          <Route path="/on-sale" element={<OnSale />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/subscription" element={<Subscription />} />
          <Route path="/settings" element={<Settings />} />
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