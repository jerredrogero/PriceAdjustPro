import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
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
  Checkbox,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
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
  on_sale: boolean;
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
  instant_savings: string | null;
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
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedItems, setEditedItems] = useState<ReceiptItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [searchParams] = useSearchParams();
  const [showUploadSuccess, setShowUploadSuccess] = useState(false);

  const fetchReceipt = useCallback(async () => {
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
  }, [transactionNumber]);

  useEffect(() => {
    fetchReceipt();
    // Check if this is a fresh upload
    if (searchParams.get('uploaded') === 'true') {
      setShowUploadSuccess(true);
    }
  }, [fetchReceipt, searchParams]);

  const handleItemChange = (index: number, field: keyof ReceiptItem, value: any) => {
    const newItems = [...editedItems];
    
    // Handle special cases for on_sale and instant_savings
    if (field === 'on_sale') {
      newItems[index] = {
        ...newItems[index],
        [field]: value,
        // Clear savings and original price when unchecking on_sale
        instant_savings: value ? newItems[index].instant_savings : null,
        original_price: value ? newItems[index].original_price : null
      };
    } else if (field === 'instant_savings') {
      const savingsAmount = value && value !== '' ? parseFloat(value) : 0;
      const currentPrice = parseFloat(newItems[index].price);
      newItems[index] = {
        ...newItems[index],
        instant_savings: value && value !== '' ? value : null,
        // Calculate original price as current price + savings
        original_price: savingsAmount > 0 ? (currentPrice + savingsAmount).toFixed(2) : null
      };
    } else {
      newItems[index] = {
        ...newItems[index],
        [field]: value,
        total_price: field === 'price' || field === 'quantity' 
          ? (parseFloat(field === 'price' ? value : newItems[index].price) * 
             (field === 'quantity' ? value : newItems[index].quantity)).toFixed(2)
          : newItems[index].total_price
      };
    }
    
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
          total_price: (parseFloat(item.price) * item.quantity).toFixed(2),
          instant_savings: item.instant_savings ? parseFloat(item.instant_savings).toFixed(2) : null,
          original_price: item.original_price ? parseFloat(item.original_price).toFixed(2) : null
        })),
        total_items_sold: editedItems.reduce((sum, item) => sum + item.quantity, 0),
        subtotal: calculateSubtotal(),
        tax: receipt?.tax,
        total: calculateTotal(),
        instant_savings: calculateTotalSavings()
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

  const addNewItem = () => {
    const newItem: ReceiptItem = {
      id: Date.now(), // Temporary ID for new items
      item_code: '',
      description: '',
      price: '0.00',
      quantity: 1,
      total_price: '0.00',
      is_taxable: true,
      on_sale: false,
      instant_savings: null,
      original_price: null
    };
    setEditedItems(prev => [...prev, newItem]);
  };

  const removeItem = (index: number) => {
    setEditedItems(prev => prev.filter((_, i) => i !== index));
  };

  if (loading) return <LinearProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!receipt) return <Alert severity="error">Receipt not found</Alert>;

  const calculateSubtotal = () => {
    return editedItems.reduce((sum, item) => {
      // Use the actual price paid (already accounts for discounts)
      return sum + (parseFloat(item.price) * item.quantity);
    }, 0).toFixed(2);
  };

  const calculateTotal = () => {
    const subtotal = parseFloat(calculateSubtotal());
    const totalSavings = parseFloat(calculateTotalSavings());
    const tax = parseFloat(receipt.tax);
    return (subtotal - totalSavings + tax).toFixed(2);
  };

  const calculateTotalSavings = () => {
    return editedItems.reduce((sum, item) => {
      const savings = item.instant_savings ? parseFloat(item.instant_savings) : 0;
      return sum + (isNaN(savings) ? 0 : savings);
    }, 0).toFixed(2);
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

      {showUploadSuccess && (
        <Alert 
          severity="success" 
          sx={{ mb: 3 }}
          onClose={() => setShowUploadSuccess(false)}
        >
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Receipt uploaded successfully! 🎉
          </Typography>
          <Typography variant="body2">
            Please review the extracted details below and use the "Edit Receipt" button to make any corrections if needed. 
            Accurate data ensures better price adjustment tracking.
          </Typography>
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          {receipt.store_location}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          Transaction #: {receipt.transaction_number && receipt.transaction_number !== 'null' 
            ? receipt.transaction_number 
            : 'Not found on receipt'}
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
              {editMode && <TableCell align="center">On Sale</TableCell>}
              <TableCell align="right">Total</TableCell>
              {editMode && <TableCell align="right">Actions</TableCell>}
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
                {editMode && (
                  <TableCell align="center">
                    <Checkbox
                      checked={item.on_sale}
                      onChange={(e) => handleItemChange(index, 'on_sale', e.target.checked)}
                    />
                    {item.on_sale && (
                      <TextField
                        type="number"
                        placeholder="Sale amount"
                        value={item.instant_savings || ''}
                        onChange={(e) => handleItemChange(index, 'instant_savings', e.target.value)}
                        variant="standard"
                        size="small"
                        inputProps={{ min: 0, step: 0.01, style: { textAlign: 'center' } }}
                        sx={{ mt: 1, width: '80px' }}
                        helperText="$ saved"
                      />
                    )}
                  </TableCell>
                )}
                <TableCell align="right">
                  {formatCurrency(item.total_price)}
                  {item.instant_savings && (
                    <Typography variant="caption" color="success.main" display="block">
                      🏷️ On Sale: {formatCurrency(item.instant_savings)}
                    </Typography>
                  )}
                  {item.instant_savings && item.original_price && (
                    <Typography 
                      variant="caption" 
                      color="text.secondary" 
                      display="block"
                      sx={{ textDecoration: 'line-through' }}
                    >
                      Was: {formatCurrency(item.original_price)}
                    </Typography>
                  )}
                </TableCell>
                {editMode && (
                  <TableCell align="right">
                    <IconButton
                      onClick={() => removeItem(index)}
                      color="error"
                      size="small"
                      title="Remove Item"
                    >
                      <DeleteIcon />
                    </IconButton>
                  </TableCell>
                )}
              </TableRow>
            ))}
            <TableRow>
              {editMode ? (
                <>
                  <TableCell colSpan={5} />
                  <TableCell align="right">
                    <Typography variant="subtitle1">
                      Subtotal: {formatCurrency(calculateSubtotal())}
                    </Typography>
                    {(parseFloat(calculateTotalSavings()) > 0 || receipt.instant_savings) && (
                      <Typography variant="subtitle1" color="success.main">
                        Instant Savings: -{formatCurrency(editMode ? calculateTotalSavings() : (receipt.instant_savings || '0'))}
                      </Typography>
                    )}
                    <Typography variant="subtitle1">
                      Tax: {formatCurrency(receipt.tax)}
                    </Typography>
                    <Typography variant="h6">
                      Total: {formatCurrency(calculateTotal())}
                    </Typography>
                  </TableCell>
                  <TableCell />
                </>
              ) : (
                <>
                  <TableCell colSpan={4} />
                  <TableCell align="right">
                    <Typography variant="subtitle1">
                      Subtotal: {formatCurrency(calculateSubtotal())}
                    </Typography>
                    {(parseFloat(calculateTotalSavings()) > 0 || receipt.instant_savings) && (
                      <Typography variant="subtitle1" color="success.main">
                        Instant Savings: -{formatCurrency(editMode ? calculateTotalSavings() : (receipt.instant_savings || '0'))}
                      </Typography>
                    )}
                    <Typography variant="subtitle1">
                      Tax: {formatCurrency(receipt.tax)}
                    </Typography>
                    <Typography variant="h6">
                      Total: {formatCurrency(calculateTotal())}
                    </Typography>
                  </TableCell>
                </>
              )}
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>

      {editMode && (
        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'center' }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={addNewItem}
            sx={{ px: 3 }}
          >
            Add Missing Item
          </Button>
        </Box>
      )}
    </Container>
  );
};

export default ReceiptDetail; 