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
  Link,
} from '@mui/material';
import {
  LocationOn as LocationIcon,
  CalendarToday as CalendarIcon,
  Timer as TimerIcon,
  Close as CloseIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

interface SourceDescriptionLink {
  text: string;
  url: string;
  type: 'original' | 'cheaper';
}

interface SourceDescriptionData {
  text: string;
  links: SourceDescriptionLink[];
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
  source_description: string;
  source_description_data: SourceDescriptionData;
  source_type_display: string;
  action_required: string;
  location_context: {
    type: 'nationwide' | 'same_store' | 'different_store';
    description: string;
    store_specific: boolean;
  };
}

interface ApiResponse {
  adjustments: PriceAdjustment[];
  total_potential_savings: number;
}

const PriceAdjustments: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
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

  const renderSourceDescriptionWithLinks = (adjustment: PriceAdjustment) => {
    const { text, links } = adjustment.source_description_data || { text: adjustment.source_description, links: [] };
    
    if (!links.length) {
      return <Typography variant="body2">{text}</Typography>;
    }

    // Split the text and insert links where appropriate
    let parts: React.ReactNode[] = [text];
    
    links.forEach(link => {
      const newParts: React.ReactNode[] = [];
      
      parts.forEach(part => {
        if (typeof part === 'string') {
          // Look for price mentions to insert links
          if (link.type === 'original' && part.includes(`$${adjustment.current_price.toFixed(2)}`)) {
            const splitText = part.split(`$${adjustment.current_price.toFixed(2)}`);
            newParts.push(splitText[0]);
            newParts.push(
              <span key={link.url}>
                ${adjustment.current_price.toFixed(2)} (see{' '}
                <Link
                  component="button"
                  variant="body2"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(link.url);
                  }}
                  sx={{ 
                    textDecoration: 'underline',
                    cursor: 'pointer',
                    '&:hover': { textDecoration: 'underline' }
                  }}
                >
                  {link.text}
                </Link>
                )
              </span>
            );
            newParts.push(splitText[1]);
          } else if (link.type === 'cheaper' && part.includes(`$${adjustment.lower_price.toFixed(2)}`)) {
            const splitText = part.split(`$${adjustment.lower_price.toFixed(2)}`);
            newParts.push(splitText[0]);
            newParts.push(
              <span key={link.url}>
                ${adjustment.lower_price.toFixed(2)} (see{' '}
                <Link
                  component="button"
                  variant="body2"
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(link.url);
                  }}
                  sx={{ 
                    textDecoration: 'underline',
                    cursor: 'pointer',
                    '&:hover': { textDecoration: 'underline' }
                  }}
                >
                  {link.text}
                </Link>
                )
              </span>
            );
            newParts.push(splitText[1]);
          } else {
            newParts.push(part);
          }
        } else {
          newParts.push(part);
        }
      });
      
      parts = newParts;
    });

    return <Typography variant="body2">{parts}</Typography>;
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
            <Card sx={{ 
              borderLeft: `4px solid ${
                adjustment.location_context.type === 'nationwide' ? theme.palette.info.main :
                adjustment.data_source === 'official_promo' ? theme.palette.success.main :
                theme.palette.primary.main
              }`
            }}>
              <CardContent>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="h6" gutterBottom>
                      {adjustment.description}
                    </Typography>
                    
                    {/* Source Description - Main context */}
                    <Alert severity={adjustment.location_context.type === 'nationwide' ? 'info' : 'success'} sx={{ mb: 2 }}>
                      {renderSourceDescriptionWithLinks(adjustment)}
                    </Alert>

                    {/* Price Information */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
                      <Typography variant="body1">
                        You Paid: <strong>${adjustment.current_price.toFixed(2)}</strong>
                      </Typography>
                      <Typography variant="body1" color="success.main" sx={{ fontWeight: 'bold' }}>
                        Available For: <strong>${adjustment.lower_price.toFixed(2)}</strong>
                      </Typography>
                      <Chip
                        label={`Save $${adjustment.price_difference.toFixed(2)}`}
                        color="success"
                        size="medium"
                        sx={{ fontWeight: 'bold' }}
                      />
                    </Box>

                    {/* Action Required */}
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 'bold', mb: 1 }}>
                        What to do:
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {adjustment.action_required}
                      </Typography>
                    </Box>

                    {/* Additional Context */}
                    <Grid container spacing={2} sx={{ mb: 2 }}>
                      <Grid item xs={12} sm={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CalendarIcon color="action" fontSize="small" />
                          <Typography variant="body2" color="text.secondary">
                            Purchase: {format(new Date(adjustment.purchase_date), 'MMM d, yyyy')}
                          </Typography>
                        </Box>
                      </Grid>
                      <Grid item xs={12} sm={6}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <TimerIcon color="warning" fontSize="small" />
                          <Typography variant="body2" color="warning.main">
                            {adjustment.days_remaining} days remaining
                          </Typography>
                        </Box>
                      </Grid>
                    </Grid>

                    {/* Source and Location */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Chip
                        label={adjustment.source_type_display}
                        size="small"
                        variant="outlined"
                        color={
                          adjustment.source_type_display === 'Official Costco Promotion' ? 'success' :
                          adjustment.source_type_display === 'Your Purchase History' ? 'primary' : 'default'
                        }
                      />
                      <Chip
                        label={adjustment.location_context.description}
                        size="small"
                        variant="outlined"
                        color={
                          adjustment.location_context.type === 'nationwide' ? 'info' :
                          adjustment.location_context.type === 'same_store' ? 'success' :
                          adjustment.location_context.type === 'different_store' ? 'warning' : 'default'
                        }
                      />
                    </Box>
                  </Box>

                  <Box sx={{ textAlign: 'right', ml: 2 }}>
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