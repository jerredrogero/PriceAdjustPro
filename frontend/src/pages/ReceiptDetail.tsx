import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  IconButton,
  TextField,
  Alert,
  LinearProgress,
  useTheme,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../api/axios';

interface ReceiptItem {
  id: number;
  item_code: string;
  description: string;
  price: string;
  quantity: number;
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
}

const formatCurrency = (value: string | null | undefined): string => {
  if (!value) return '$0.00';
  const num = parseFloat(value);
  return num.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};

const ReceiptDetail: React.FC = () => {
  const { transactionNumber } = useParams<{ transactionNumber: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedItems, setEditedItems] = useState<ReceiptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchReceipt();
  }, [transactionNumber]);

  const fetchReceipt = async () => {
    try {
      const response = await api.get(`/api/receipts/${transactionNumber}/`);
      setReceipt(response.data);
      setEditedItems(response.data.items);
    } catch (err) {
      setError('Failed to load receipt details');
      console.error('Error fetching receipt:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleItemChange = (index: number, field: keyof ReceiptItem, value: any) => {
    const newItems = [...editedItems];
    newItems[index] = {
      ...newItems[index],
      [field]: value,
      total_price: field === 'price' || field === 'quantity' 
        ? (parseFloat(field === 'price' ? value : newItems[index].price) * 
           (field === 'quantity' ? value : newItems[index].quantity)).toFixed(2)
        : newItems[index].total_price
    };
    setEditedItems(newItems);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.post(`/api/receipts/${transactionNumber}/update/`, {
        transaction_number: transactionNumber,
        store_location: receipt?.store_location,
        store_number: receipt?.store_number,
        transaction_date: receipt?.transaction_date,
        items: editedItems.map(item => ({
          ...item,
          price: parseFloat(item.price).toFixed(2),
          total_price: (parseFloat(item.price) * item.quantity).toFixed(2)
        })),
        total_items_sold: editedItems.reduce((sum, item) => sum + item.quantity, 0),
        subtotal: editedItems.reduce((sum, item) => sum + parseFloat(item.total_price), 0).toFixed(2),
        tax: receipt?.tax,
        total: calculateTotal()
      });
      setEditMode(false);
      fetchReceipt(); // Refresh data
    } catch (err) {
      setError('Failed to save changes');
      console.error('Save error:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LinearProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!receipt) return <Alert severity="error">Receipt not found</Alert>;

  const calculateTotal = () => {
    const subtotal = editedItems.reduce((sum, item) => sum + parseFloat(item.total_price), 0);
    const tax = parseFloat(receipt.tax);
    return (subtotal + tax).toFixed(2);
  };

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button
          startIcon={<BackIcon />}
          onClick={() => navigate('/receipts')}
          variant="outlined"
        >
          Back to Receipts
        </Button>
        {!editMode ? (
          <Button
            startIcon={<EditIcon />}
            variant="contained"
            onClick={() => setEditMode(true)}
          >
            Edit Receipt
          </Button>
        ) : (
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              startIcon={<CancelIcon />}
              variant="outlined"
              onClick={() => {
                setEditMode(false);
                setEditedItems(receipt.items);
              }}
            >
              Cancel
            </Button>
            <Button
              startIcon={<SaveIcon />}
              variant="contained"
              onClick={handleSave}
              disabled={saving}
            >
              Save Changes
            </Button>
          </Box>
        )}
      </Box>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          {receipt.store_location}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          Transaction #: {receipt.transaction_number}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          Date: {format(new Date(receipt.transaction_date), 'PPPp')}
        </Typography>
      </Paper>

      {editMode && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          <Typography variant="body2">
            <strong>Beta Feature:</strong> Item number editing is enabled for testing. 
            Note that item numbers are used to match products across users for price adjustment alerts. 
            Incorrect item numbers may affect price matching accuracy.
          </Typography>
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Item Code</TableCell>
              <TableCell>Description</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Total</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {editedItems.map((item, index) => (
              <TableRow key={item.id}>
                <TableCell>
                  {editMode ? (
                    <TextField
                      value={item.item_code}
                      onChange={(e) => handleItemChange(index, 'item_code', e.target.value)}
                      variant="standard"
                      inputProps={{ style: { textAlign: 'center' } }}
                      sx={{ width: '120px' }}
                    />
                  ) : (
                    item.item_code
                  )}
                </TableCell>
                <TableCell>
                  {editMode ? (
                    <TextField
                      fullWidth
                      value={item.description}
                      onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                      variant="standard"
                    />
                  ) : (
                    item.description
                  )}
                </TableCell>
                <TableCell align="right">
                  {editMode ? (
                    <TextField
                      type="number"
                      value={item.price}
                      onChange={(e) => handleItemChange(index, 'price', e.target.value)}
                      variant="standard"
                      inputProps={{ min: 0, step: 0.01, style: { textAlign: 'right' } }}
                    />
                  ) : (
                    formatCurrency(item.price)
                  )}
                </TableCell>
                <TableCell align="right">
                  {editMode ? (
                    <TextField
                      type="number"
                      value={item.quantity}
                      onChange={(e) => handleItemChange(index, 'quantity', parseInt(e.target.value))}
                      variant="standard"
                      inputProps={{ min: 1, style: { textAlign: 'right' } }}
                    />
                  ) : (
                    item.quantity
                  )}
                </TableCell>
                <TableCell align="right">
                  {formatCurrency(item.total_price)}
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell colSpan={3} />
              <TableCell align="right">
                <Typography variant="subtitle1">Subtotal:</Typography>
                <Typography variant="subtitle1">Tax:</Typography>
                <Typography variant="h6">Total:</Typography>
              </TableCell>
              <TableCell align="right">
                <Typography variant="subtitle1">
                  {formatCurrency(editedItems.reduce((sum, item) => sum + parseFloat(item.total_price), 0).toString())}
                </Typography>
                <Typography variant="subtitle1">
                  {formatCurrency(receipt.tax)}
                </Typography>
                <Typography variant="h6">
                  {formatCurrency(calculateTotal())}
                </Typography>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Container>
  );
};

export default ReceiptDetail; 