import React from 'react';
import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import Navigation from './Navigation';

const Layout: React.FC = () => {
  return (
    <>
      <Navigation />
      <Box component="main" sx={{ pt: 8, pb: 4 }}>
        <Outlet />
      </Box>
    </>
  );
};

export default Layout; 