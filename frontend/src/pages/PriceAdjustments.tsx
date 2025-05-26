import React, { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Grid,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Alert,
  Button,
  useTheme,
  IconButton,
  Tooltip,
  Snackbar,
} from '@mui/material';
import {
  LocationOn as LocationIcon,
  CalendarToday as CalendarIcon,
  Timer as TimerIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import api from '../api/axios';

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
}

interface ApiResponse {
  adjustments: PriceAdjustment[];
  total_potential_savings: number;
}

const PriceAdjustments: React.FC = () => {
  const theme = useTheme();
  const [adjustments, setAdjustments] = useState<PriceAdjustment[]>([]);
  const [totalSavings, setTotalSavings] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dismissing, setDismissing] = useState<string | null>(null);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState('');

  useEffect(() => {
    fetchAdjustments();
  }, []);

  const fetchAdjustments = async () => {
    try {
      const response = await api.get('/api/price-adjustments/');
      setAdjustments(response.data.adjustments);
      setTotalSavings(response.data.total_potential_savings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleDismissAdjustment = async (itemCode: string) => {
    setDismissing(itemCode);
    try {
      await api.post(`/api/price-adjustments/dismiss/${itemCode}/`);
      
      // Remove the dismissed adjustment from the list
      setAdjustments(prev => {
        const updated = prev.filter(adj => adj.item_code !== itemCode);
        // Recalculate total savings
        const newTotal = updated.reduce((sum, adj) => sum + adj.price_difference, 0);
        setTotalSavings(newTotal);
        return updated;
      });
      
      setSnackbarMessage('Price adjustment alert dismissed successfully');
      setSnackbarOpen(true);
    } catch (err) {
      console.error('Error dismissing price adjustment:', err);
      setSnackbarMessage('Failed to dismiss price adjustment alert');
      setSnackbarOpen(true);
    } finally {
      setDismissing(null);
    }
  };

  if (loading) return <LinearProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (adjustments.length === 0) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h5" gutterBottom>
            Price Adjustment Policy
          </Typography>
          <Typography color="text.secondary" paragraph>
            Costco offers price adjustments within 30 days of purchase. If an item you bought goes on sale within 30 days, you can request a refund for the difference.
          </Typography>
          
          {/* How to Request Price Adjustments */}
          <Alert severity="info" sx={{ mb: 3, textAlign: 'left' }}>
            <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
              How to Request a Price Adjustment:
            </Typography>
            <Typography variant="body2" paragraph>
              To request a price adjustment for something you bought in the warehouse, just visit the Returns desk at the Costco location where you made the purchase. For online purchases, complete the price adjustment request form online.
            </Typography>
            <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
              <strong>Note:</strong> Costco will never match their in-store prices to online prices and vice versa. Costco's online prices are usually a little higher to cover shipping and handling costs.
            </Typography>
          </Alert>

          <Alert severity="success">
            No price adjustments available at this time. We'll notify you when we find better prices!
          </Alert>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Paper sx={{ p: 4, mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Price Adjustment Opportunities
        </Typography>
        <Typography color="text.secondary" paragraph>
          Costco offers price adjustments within 30 days of purchase. When an item you bought goes on sale within 30 days, 
          you can request a refund for the difference. Below are your current opportunities for price adjustments.
        </Typography>
        
        {/* How to Request Price Adjustments */}
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
            How to Request Your Price Adjustment:
          </Typography>
          <Typography variant="body2" paragraph>
            To request a price adjustment for something you bought in the warehouse, just visit the Returns desk at the Costco location where you made the purchase. For online purchases, complete the price adjustment request form online.
          </Typography>
          <Typography variant="body2" sx={{ fontStyle: 'italic' }}>
            <strong>Note:</strong> Costco will never match their in-store prices to online prices and vice versa. Costco's online prices are usually a little higher to cover shipping and handling costs.
          </Typography>
        </Alert>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mt: 2 }}>
          <Typography variant="h6">
            Total Potential Savings:
          </Typography>
          <Chip
            label={`$${totalSavings.toFixed(2)}`}
            color="success"
            sx={{ 
              fontWeight: 'bold',
              fontSize: '1.2rem',
              height: 'auto',
              padding: '12px 16px',
              '& .MuiChip-label': {
                padding: '0',
              },
            }}
          />
        </Box>
      </Paper>

      <Grid container spacing={3}>
        {adjustments.map((adjustment) => (
          <Grid item xs={12} key={adjustment.item_code}>
            <Card>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h6" gutterBottom>
                      {adjustment.description}
                    </Typography>
                    
                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      <Grid item xs={12} sm={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <LocationIcon color="action" />
                          <Typography variant="body2">
                            Original Purchase: {adjustment.original_store} #{adjustment.original_store_number}
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CalendarIcon color="action" />
                          <Typography variant="body2">
                            Purchased: {format(new Date(adjustment.purchase_date), 'MMM d, yyyy')}
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                      <Typography variant="body1">
                        Original Price: ${adjustment.current_price.toFixed(2)}
                      </Typography>
                      <Typography variant="body1" color="success.main" sx={{ fontWeight: 'bold' }}>
                        Sale Price: ${adjustment.lower_price.toFixed(2)}
                      </Typography>
                      <Chip
                        label={`Save $${adjustment.price_difference.toFixed(2)}`}
                        color="success"
                        size="small"
                      />
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <LocationIcon color="success" />
                      <Typography variant="body2" color="success.main">
                        Available at: {adjustment.store_location} #{adjustment.store_number}
                      </Typography>
                    </Box>
                  </Box>

                  <Box sx={{ textAlign: 'right' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <TimerIcon color="warning" />
                      <Typography variant="body2" color="warning.main">
                        {adjustment.days_remaining} days remaining
                      </Typography>
                    </Box>
                    <Tooltip title="Dismiss this price adjustment alert">
                      <IconButton
                        onClick={() => handleDismissAdjustment(adjustment.item_code)}
                        disabled={dismissing === adjustment.item_code}
                        color="default"
                        size="small"
                        sx={{
                          backgroundColor: theme.palette.mode === 'dark' ? theme.palette.grey[700] : theme.palette.grey[100],
                          color: theme.palette.mode === 'dark' ? theme.palette.common.white : theme.palette.common.black,
                          '&:hover': {
                            backgroundColor: theme.palette.mode === 'dark' ? theme.palette.grey[600] : theme.palette.grey[200],
                          },
                        }}
                      >
                        <CloseIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Snackbar
        open={snackbarOpen}
        autoHideDuration={4000}
        onClose={() => setSnackbarOpen(false)}
        message={snackbarMessage}
        action={
          <IconButton
            size="small"
            aria-label="close"
            color="inherit"
            onClick={() => setSnackbarOpen(false)}
          >
            <CloseIcon fontSize="small" />
          </IconButton>
        }
      />
    </Container>
  );
};

export default PriceAdjustments; 