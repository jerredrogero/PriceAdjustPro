import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import PrivateRoute from './components/PrivateRoute';
import Dashboard from './pages/Dashboard';
import ReceiptList from './pages/ReceiptList';
import ReceiptUpload from './pages/ReceiptUpload';
import PriceAdjustments from './pages/PriceAdjustments';
import Analytics from './pages/Analytics';
import Login from './components/Login';
import Register from './components/Register';

const App: React.FC = () => {
  return (
    <Router>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/receipts" element={<PrivateRoute><ReceiptList /></PrivateRoute>} />
          <Route path="/upload" element={<PrivateRoute><ReceiptUpload /></PrivateRoute>} />
          <Route path="/adjustments" element={<PrivateRoute><PriceAdjustments /></PrivateRoute>} />
          <Route path="/analytics" element={<PrivateRoute><Analytics /></PrivateRoute>} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>
      </Routes>
    </Router>
  );
};

export default App; 