import React, { useEffect, useState } from 'react';
import {
  Container,
  Typography,
  Paper,
  Box,
  Grid,
  Card,
  CardContent,
  Button,
  Chip,
  LinearProgress,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Close as CloseIcon,
  LocationOn as LocationIcon,
  CalendarToday as CalendarIcon,
  Timer as TimerIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';

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
  const [adjustments, setAdjustments] = useState<PriceAdjustment[]>([]);
  const [totalSavings, setTotalSavings] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAdjustments();
  }, []);

  const fetchAdjustments = async () => {
    try {
      const response = await fetch('/api/price-adjustments/');
      if (!response.ok) throw new Error('Failed to fetch price adjustments');
      
      const data: ApiResponse = await response.json();
      setAdjustments(data.adjustments);
      setTotalSavings(data.total_potential_savings);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = async (itemCode: string) => {
    try {
      const response = await fetch(`/api/price-adjustments/${itemCode}/dismiss/`, {
        method: 'POST',
      });
      
      if (!response.ok) throw new Error('Failed to dismiss adjustment');
      
      setAdjustments(prev => prev.filter(adj => adj.item_code !== itemCode));
      setTotalSavings(prev => prev - adjustments.find(adj => adj.item_code === itemCode)!.price_difference);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to dismiss adjustment');
    }
  };

  if (loading) return <LinearProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (adjustments.length === 0) {
    return (
      <Container maxWidth="md" sx={{ mt: 4 }}>
        <Alert severity="info">
          No price adjustments available at this time. We'll notify you when we find better prices!
        </Alert>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" gutterBottom>
          Price Adjustments Available
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Total potential savings: <Chip label={`$${totalSavings.toFixed(2)}`} color="success" />
        </Typography>
      </Box>

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
                        Current Price: ${adjustment.current_price.toFixed(2)}
                      </Typography>
                      <Typography variant="body1" color="success.main" sx={{ fontWeight: 'bold' }}>
                        Lower Price: ${adjustment.lower_price.toFixed(2)}
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

                  <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 1 }}>
                    <Tooltip title="Dismiss this alert">
                      <IconButton
                        onClick={() => handleDismiss(adjustment.item_code)}
                        size="small"
                        color="default"
                      >
                        <CloseIcon />
                      </IconButton>
                    </Tooltip>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <TimerIcon color="warning" />
                      <Typography variant="body2" color="warning.main">
                        {adjustment.days_remaining} days remaining
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default PriceAdjustments; 