import React, { useContext } from 'react';
import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import Navigation from './Navigation';
import Footer from './Footer';

// Define the User interface
interface User {
  id: number;
  username: string;
  email?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  account_type?: 'free' | 'paid';
}

// Create a context for user data
export const UserContext = React.createContext<User | null>(null);

const Layout: React.FC = () => {
  // Get user from context
  const user = useContext(UserContext);
  
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Navigation user={user} />
      <Box component="main" sx={{ pt: 8, pb: 4, flexGrow: 1 }}>
        <Outlet />
      </Box>
      <Footer />
    </Box>
  );
};

export default Layout; 