import React, { useState, useEffect } from 'react';
import { useParams, Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  Box,
  Chip,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  LocalOffer as PriceIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../api/axios';

interface ReceiptItem {
  item_code: string;
  description: string;
  quantity: number;
  price: string;
  total_price: string;
  is_taxable: boolean;
  discount: string | null;
}

interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  subtotal: string;
  tax: string;
  total: string;
  items: ReceiptItem[];
  parsed_successfully: boolean;
  parse_error: string | null;
  file: string | null;
}

const ReceiptDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchReceipt();
  }, [id]);

  const fetchReceipt = async () => {
    try {
      const response = await api.get(`/api/receipts/${id}/`);
      setReceipt(response.data);
    } catch (err) {
      setError('Failed to load receipt details');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LinearProgress />;

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Container>
    );
  }

  if (!receipt) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">Receipt not found</Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Button
        component={RouterLink}
        to="/receipts"
        startIcon={<ArrowBackIcon />}
        sx={{ mb: 3 }}
      >
        Back to Receipts
      </Button>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h4" gutterBottom>
          Receipt Details
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          {receipt.store_location}
          {receipt.store_number && ` #${receipt.store_number}`}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          Date: {receipt.transaction_date ? 
            format(new Date(receipt.transaction_date), 'MMMM d, yyyy') : 
            'Invalid date'}
        </Typography>
        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            Subtotal: ${receipt.subtotal}
          </Typography>
          <Typography variant="subtitle1" gutterBottom>
            Tax: ${receipt.tax}
          </Typography>
          <Typography variant="h5" color="primary" gutterBottom>
            Total: ${receipt.total}
          </Typography>
        </Box>
      </Paper>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Item Code</TableCell>
              <TableCell>Description</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell align="center">Status</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {receipt.items.map((item) => (
              <TableRow key={item.item_code}>
                <TableCell>{item.item_code}</TableCell>
                <TableCell>{item.description}</TableCell>
                <TableCell align="right">{item.quantity}</TableCell>
                <TableCell align="right">${item.price}</TableCell>
                <TableCell align="right">${item.total_price}</TableCell>
                <TableCell align="center">
                  {item.is_taxable && (
                    <Chip
                      label="Taxable"
                      color="default"
                      size="small"
                      sx={{ mr: 1 }}
                    />
                  )}
                  {item.discount && (
                    <Chip
                      icon={<PriceIcon />}
                      label={`-$${item.discount}`}
                      color="success"
                      size="small"
                    />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
};

export default ReceiptDetail; 