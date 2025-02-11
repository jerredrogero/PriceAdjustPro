import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import theme from './theme';
import Layout from './components/Layout';
import Home from './pages/Home';
import ReceiptList from './pages/ReceiptList';
import ReceiptDetail from './pages/ReceiptDetail';
import PriceAdjustments from './pages/PriceAdjustments';
import Settings from './pages/Settings';
import Login from './pages/Login';
import Register from './pages/Register';
import Analytics from './pages/Analytics';
import PrivateRoute from './components/PrivateRoute';
import ReceiptUpload from './components/ReceiptUpload';

const App: React.FC = () => {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/" element={<PrivateRoute><Home /></PrivateRoute>} />
          <Route path="/receipts" element={<PrivateRoute><ReceiptList /></PrivateRoute>} />
          <Route path="/receipts/:id" element={<PrivateRoute><ReceiptDetail /></PrivateRoute>} />
          <Route path="/adjustments" element={<PrivateRoute><PriceAdjustments /></PrivateRoute>} />
          <Route path="/analytics" element={<PrivateRoute><Analytics /></PrivateRoute>} />
          <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
          <Route path="/upload" element={<ReceiptUpload />} />
        </Routes>
      </Layout>
    </Router>
  );
};

export default App; 