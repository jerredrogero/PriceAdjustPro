import React from 'react';

export interface User {
  id: number;
  username: string;
  email?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
}

const UserTypes: React.FC = () => {
  return null;
};

export default UserTypes; 