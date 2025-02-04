import React from 'react';
import Navigation from './components/Navigation';
import AppRoutes from './routes';
import { AuthProvider } from './contexts/AuthContext';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <Navigation />
      <AppRoutes />
    </AuthProvider>
  );
};

export default App; 