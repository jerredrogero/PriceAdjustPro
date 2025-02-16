import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
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

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <Router>
        <Navigation />
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
      </Router>
    </ThemeProvider>
  );
};

export default App; 