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
  Divider,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  LocalOffer as PriceIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../api/axios';

interface ReceiptItem {
  id?: number;
  item_code: string;
  description: string;
  quantity: number;
  price: string;
  total_price: string;
  is_taxable: boolean;
  instant_savings: string | null;
  original_price: string | null;
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
  instant_savings?: string;
  ebt_amount?: string;
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
              <TableCell align="right">Sale</TableCell>
              <TableCell align="right">Total</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {receipt.items.map((item) => (
              <TableRow key={item.item_code}>
                <TableCell>{item.item_code}</TableCell>
                <TableCell>{item.description}</TableCell>
                <TableCell align="right">{item.quantity}</TableCell>
                <TableCell align="right">
                  ${item.price}
                  {item.original_price && (
                    <Typography variant="caption" color="text.secondary" display="block">
                      Was: ${item.original_price}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  {item.instant_savings ? (
                    <Chip
                      label={`Save $${item.instant_savings}`}
                      color="success"
                      size="small"
                      sx={{ fontWeight: 'medium' }}
                    />
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      -
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">${item.total_price}</TableCell>
              </TableRow>
            ))}

            <TableRow>
              <TableCell colSpan={6}>
                <Divider sx={{ my: 2 }} />
              </TableCell>
            </TableRow>

            <TableRow>
              <TableCell colSpan={4} align="right">
                <Typography variant="subtitle1">Subtotal</Typography>
              </TableCell>
              <TableCell align="right" colSpan={2}>
                <Typography variant="subtitle1">${receipt.subtotal}</Typography>
              </TableCell>
            </TableRow>

            {receipt.instant_savings && (
              <TableRow>
                <TableCell colSpan={4} align="right">
                  <Typography variant="subtitle1" color="success.main">
                    Total Instant Savings
                  </Typography>
                </TableCell>
                <TableCell align="right" colSpan={2}>
                  <Typography variant="subtitle1" color="success.main">
                    -${receipt.instant_savings}
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            <TableRow>
              <TableCell colSpan={4} align="right">
                <Typography variant="subtitle1">Tax</Typography>
              </TableCell>
              <TableCell align="right" colSpan={2}>
                <Typography variant="subtitle1">${receipt.tax}</Typography>
              </TableCell>
            </TableRow>

            {receipt.ebt_amount && (
              <TableRow>
                <TableCell colSpan={4} align="right">
                  <Typography variant="subtitle1" color="info.main">
                    EBT Amount
                  </Typography>
                </TableCell>
                <TableCell align="right" colSpan={2}>
                  <Typography variant="subtitle1" color="info.main">
                    ${receipt.ebt_amount}
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            <TableRow>
              <TableCell colSpan={4} align="right">
                <Typography variant="h6" color="primary.main">Total</Typography>
              </TableCell>
              <TableCell align="right" colSpan={2}>
                <Typography variant="h6" color="primary.main">${receipt.total}</Typography>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
};

export default ReceiptDetail; 