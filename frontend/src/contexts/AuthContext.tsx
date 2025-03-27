import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/axios';

interface AuthContextType {
  isAuthenticated: boolean;
  user: any;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  isAuthenticated: false,
  user: null,
  login: async () => {},
  logout: async () => {},
});

export const useAuth = () => useContext(AuthContext);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    // Check authentication status on mount
    console.log('AuthProvider: Checking authentication on mount');
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      console.log('AuthProvider: Making API call to check auth status');
      const response = await api.get('/api/auth/user/');
      console.log('AuthProvider: Auth check successful', response.data);
      setIsAuthenticated(true);
      setUser(response.data);
    } catch (error) {
      console.log('AuthProvider: Auth check failed', error);
      setIsAuthenticated(false);
      setUser(null);
    }
  };

  const login = async (username: string, password: string) => {
    try {
      console.log('AuthProvider: Attempting login for', username);
      const response = await api.post('/api/auth/login/', {
        username,
        password,
      });
      console.log('AuthProvider: Login successful', response.data);
      setIsAuthenticated(true);
      setUser(response.data);
      // Force a cookie check to ensure cookies are set properly
      await checkAuth();
    } catch (error) {
      console.error('AuthProvider: Login failed:', error);
      throw new Error('Login failed');
    }
  };

  const logout = async () => {
    try {
      console.log('AuthProvider: Attempting logout');
      await api.post('/api/auth/logout/');
      console.log('AuthProvider: Logout successful');
      setIsAuthenticated(false);
      setUser(null);
    } catch (error) {
      console.error('AuthProvider: Logout failed:', error);
    }
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}; 