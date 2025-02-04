import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box, Container } from '@mui/material';
import ReceiptList from './components/ReceiptList';
import ReceiptUpload from './components/ReceiptUpload';
import ReceiptDetail from './components/ReceiptDetail';
import Login from './components/Login';
import { useAuth } from './contexts/AuthContext';

const PrivateRoute: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" />;
};

const AppRoutes: React.FC = () => {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Container component="main" sx={{ mt: 4, mb: 4, flex: 1 }}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/"
            element={
              <PrivateRoute>
                <ReceiptList />
              </PrivateRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <PrivateRoute>
                <ReceiptUpload />
              </PrivateRoute>
            }
          />
          <Route
            path="/receipt/:id"
            element={
              <PrivateRoute>
                <ReceiptDetail />
              </PrivateRoute>
            }
          />
        </Routes>
      </Container>
    </Box>
  );
};

export default AppRoutes; 