import React, { useContext } from 'react';
import { Navigate } from 'react-router-dom';
import { UserContext } from './Layout';

interface Props {
  children: React.ReactNode;
}

const PrivateRoute: React.FC<Props> = ({ children }) => {
  const user = useContext(UserContext);
  const isAuthenticated = !!user;

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export default PrivateRoute; 