import React, { useState, useEffect } from 'react';
import { Link as RouterLink } from 'react-router-dom';
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
} from '@mui/material';
import { Receipt as ReceiptIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../api/axios';

interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  total: string;
  items_count: number;
  parsed_successfully: boolean;
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
  onDelete
}: { 
  receipt: Receipt;
  onDelete: (receipt: Receipt) => void;
}) => (
  <Card>
    <CardActionArea component={RouterLink} to={`/receipts/${receipt.transaction_number}`}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {receipt.store_location}
        </Typography>
        <Typography color="text.secondary" gutterBottom>
          {format(new Date(receipt.transaction_date), 'MMM d, yyyy')}
        </Typography>
        <Typography variant="h5" gutterBottom>
          ${receipt.total}
        </Typography>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Chip
            label={`${receipt.items_count} items`}
            size="small"
            color="primary"
            variant="outlined"
          />
          {!receipt.parsed_successfully && (
            <Chip
              label="Parse Warning"
              size="small"
              color="warning"
            />
          )}
        </Box>
        <Box sx={{ position: 'absolute', top: 8, right: 8 }}>
          <IconButton 
            onClick={(e) => {
              e.stopPropagation();
              e.preventDefault();
              onDelete(receipt);
            }}
            color="error"
            size="small"
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </Box>
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
      try {
        setLoading(true);
        setError('');
        setDebugInfo('');

        const response = await api.get('/api/receipts/');
        const data = response.data;

        // Debug logging
        console.log('API Response:', data);
        setDebugInfo(JSON.stringify(data, null, 2));

        if (!mounted) return;

        if (!data || typeof data !== 'object') {
          console.error('Invalid response format:', data);
          setReceipts([]);
          return;
        }

        const receiptsList = Array.isArray(data.receipts) ? data.receipts : [];
        const validReceipts = receiptsList.filter((item: any): item is Receipt => {
          if (!item || typeof item !== 'object') return false;
          const r = item as Partial<Receipt>;
          return (
            typeof r.transaction_number === 'string' &&
            typeof r.store_location === 'string' &&
            typeof r.store_number === 'string' &&
            typeof r.transaction_date === 'string' &&
            typeof r.total === 'string' &&
            typeof r.items_count === 'number' &&
            typeof r.parsed_successfully === 'boolean'
          );
        });

        if (mounted) {
          setReceipts(validReceipts);
        }
      } catch (err) {
        console.error('Error fetching receipts:', err);
        if (mounted) {
          setError(err instanceof Error ? err.message : 'Failed to load receipts');
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
          {receipts.map((receipt) => (
            <Grid item xs={12} sm={6} md={4} key={receipt.transaction_number}>
              <ReceiptCard 
                receipt={receipt}
                onDelete={handleDeleteClick}
              />
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