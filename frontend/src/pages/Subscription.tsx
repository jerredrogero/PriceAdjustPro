import React, { useState, useEffect, useContext } from 'react';
import {
  Container,
  Grid,
  Card,
  CardHeader,
  CardContent,
  CardActions,
  Typography,
  Button,
  Box,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  CircularProgress,
  Divider,
  Paper,
  useTheme,
  alpha,
  Stack,
} from '@mui/material';
import {
  Check as CheckIcon,
  Star as StarIcon,
  Upgrade as UpgradeIcon,
  Receipt as ReceiptIcon,
  Notifications as NotificationsIcon,
  Analytics as AnalyticsIcon,
  Security as SecurityIcon,
  LocalOffer as SaleIcon,
  Verified as VerifiedIcon,
} from '@mui/icons-material';
import { UserContext } from '../components/Layout';
import api from '../api/axios';

interface SubscriptionProduct {
  id: number;
  stripe_price_id: string;
  name: string;
  price: string;
  currency: string;
  billing_interval: string;
}

interface UserSubscription {
  has_subscription: boolean;
  status: string | null;
  is_active: boolean;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
  days_until_renewal?: number;
  product?: {
    name: string;
    price: string;
    billing_interval: string;
  };
}

const Subscription: React.FC = () => {
  const user = useContext(UserContext);
  const theme = useTheme();
  const [products, setProducts] = useState<SubscriptionProduct[]>([]);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Fallback products for when API fails
  const fallbackProducts = [
    {
      id: 1,
      stripe_price_id: 'price_1SuFfcCBOzePXFXgnR1w3wQc',
      name: 'Premium Monthly',
      price: '4.99',
      currency: 'usd',
      billing_interval: 'month'
    },
    {
      id: 2,
      stripe_price_id: 'price_1SuFfcCBOzePXFXgnR1w3wQc',
      name: 'Premium Yearly',
      price: '49.99',
      currency: 'usd',
      billing_interval: 'year'
    }
  ];

  useEffect(() => {
    fetchSubscriptionData();
  }, []);

  const retryFetch = () => {
    setError('');
    fetchSubscriptionData();
  };

  const fetchSubscriptionData = async () => {
    try {
      setLoading(true);
      setError('');

      const apiTimeout = 5000;
      
      const [statusResponse, productsResponse] = await Promise.allSettled([
        api.get('/subscriptions/status/', { timeout: apiTimeout }),
        api.get('/subscriptions/products/', { timeout: apiTimeout }),
      ]);

      if (statusResponse.status === 'fulfilled') {
        setSubscription(statusResponse.value.data);
      }

      let fetchedProducts = [];
      if (productsResponse.status === 'fulfilled') {
        const productsData = productsResponse.value.data;
        fetchedProducts = productsData.products || productsData || [];
      }

      if (fetchedProducts.length === 0) {
        fetchedProducts = fallbackProducts;
      }

      setProducts(fetchedProducts);

    } catch (err) {
      console.error('Subscription data fetch error:', err);
      setProducts(fallbackProducts);
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (product: SubscriptionProduct) => {
    try {
      setLoading(true);
      setError('');

      const response = await api.post('/subscriptions/create-checkout-session/', {
        price_id: product.stripe_price_id,
        product_id: product.id,
      });

      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      } else {
        throw new Error('No checkout URL received from server');
      }

    } catch (err: any) {
      console.error('Checkout session error:', err);
      let errorMessage = 'Failed to create checkout session.';
      if (err.response?.data?.error) errorMessage = err.response.data.error;
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { icon: <ReceiptIcon color="primary" />, text: 'Unlimited receipt uploads' },
    { icon: <SaleIcon color="secondary" />, text: 'Searchable Costco sale directory' },
    { icon: <NotificationsIcon color="error" />, text: 'Push notification alerts' },
    { icon: <AnalyticsIcon color="info" />, text: 'Advanced spending insights' },
    { icon: <SecurityIcon color="success" />, text: 'Priority customer support' },
  ];

  if (loading && products.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 8, textAlign: 'center', minHeight: '60vh' }}>
        <CircularProgress size={60} />
        <Typography variant="h6" sx={{ mt: 4 }}>
          Loading your premium options...
        </Typography>
      </Container>
    );
  }

  return (
    <Box sx={{ bgcolor: alpha(theme.palette.primary.main, 0.02), minHeight: '100vh', pb: 12 }}>
      {/* Header Section */}
      <Box 
        sx={{ 
          background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
          color: 'white',
          pt: 12,
          pb: 15,
          textAlign: 'center',
          clipPath: 'polygon(0 0, 100% 0, 100% 85%, 0% 100%)',
        }}
      >
        <Container maxWidth="md">
          <Typography variant="h2" gutterBottom fontWeight="900" sx={{ mb: 2 }}>
            Go Premium. <br /> Save More.
          </Typography>
          <Typography variant="h5" sx={{ opacity: 0.9, maxWidth: 700, mx: 'auto', mb: 4 }}>
            Join Costco members who use PriceAdjustPro to 
            save even more.
          </Typography>
          <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2 }}>
            <Chip 
              icon={<VerifiedIcon sx={{ color: 'white !important' }} />} 
              label="Cancel anytime" 
              sx={{ color: 'white', border: '1px solid rgba(255,255,255,0.3)', bgcolor: 'rgba(255,255,255,0.1)' }} 
            />
          </Box>
        </Container>
      </Box>

      <Container maxWidth="lg" sx={{ mt: -8 }}>
        {error && (
          <Alert severity="error" sx={{ mb: 4, borderRadius: 3, boxShadow: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        )}

        {success && (
          <Alert severity="success" sx={{ mb: 4, borderRadius: 3, boxShadow: 2 }} onClose={() => setSuccess('')}>
            {success}
          </Alert>
        )}

        {/* Current Subscription Status */}
        {subscription?.has_subscription && (
          <Paper 
            elevation={0}
            sx={{ 
              mb: 6, 
              p: 4, 
              borderRadius: 4, 
              border: `1px solid ${alpha(theme.palette.success.main, 0.2)}`,
              bgcolor: alpha(theme.palette.success.main, 0.02),
              display: 'flex',
              flexDirection: { xs: 'column', md: 'row' },
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 3
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <Box 
                sx={{ 
                  width: 64, 
                  height: 64, 
                  borderRadius: '50%', 
                  bgcolor: 'success.main', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center' 
                }}
              >
                <StarIcon sx={{ color: 'white', fontSize: 32 }} />
              </Box>
              <Box>
                <Typography variant="h5" fontWeight="bold">You are a Premium Member</Typography>
                <Typography color="text.secondary">
                  {subscription.product?.name} • ${subscription.product?.price}/{subscription.product?.billing_interval}
                </Typography>
              </Box>
            </Box>
            <Stack direction="row" spacing={2}>
              <Button 
                variant="outlined" 
                color="primary"
                onClick={() => window.location.href = '/api/subscriptions/customer-portal/'}
                sx={{ borderRadius: '50px', px: 4 }}
              >
                Manage
              </Button>
            </Stack>
          </Paper>
        )}

        <Grid container spacing={4} justifyContent="center">
          {/* Feature List Column */}
          <Grid item xs={12} md={4}>
            <Box sx={{ py: 2 }}>
              <Typography variant="h5" fontWeight="bold" gutterBottom>
                Premium Features
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                Everything you need to squeeze every cent of value out of your Costco membership.
              </Typography>
              <List sx={{ bgcolor: 'background.paper', borderRadius: 4, p: 2, boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
                {features.map((feature, index) => (
                  <ListItem key={index}>
                    <ListItemIcon sx={{ minWidth: 44 }}>
                      {feature.icon}
                    </ListItemIcon>
                    <ListItemText 
                      primary={feature.text} 
                      primaryTypographyProps={{ fontWeight: 'medium' }}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          </Grid>

          {/* Pricing Plans Column */}
          <Grid item xs={12} md={8}>
            <Grid container spacing={3} alignItems="stretch">
              {!subscription?.has_subscription && products.map((product) => {
                const isYearly = product.billing_interval === 'year';
                return (
                  <Grid item xs={12} sm={6} key={product.id}>
                    <Card 
                      elevation={isYearly ? 24 : 4}
                      sx={{ 
                        height: '100%',
                        borderRadius: 6,
                        display: 'flex',
                        flexDirection: 'column',
                        position: 'relative',
                        transition: 'transform 0.3s ease',
                        '&:hover': { transform: 'translateY(-8px)' },
                        ...(isYearly && {
                          border: `2px solid ${theme.palette.primary.main}`,
                          boxShadow: '0 20px 40px rgba(227, 24, 55, 0.15)'
                        })
                      }}
                    >
                      {isYearly && (
                        <Box 
                          sx={{ 
                            position: 'absolute', 
                            top: 24, 
                            right: -35, 
                            bgcolor: 'secondary.main', 
                            color: 'white', 
                            px: 6, 
                            py: 0.5, 
                            transform: 'rotate(45deg)',
                            fontWeight: 900,
                            fontSize: '0.75rem',
                            zIndex: 1
                          }}
                        >
                          Best Value
                        </Box>
                      )}
                      <CardContent sx={{ p: 4, flexGrow: 1 }}>
                        <Typography variant="h6" fontWeight="bold" color={isYearly ? "primary" : "text.primary"}>
                          {product.name}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'baseline', my: 3 }}>
                          <Typography variant="h2" fontWeight="900">${product.price}</Typography>
                          <Typography variant="subtitle1" color="text.secondary" sx={{ ml: 1 }}>
                            /{product.billing_interval}
                          </Typography>
                        </Box>
                        <Divider sx={{ my: 3 }} />
                        <List dense>
                          <ListItem sx={{ px: 0 }}>
                            <ListItemIcon sx={{ minWidth: 32 }}><CheckIcon color="success" fontSize="small" /></ListItemIcon>
                            <ListItemText primary="All Premium Features" />
                          </ListItem>
                          {isYearly && (
                            <ListItem sx={{ px: 0 }}>
                              <ListItemIcon sx={{ minWidth: 32 }}><CheckIcon color="success" fontSize="small" /></ListItemIcon>
                              <ListItemText primary="Two Months Free" />
                            </ListItem>
                          )}
                        </List>
                      </CardContent>
                      <CardActions sx={{ p: 4, pt: 0 }}>
                        <Button
                          variant={isYearly ? "contained" : "outlined"}
                          fullWidth
                          size="large"
                          onClick={() => handleSubscribe(product)}
                          disabled={loading}
                          sx={{ 
                            borderRadius: '50px', 
                            py: 1.5,
                            fontWeight: 'bold',
                            textTransform: 'none',
                            fontSize: '1.1rem'
                          }}
                        >
                          {loading ? 'Processing...' : 'Subscribe Now'}
                        </Button>
                      </CardActions>
                    </Card>
                  </Grid>
                );
              })}
            </Grid>
          </Grid>
        </Grid>

        {/* Secure Payments Note */}
        <Box sx={{ mt: 8, textAlign: 'center' }}>
          <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1, mb: 2, color: 'text.secondary' }}>
            <SecurityIcon fontSize="small" />
            <Typography variant="body2">Secure payments handled by Stripe</Typography>
          </Box>
          <Typography variant="caption" color="text.secondary">
            By subscribing, you agree to our Terms of Service and Privacy Policy. <br />
            Need help? Contact us at support@priceadjustpro.com
          </Typography>
        </Box>
      </Container>
    </Box>
  );
};

export default Subscription;
