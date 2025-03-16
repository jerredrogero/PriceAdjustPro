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
} from '@mui/material';
import {
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
  const theme = useTheme();
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
          <Alert severity="info">
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