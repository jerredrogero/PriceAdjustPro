import React from 'react';
import { Box } from '@mui/material';
import Navigation from './Navigation';

interface Props {
  children: React.ReactNode;
}

const Layout: React.FC<Props> = ({ children }) => {
  return (
    <>
      <Navigation />
      <Box component="main" sx={{ pt: 8, pb: 4 }}>
        {children}
      </Box>
    </>
  );
};

export default Layout; 