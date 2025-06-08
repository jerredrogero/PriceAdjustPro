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
  useTheme,
  useMediaQuery,
  Card,
  CardContent,
  Divider,
  Chip,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Edit as EditIcon,
  Save as SaveIcon,
  Cancel as CancelIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  TouchApp as SwipeIcon,
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
  original_total_price: string;
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
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editedItems, setEditedItems] = useState<ReceiptItem[]>([]);
  const [editedTransactionDate, setEditedTransactionDate] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [searchParams] = useSearchParams();
  const [showUploadSuccess, setShowUploadSuccess] = useState(false);
  const [priceAdjustmentsCreated, setPriceAdjustmentsCreated] = useState<number>(0);

  const fetchReceipt = useCallback(async () => {
    try {
      const response = await api.get(`/api/receipts/${transactionNumber}/`);
      setReceipt(response.data);
      setEditedItems(response.data.items.map((item: ReceiptItem) => ({
        ...item,
        original_total_price: item.total_price || (parseFloat(item.price) * item.quantity).toFixed(2),
        // Auto-check "on_sale" if item has instant_savings
        on_sale: Boolean(item.on_sale || (item.instant_savings && parseFloat(item.instant_savings) > 0))
      })));
      // Set the transaction date for editing (convert to YYYY-MM-DDTHH:MM format for datetime-local input)
      const isoDate = new Date(response.data.transaction_date).toISOString().slice(0, 16);
      setEditedTransactionDate(isoDate);
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
    
    if (field === 'price') {
      const priceValue = value && value !== '' ? parseFloat(value) : 0;
      const currentSavings = newItems[index].instant_savings ? parseFloat(newItems[index].instant_savings!) : 0;
      newItems[index] = {
        ...newItems[index],
        price: value,
        // Calculate original price as current price + savings
        original_price: currentSavings > 0 ? (priceValue + currentSavings).toFixed(2) : null
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
    } else if (field === 'quantity') {
      // When quantity changes, calculate per-unit price from total price
      const newQuantity = parseInt(value) || 1;
      const originalTotalPrice = parseFloat(newItems[index].original_total_price || newItems[index].total_price || (parseFloat(newItems[index].price) * newItems[index].quantity).toString());
      const perUnitPrice = originalTotalPrice / newQuantity;
      
      newItems[index] = {
        ...newItems[index],
        quantity: newQuantity,
        price: perUnitPrice.toFixed(2), // Store per-unit price
        total_price: originalTotalPrice.toFixed(2) // Keep original total price
      };
    } else {
      newItems[index] = {
        ...newItems[index],
        [field]: value
      };
    }
    
    setEditedItems(newItems);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const saveData = {
        transaction_number: transactionNumber,
        store_location: receipt?.store_location,
        store_number: receipt?.store_number,
        transaction_date: new Date(editedTransactionDate).toISOString(),
        items: editedItems.map(item => ({
          ...item,
          price: parseFloat(item.price).toFixed(2),
          total_price: item.original_total_price || item.total_price || (parseFloat(item.price) * item.quantity).toFixed(2), // Preserve original total
          instant_savings: item.instant_savings ? parseFloat(item.instant_savings).toFixed(2) : null,
          original_price: item.original_price ? parseFloat(item.original_price).toFixed(2) : null
        })),
        total_items_sold: editedItems.reduce((sum, item) => sum + item.quantity, 0),
        subtotal: calculateSubtotal(),
        tax: receipt?.tax,
        total: calculateTotal(),
        instant_savings: calculateTotalSavings()
      };
      
      console.log('Saving data:', saveData); // Debug: what we're sending
      console.log('Original editedItems:', editedItems); // Debug: current state
      
      const response = await api.post(`/api/receipts/${transactionNumber}/update/`, saveData);
      
      console.log('Save response:', response.data); // Debug logging
      
      // Check if price adjustments were created
      const adjustmentsCreated = response.data.price_adjustments_created || 0;
      setPriceAdjustmentsCreated(adjustmentsCreated);
      
      setEditMode(false);
      
      console.log('About to refresh data...'); // Debug
      await fetchReceipt(); // Refresh data
      console.log('Data refreshed'); // Debug
      
    } catch (err: any) {
      setError('Failed to save changes');
      console.error('Save error:', err);
      console.error('Error details:', err.response?.data); // Better error logging
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
      original_price: null,
      original_total_price: '0.00'
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
      // Use per-unit price * quantity for accurate calculation
      const perUnitPrice = parseFloat(item.price);
      const quantity = item.quantity;
      return sum + (perUnitPrice * quantity);
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
                setEditedItems(receipt.items.map(item => ({
                  ...item,
                  original_total_price: item.total_price || (parseFloat(item.price) * item.quantity).toFixed(2),
                  // Auto-check "on_sale" if item has instant_savings
                  on_sale: Boolean(item.on_sale || (item.instant_savings && parseFloat(item.instant_savings) > 0))
                })));
                // Reset transaction date to original
                const isoDate = new Date(receipt.transaction_date).toISOString().slice(0, 16);
                setEditedTransactionDate(isoDate);
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
          severity="warning" 
          sx={{ mb: 3, border: '2px solid #ed6c02' }}
          onClose={() => setShowUploadSuccess(false)}
        >
          <Typography variant="h6" sx={{ mb: 1, fontWeight: 'bold' }}>
            ⚠️ IMPORTANT: Please Verify All Receipt Data
          </Typography>
          <Typography variant="body2" sx={{ mb: 2 }}>
            Receipt parsing is automated but <strong>may contain errors</strong>. Please carefully review and correct:
          </Typography>
          <Box component="ul" sx={{ mb: 2, pl: 2 }}>
            <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
              <strong>Item Quantities:</strong> Costco receipts don't show quantities - verify each item count
            </Typography>
            <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
              <strong>Prices:</strong> Ensure per-unit prices are correct (divide total by quantity if needed)
            </Typography>
            <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
              <strong>Sale Items:</strong> Mark items as "on sale" and enter savings amount if you got discounts
            </Typography>
            <Typography component="li" variant="body2" sx={{ mb: 0.5 }}>
              <strong>Item Codes & Descriptions:</strong> Verify these match your receipt
            </Typography>
            <Typography component="li" variant="body2">
              <strong>Transaction Details:</strong> Check store location, date, and totals
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 2, bgcolor: 'rgba(237, 108, 2, 0.1)', borderRadius: 1 }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
              👉 Use the "Edit Receipt" button below to make corrections
            </Typography>
          </Box>
        </Alert>
      )}

      {priceAdjustmentsCreated > 0 && (
        <Alert 
          severity="success" 
          sx={{ mb: 3 }}
          onClose={() => setPriceAdjustmentsCreated(0)}
        >
          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
            Receipt Updated Successfully! ✅
          </Typography>
          <Typography variant="body2">
            Your receipt data has been saved and is now helping the community find better deals.
          </Typography>
        </Alert>
      )}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h5" gutterBottom>
          {receipt.store_location}
        </Typography>
        <Typography variant="subtitle1" gutterBottom>
          Transaction #: {receipt.transaction_number && 
                          receipt.transaction_number !== 'null' && 
                          !receipt.transaction_number.toLowerCase().includes('null')
            ? receipt.transaction_number 
            : 'Not found on receipt'}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="subtitle1">
            Date:
          </Typography>
          {editMode ? (
            <TextField
              type="datetime-local"
              value={editedTransactionDate}
              onChange={(e) => setEditedTransactionDate(e.target.value)}
              variant="outlined"
              size="small"
              sx={{ minWidth: 200 }}
              InputLabelProps={{
                shrink: true,
              }}
            />
          ) : (
            <Typography variant="subtitle1">
              {format(new Date(receipt.transaction_date), 'PPPp')}
            </Typography>
          )}
        </Box>
        
      </Paper>

      {/* Mobile Card Layout */}
      {isMobile ? (
        <Box sx={{ mb: 3 }}>
          {editedItems.map((item, index) => (
            <Card key={item.id} sx={{ mb: 2, position: 'relative' }}>
              <CardContent sx={{ pb: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    {editMode ? (
                      <>
                        <TextField
                          fullWidth
                          value={item.description}
                          onChange={(e) => handleItemChange(index, 'description', e.target.value)}
                          variant="outlined"
                          size="small"
                          label="Description"
                          sx={{ mb: 1 }}
                        />
                        <TextField
                          value={item.item_code}
                          onChange={(e) => handleItemChange(index, 'item_code', e.target.value)}
                          variant="outlined"
                          size="small"
                          label="Item Code"
                          sx={{ width: '140px' }}
                        />
                      </>
                    ) : (
                      <>
                        <Typography variant="subtitle1" sx={{ fontWeight: 500, mb: 0.5 }}>
                          {item.description}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          #{item.item_code}
                        </Typography>
                      </>
                    )}
                  </Box>
                  {editMode && (
                    <IconButton
                      onClick={() => removeItem(index)}
                      color="error"
                      size="small"
                      sx={{ ml: 1 }}
                    >
                      <DeleteIcon />
                    </IconButton>
                  )}
                </Box>

                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 2 }}>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="caption" color="text.secondary">Price</Typography>
                    {editMode ? (
                      <TextField
                        type="number"
                        value={item.price}
                        onChange={(e) => handleItemChange(index, 'price', e.target.value)}
                        variant="outlined"
                        size="small"
                        fullWidth
                        inputProps={{ min: 0, step: 0.01 }}
                      />
                    ) : (
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {formatCurrency(item.price)}
                      </Typography>
                    )}
                  </Box>
                  
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Quantity
                      {editMode && (
                        <Typography component="span" variant="caption" color="warning.main" sx={{ ml: 0.5, fontWeight: 'bold' }}>
                          ⚠️
                        </Typography>
                      )}
                    </Typography>
                    {editMode ? (
                      <TextField
                        type="number"
                        value={item.quantity}
                        onChange={(e) => handleItemChange(index, 'quantity', parseInt(e.target.value))}
                        variant="outlined"
                        size="small"
                        fullWidth
                        inputProps={{ min: 1 }}
                      />
                    ) : (
                      <Typography variant="body1" sx={{ fontWeight: 500 }}>
                        {item.quantity}
                      </Typography>
                    )}
                  </Box>

                  <Box sx={{ flex: 1 }}>
                    <Typography variant="caption" color="text.secondary">Total</Typography>
                    <Typography variant="body1" sx={{ fontWeight: 500, color: 'primary.main' }}>
                      {formatCurrency(item.original_total_price || item.total_price || (parseFloat(item.price) * item.quantity).toFixed(2))}
                    </Typography>
                  </Box>
                </Box>

                {editMode && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Checkbox
                        checked={item.on_sale}
                        onChange={(e) => handleItemChange(index, 'on_sale', e.target.checked)}
                        size="small"
                      />
                      <Typography variant="body2">On Sale</Typography>
                    </Box>
                    {item.on_sale && (
                      <TextField
                        type="number"
                        placeholder="0.00"
                        value={item.instant_savings || ''}
                        onChange={(e) => handleItemChange(index, 'instant_savings', e.target.value)}
                        variant="outlined"
                        size="small"
                        label="$ Saved"
                        sx={{ width: '100px' }}
                        inputProps={{ min: 0, step: 0.01 }}
                      />
                    )}
                  </Box>
                )}

                {item.instant_savings && !editMode && (
                  <Box sx={{ mt: 1 }}>
                    <Chip
                      label={`🏷️ On Sale: ${formatCurrency(item.instant_savings)}`}
                      color="success"
                      size="small"
                      variant="outlined"
                    />
                    {item.original_price && (
                      <Typography 
                        variant="caption" 
                        color="text.secondary" 
                        sx={{ textDecoration: 'line-through', ml: 1 }}
                      >
                        Was: {formatCurrency(item.original_price)}
                      </Typography>
                    )}
                  </Box>
                )}
              </CardContent>
            </Card>
          ))}
          
          {/* Mobile totals card */}
          <Card sx={{ mt: 2, backgroundColor: 'primary.main', color: 'primary.contrastText' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography>Subtotal:</Typography>
                <Typography>{formatCurrency(calculateSubtotal())}</Typography>
              </Box>
              {(parseFloat(calculateTotalSavings()) > 0 || receipt.instant_savings) && (
                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                  <Typography color="success.light">Instant Savings:</Typography>
                  <Typography color="success.light">
                    -{formatCurrency(editMode ? calculateTotalSavings() : (receipt.instant_savings || '0'))}
                  </Typography>
                </Box>
              )}
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                <Typography>Tax:</Typography>
                <Typography>{formatCurrency(receipt.tax)}</Typography>
              </Box>
              <Divider sx={{ my: 1, borderColor: 'primary.contrastText', opacity: 0.3 }} />
              <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="h6">Total:</Typography>
                <Typography variant="h6">{formatCurrency(calculateTotal())}</Typography>
              </Box>
            </CardContent>
          </Card>
        </Box>
      ) : (
        /* Desktop Table Layout with scroll indicators */
        <Box sx={{ position: 'relative' }}>
          {/* Scroll indicator for desktop when needed */}
          <Box sx={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: 1, 
            mb: 1,
            color: 'text.secondary',
            fontSize: '0.875rem'
          }}>
            <SwipeIcon fontSize="small" />
            <Typography variant="caption">
              Scroll horizontally to see all columns
            </Typography>
          </Box>
          
          <TableContainer 
            component={Paper} 
            sx={{ 
              overflowX: 'auto',
              '&::-webkit-scrollbar': {
                height: 8,
              },
              '&::-webkit-scrollbar-track': {
                backgroundColor: 'grey.100',
                borderRadius: 4,
              },
              '&::-webkit-scrollbar-thumb': {
                backgroundColor: 'grey.400',
                borderRadius: 4,
                '&:hover': {
                  backgroundColor: 'grey.600',
                },
              },
            }}
          >
            <Table sx={{ minWidth: editMode ? 800 : 600 }}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ minWidth: 100 }}>Item Code</TableCell>
                  <TableCell sx={{ minWidth: 200 }}>Description</TableCell>
                  <TableCell align="right" sx={{ minWidth: 80 }}>Price</TableCell>
                  <TableCell align="right" sx={{ minWidth: 80 }}>
                    Quantity
                    {editMode && (
                      <Typography variant="caption" color="warning.main" display="block" sx={{ fontSize: '0.7rem', fontWeight: 'bold' }}>
                        ⚠️ Verify Count
                      </Typography>
                    )}
                  </TableCell>
                  {editMode && <TableCell align="center" sx={{ minWidth: 120 }}>On Sale</TableCell>}
                  <TableCell align="right" sx={{ minWidth: 100 }}>Total</TableCell>
                  {editMode && <TableCell align="right" sx={{ minWidth: 80 }}>Actions</TableCell>}
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
                  <TableCell align="center" sx={{ minWidth: 120, maxWidth: 150 }}>
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                      <Checkbox
                        checked={item.on_sale}
                        onChange={(e) => handleItemChange(index, 'on_sale', e.target.checked)}
                        size="small"
                      />
                      {item.on_sale && (
                        <TextField
                          type="number"
                          placeholder="0.00"
                          value={item.instant_savings || ''}
                          onChange={(e) => handleItemChange(index, 'instant_savings', e.target.value)}
                          variant="standard"
                          size="small"
                          inputProps={{ 
                            min: 0, 
                            step: 0.01, 
                            style: { textAlign: 'center' },
                            'aria-label': 'Sale amount'
                          }}
                          sx={{ 
                            mt: 0.5, 
                            width: '70px',
                            '& .MuiInput-input': {
                              fontSize: '0.875rem'
                            }
                          }}
                          helperText="$ saved"
                          FormHelperTextProps={{
                            sx: { fontSize: '0.7rem' }
                          }}
                        />
                      )}
                    </Box>
                  </TableCell>
                )}
                <TableCell align="right">
                  {formatCurrency(item.original_total_price || item.total_price || (parseFloat(item.price) * item.quantity).toFixed(2))}
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
        </Box>
      )}

      {/* Mobile Add Item Button */}
      {isMobile && editMode && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={addNewItem}
            fullWidth
            sx={{ maxWidth: 300 }}
          >
            Add Missing Item
          </Button>
        </Box>
      )}
    </Container>
  );
};

export default ReceiptDetail; 