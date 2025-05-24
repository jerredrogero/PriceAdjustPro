import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { UserContext } from './Layout';
import { Box, CircularProgress } from '@mui/material';

interface Props {
  children: React.ReactNode;
  authChecked?: boolean;
}

const PrivateRoute: React.FC<Props> = ({ children, authChecked = true }) => {
  const user = useContext(UserContext);
  const isAuthenticated = !!user;

  // Show loading spinner while authentication is being checked
  if (!authChecked) {
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

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export default PrivateRoute; 