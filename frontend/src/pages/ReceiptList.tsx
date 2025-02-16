import React, { useState, useEffect } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import {
  Container,
  Typography,
  Grid,
  Card,
  CardContent,
  CardActionArea,
  Chip,
  Box,
  LinearProgress,
  Alert,
  Button,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Tooltip,
  Paper,
  Fade,
} from '@mui/material';
import {
  Receipt as ReceiptIcon,
  Delete as DeleteIcon,
  Store as StoreIcon,
  DateRange as DateIcon,
  Warning as WarningIcon,
  Visibility as ViewIcon,
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
  instant_savings: string | null;
  original_price: string | null;
}

interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  total: string;
  items_count: number;
  parsed_successfully: boolean;
  items: ReceiptItem[];
  subtotal: string;
  tax: string;
  instant_savings: string | null;
}

interface ApiResponse {
  receipts: Receipt[];
  price_adjustments_count: number;
}

const EmptyState = () => (
  <Box sx={{ textAlign: 'center', py: 4 }}>
    <ReceiptIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 2 }} />
    <Typography color="text.secondary" gutterBottom>
      No receipts found
    </Typography>
    <Button
      variant="contained"
      color="primary"
      component={RouterLink}
      to="/upload"
      sx={{ mt: 2 }}
    >
      Upload Your First Receipt
    </Button>
  </Box>
);

const ReceiptCard = ({ 
  receipt,
  onDelete,
  navigate
}: { 
  receipt: Receipt;
  onDelete: (receipt: Receipt) => void;
  navigate: (path: string) => void;
}) => (
  <Card>
    <CardActionArea component={RouterLink} to={`/receipts/${receipt.transaction_number}`}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <StoreIcon color="primary" />
            <Box>
              <Typography variant="h6" component="div">
                Receipt #{receipt.transaction_number.slice(-4)}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {receipt.store_location}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Delete Receipt">
              <IconButton
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  onDelete(receipt);
                }}
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
                onClick={() => navigate(`/receipts/${receipt.transaction_number}`)}
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

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
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
          mt: 2,
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
              mt: 2,
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
      </CardContent>
    </CardActionArea>
  </Card>
);

const ReceiptList: React.FC = () => {
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [debugInfo, setDebugInfo] = useState('');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedReceipt, setSelectedReceipt] = useState<Receipt | null>(null);
  const navigate = useNavigate();

  const handleDeleteClick = (receipt: Receipt) => {
    setSelectedReceipt(receipt);
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedReceipt) return;

    try {
      await api.delete(`/api/receipts/${selectedReceipt.transaction_number}/delete/`);
      setReceipts(prev => prev.filter(r => r.transaction_number !== selectedReceipt.transaction_number));
    } catch (err) {
      console.error('Delete failed:', err);
    } finally {
      setDeleteDialogOpen(false);
      setSelectedReceipt(null);
    }
  };

  useEffect(() => {
    let mounted = true;

    const fetchReceipts = async () => {
      setLoading(true);
      try {
        const response = await api.get('/api/receipts/');
        console.log('API Response:', response.data); // Debug logging
        
        if (mounted) {
          if (response.data && Array.isArray(response.data.receipts)) {
            setReceipts(response.data.receipts);
            setError('');
            setDebugInfo('');
          } else {
            console.error('Invalid response format:', response.data);
            setError('Invalid response format from server');
            setDebugInfo(JSON.stringify(response.data, null, 2));
            setReceipts([]);
          }
        }
      } catch (err) {
        console.error('Error fetching receipts:', err);
        if (mounted) {
          setError('Failed to load receipts');
          setDebugInfo(err instanceof Error ? err.message : String(err));
          setReceipts([]);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    fetchReceipts();

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <LinearProgress />
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert 
          severity="error" 
          action={
            <Button color="inherit" size="small" onClick={() => window.location.reload()}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
        {debugInfo && (
          <Box sx={{ mt: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
            <Typography variant="subtitle2" gutterBottom>Debug Information:</Typography>
            <pre style={{ overflow: 'auto', maxHeight: '200px' }}>
              {debugInfo}
            </pre>
          </Box>
        )}
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">
          My Receipts
        </Typography>
        <Button 
          variant="contained" 
          color="primary" 
          component={RouterLink} 
          to="/upload"
        >
          Upload Receipt
        </Button>
      </Box>

      {(!Array.isArray(receipts) || receipts.length === 0) ? (
        <EmptyState />
      ) : (
        <Grid container spacing={3}>
          {receipts.map((receipt, index) => (
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
                  <ReceiptCard 
                    receipt={receipt}
                    onDelete={handleDeleteClick}
                    navigate={navigate}
                  />
                </Paper>
              </Fade>
            </Grid>
          ))}
        </Grid>
      )}

      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>Delete Receipt?</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete receipt {selectedReceipt?.transaction_number}?
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
          <Button 
            onClick={handleDeleteConfirm} 
            color="error"
            variant="contained"
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Container>
  );
};

export default ReceiptList; 