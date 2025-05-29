import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  CardContent,
  Typography,
  Grid,
  Chip,
  IconButton,
  Alert,
  Fade,
  Button,
  Skeleton,
  Container,
  Paper,
  Stack,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Warning as WarningIcon,
  Add as AddIcon,
  CalendarToday as DateIcon,
  Store as StoreIcon,
  ShoppingCart as CartIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import api from '../api/axios';
import PriceAdjustmentAlert from './PriceAdjustmentAlert';

interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  total: string;
  items_count: number;
  parsed_successfully: boolean;
  parse_error?: string;
}

interface PriceAdjustment {
  item_code: string;
  description: string;
  current_price: number;
  lower_price: number;
  price_difference: number;
  store_location: string;
  store_number: string;
  purchase_date: string;
  days_remaining: number;
  original_store: string;
  original_store_number: string;
  data_source: string;
  is_official: boolean;
  promotion_title?: string;
  sale_type?: string;
  confidence_level: string;
  transaction_number?: string;
}

const ReceiptList: React.FC = () => {
  const navigate = useNavigate();
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedReceipt, setSelectedReceipt] = useState<Receipt | null>(null);
  const [priceAdjustments, setPriceAdjustments] = useState<PriceAdjustment[]>([]);

  useEffect(() => {
    fetchReceipts();
    checkPriceAdjustments();
  }, []);

  const fetchReceipts = async () => {
    try {
      const response = await api.get('/api/receipts/');
      
      // Handle different API response structures
      const rawData = response.data;
      const receiptsArray = 
        Array.isArray(rawData) ? rawData :          // Direct array
        Array.isArray(rawData?.results) ? rawData.results :  // Paginated response
        Array.isArray(rawData?.data) ? rawData.data :  // Nested data
        [];  // Fallback

      setReceipts(receiptsArray);
      setError('');
    } catch (err) {
      setError('Failed to load receipts');
      console.error('Error fetching receipts:', err);
      setReceipts([]);  // Reset to empty array on error
    } finally {
      setLoading(false);
    }
  };

  const checkPriceAdjustments = async () => {
    try {
      const response = await api.get('/api/price-adjustments/');
      setPriceAdjustments(response.data.adjustments);
    } catch (err) {
      console.error('Error checking price adjustments:', err);
    }
  };

  const handleDismissAdjustment = (itemCode: string) => {
    setPriceAdjustments(current => current.filter(adj => adj.item_code !== itemCode));
  };

  const handleDeleteClick = (receipt: Receipt) => {
    // Validate transaction number before allowing delete
    if (!receipt.transaction_number || 
        receipt.transaction_number === 'N/A' || 
        receipt.transaction_number === 'null' || 
        receipt.transaction_number === '' ||
        receipt.transaction_number === 'None') {
      setError('Cannot delete receipt with invalid transaction number. Please refresh the page.');
      return;
    }
    
    setSelectedReceipt(receipt);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedReceipt) return;

    // Double-check transaction number before making API call
    if (!selectedReceipt.transaction_number || 
        selectedReceipt.transaction_number === 'N/A' || 
        selectedReceipt.transaction_number === 'null' || 
        selectedReceipt.transaction_number === '' ||
        selectedReceipt.transaction_number === 'None') {
      setError('Cannot delete receipt with invalid transaction number. Please refresh the page.');
      setDeleteDialogOpen(false);
      setSelectedReceipt(null);
      return;
    }

    try {
      await api.delete(`/api/receipts/${selectedReceipt.transaction_number}/delete/`);
      setReceipts(receipts.filter(r => r.transaction_number !== selectedReceipt.transaction_number));
      setDeleteDialogOpen(false);
      setSelectedReceipt(null);
    } catch (err: any) {
      console.error('Error deleting receipt:', err);
      
      // Provide more specific error messages
      if (err.response?.status === 404) {
        setError('Receipt not found. It may have already been deleted.');
        // Remove from local state since it doesn't exist on server
        setReceipts(receipts.filter(r => r.transaction_number !== selectedReceipt.transaction_number));
      } else {
        setError('Failed to delete receipt. Please try again.');
      }
      
      setDeleteDialogOpen(false);
      setSelectedReceipt(null);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Grid container spacing={3}>
          {[1, 2, 3].map((skeleton) => (
            <Grid item xs={12} sm={6} md={4} key={skeleton}>
              <Paper elevation={2} sx={{ height: '100%' }}>
                <CardContent>
                  <Stack spacing={2}>
                    <Skeleton variant="text" width="70%" height={32} />
                    <Skeleton variant="text" width="40%" />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Skeleton variant="text" width="30%" />
                      <Skeleton variant="rectangular" width={80} height={24} />
                    </Box>
                  </Stack>
                </CardContent>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert 
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={fetchReceipts}>
              Retry
            </Button>
          }
          sx={{ maxWidth: 600, mx: 'auto' }}
        >
          {error}
        </Alert>
      </Container>
    );
  }

  if (receipts.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Fade in>
          <Paper 
            elevation={3}
            sx={{ 
              textAlign: 'center', 
              p: 6, 
              maxWidth: 500,
              mx: 'auto',
              borderRadius: 4,
              background: 'linear-gradient(to bottom right, #ffffff, #f5f5f5)'
            }}
          >
            <CartIcon sx={{ fontSize: 64, color: 'primary.main', mb: 3, opacity: 0.8 }} />
            <Typography variant="h4" color="text.primary" gutterBottom fontWeight="medium">
              No Receipts Yet
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 400, mx: 'auto' }}>
              Start tracking your expenses by uploading your first receipt. We'll help you organize and analyze your spending.
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => navigate('/upload')}
              size="large"
              sx={{
                px: 4,
                py: 1.5,
                borderRadius: 2,
                textTransform: 'none',
                fontSize: '1.1rem',
                boxShadow: 2,
                '&:hover': {
                  boxShadow: 4,
                },
              }}
            >
              Upload Your First Receipt
            </Button>
          </Paper>
        </Fade>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <PriceAdjustmentAlert 
        adjustments={priceAdjustments}
        onDismiss={handleDismissAdjustment}
      />

      <Box sx={{ mb: 5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1" fontWeight="medium">
          Your Receipts
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/upload')}
          sx={{
            px: 3,
            py: 1,
            borderRadius: 2,
            textTransform: 'none',
            boxShadow: 2,
            '&:hover': {
              boxShadow: 4,
            },
          }}
        >
          Upload New
        </Button>
      </Box>

      <Grid container spacing={3}>
        {(receipts || []).slice(0, 10)
          .map((receipt, index) => (
            <Grid item xs={12} sm={6} md={4} key={receipt.transaction_number}>
              <Fade in timeout={300} style={{ transitionDelay: `${index * 100}ms` }}>
                <Paper 
                  elevation={2}
                  sx={{
                    height: '100%',
                    borderRadius: 3,
                    transition: 'all 0.3s ease-in-out',
                    '&:hover': {
                      transform: 'translateY(-4px)',
                      boxShadow: 6,
                    },
                  }}
                >
                  <CardContent sx={{ p: 3 }}>
                    <Stack spacing={2}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <StoreIcon color="primary" />
                          <Box>
                            <Typography variant="h6" component="div">
                              Costco #{receipt.transaction_number.slice(-4)}
                              {(!receipt.parsed_successfully || receipt.parse_error) && (
                                <Tooltip title={receipt.parse_error || "Parsing issues detected - please review"}>
                                  <WarningIcon 
                                    sx={{ 
                                      ml: 1, 
                                      fontSize: 16, 
                                      color: 'warning.main',
                                      verticalAlign: 'middle'
                                    }} 
                                  />
                                </Tooltip>
                              )}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {receipt.store_location}
                            </Typography>
                          </Box>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                          <Tooltip title="Delete Receipt">
                            <IconButton
                              onClick={() => handleDeleteClick(receipt)}
                              color="error"
                              sx={{
                                backgroundColor: 'action.hover',
                                '&:hover': {
                                  backgroundColor: 'error.main',
                                  color: 'error.contrastText',
                                },
                              }}
                            >
                              <DeleteIcon />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="View Details">
                            <IconButton
                              onClick={() => {
                                // Validate transaction number before navigation
                                if (!receipt.transaction_number || 
                                    receipt.transaction_number === 'N/A' || 
                                    receipt.transaction_number === 'null' || 
                                    receipt.transaction_number === '' ||
                                    receipt.transaction_number === 'None') {
                                  setError('Cannot view receipt with invalid transaction number. Please refresh the page.');
                                  return;
                                }
                                navigate(`/receipt/${receipt.transaction_number}`);
                              }}
                              color="primary"
                              sx={{
                                backgroundColor: 'action.hover',
                                '&:hover': {
                                  backgroundColor: 'primary.main',
                                  color: 'primary.contrastText',
                                },
                              }}
                            >
                              <ViewIcon />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </Box>

                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <DateIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                        <Typography color="text.secondary">
                          {new Date(receipt.transaction_date).toLocaleDateString(undefined, {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                          })}
                        </Typography>
                      </Box>

                      <Box sx={{ 
                        display: 'flex', 
                        justifyContent: 'space-between', 
                        alignItems: 'center',
                        backgroundColor: 'primary.main',
                        color: 'primary.contrastText',
                        p: 1.5,
                        borderRadius: 2,
                      }}>
                        <Typography variant="h6" component="div">
                          ${receipt.total}
                        </Typography>
                        <Chip
                          label={`${receipt.items_count} items`}
                          size="small"
                          sx={{ 
                            backgroundColor: 'rgba(255, 255, 255, 0.2)',
                            color: 'inherit',
                            '.MuiChip-label': {
                              fontWeight: 500,
                            },
                          }}
                        />
                      </Box>

                      {!receipt.parsed_successfully && (
                        <Alert
                          severity="warning"
                          icon={<WarningIcon />}
                          sx={{ 
                            borderRadius: 2,
                            '& .MuiAlert-icon': {
                              color: 'warning.dark',
                            },
                          }}
                        >
                          <Typography variant="body2">
                            Parse warning
                          </Typography>
                        </Alert>
                      )}
                    </Stack>
                  </CardContent>
                </Paper>
              </Fade>
            </Grid>
          ))}
      </Grid>

      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        aria-labelledby="delete-dialog-title"
      >
        <DialogTitle id="delete-dialog-title">
          Delete Receipt
        </DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete this receipt? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button onClick={handleDeleteConfirm} color="error" variant="contained">
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ReceiptList; 