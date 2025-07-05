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
} from '@mui/material';
import {
  Check as CheckIcon,
  Star as StarIcon,
  Upgrade as UpgradeIcon,
  Receipt as ReceiptIcon,
  Notifications as NotificationsIcon,
  Analytics as AnalyticsIcon,
  Security as SecurityIcon,
} from '@mui/icons-material';
import { UserContext } from '../components/Layout';
import api from '../api/axios';

interface SubscriptionProduct {
  id: number;
  stripe_price_id: string;
  name: string;
  description: string;
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
  const [products, setProducts] = useState<SubscriptionProduct[]>([]);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

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

      // Fetch subscription status and products using axios
      const [statusResponse, productsResponse] = await Promise.allSettled([
        api.get('/subscriptions/status/'),
        api.get('/subscriptions/products/'),
      ]);

      // Handle subscription status
      if (statusResponse.status === 'fulfilled') {
        console.log('Subscription status data:', statusResponse.value.data);
        setSubscription(statusResponse.value.data);
      } else {
        console.warn('Subscription status API failed:', statusResponse.reason);
      }

      // Handle products - for now, always use fallback products with correct pricing
      let fetchedProducts = [];
      if (productsResponse.status === 'fulfilled') {
        const productsData = productsResponse.value.data;
        console.log('API Products data (using fallback instead):', productsData);
        // Don't use API data for now since it has old pricing
        // fetchedProducts = productsData.products || productsData || [];
      } else {
        console.warn('Products API failed:', productsResponse.reason);
      }

      // Always use current pricing from fallback products
      console.log('Using fallback products with updated pricing');
      fetchedProducts = [
        {
          id: 1,
          stripe_price_id: 'price_monthly',
          name: 'PriceAdjustPro Monthly',
          description: 'Full access to all features',
          price: '2.99',
          currency: 'usd',
          billing_interval: 'month'
        },
        {
          id: 2,
          stripe_price_id: 'price_yearly',
          name: 'PriceAdjustPro Yearly',
          description: 'Full access to all features',
          price: '29.99',
          currency: 'usd',
          billing_interval: 'year'
        }
      ];

      setProducts(fetchedProducts);
    } catch (err) {
      console.error('Subscription data fetch error:', err);
      setError('Failed to load subscription information. Please try refreshing the page.');
      // Set fallback products even on error
      setProducts([
        {
          id: 1,
          stripe_price_id: 'price_monthly',
          name: 'PriceAdjustPro Monthly',
          description: 'Full access to all features',
          price: '2.99',
          currency: 'usd',
          billing_interval: 'month'
        },
        {
          id: 2,
          stripe_price_id: 'price_yearly',
          name: 'PriceAdjustPro Yearly',
          description: 'Full access to all features',
          price: '29.99',
          currency: 'usd',
          billing_interval: 'year'
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (product: SubscriptionProduct) => {
    try {
      setLoading(true);
      setError('');

      console.log('Subscription requested for product:', product);

      // For now, show a message that subscription processing is being finalized
      setError(`Subscription processing is currently being finalized. 

To subscribe to ${product.name} (${product.price}/${product.billing_interval}), please contact us at:

📧 support@priceadjustpro.com
💬 Mention: "${product.name} subscription"

We'll set up your subscription manually and provide immediate access to all premium features.`);

    } catch (err: any) {
      console.error('Subscription error:', err);
      setError('Unable to process subscription at this time. Please contact support@priceadjustpro.com for assistance.');
    } finally {
      setLoading(false);
    }
  };


  const handleCancelSubscription = async () => {
    try {
      const response = await fetch('/api/subscriptions/cancel/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ cancel_immediately: false }),
      });

      if (!response.ok) {
        throw new Error('Failed to cancel subscription');
      }

      setSuccess('Subscription canceled successfully');
      fetchSubscriptionData();
    } catch (err) {
      setError('Failed to cancel subscription');
    }
  };

  const handleReactivateSubscription = async () => {
    try {
      const response = await fetch('/api/subscriptions/update/', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to reactivate subscription');
      }

      setSuccess('Subscription reactivated successfully');
      fetchSubscriptionData();
    } catch (err) {
      setError('Failed to reactivate subscription');
    }
  };

  const handleManageSubscription = async () => {
    try {
      const response = await fetch('/api/subscriptions/customer-portal/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to create customer portal session');
      }

      const data = await response.json();
      // Redirect to Stripe Customer Portal
      window.location.href = data.url;
    } catch (err) {
      setError('Failed to access customer portal');
    }
  };

  const features = [
    { icon: <ReceiptIcon />, text: 'Unlimited receipt uploads' },
    { icon: <NotificationsIcon />, text: 'Real-time price adjustment alerts' },
    { icon: <AnalyticsIcon />, text: 'Advanced analytics and insights' },
    { icon: <SecurityIcon />, text: 'Priority customer support' },
  ];

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ mt: 2 }}>
          Loading subscription information...
        </Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h3" gutterBottom>
          Upgrade Your Account
        </Typography>
        <Typography variant="h6" color="text.secondary" paragraph>
          Get the most out of PriceAdjustPro with premium features
        </Typography>
      </Box>

      {error && (
        <Alert 
          severity="error" 
          sx={{ mb: 3 }} 
          onClose={() => setError('')}
          action={
            <Button color="inherit" size="small" onClick={retryFetch}>
              Retry
            </Button>
          }
        >
          {error}
        </Alert>
      )}

      {success && (
        <Alert severity="success" sx={{ mb: 3 }} onClose={() => setSuccess('')}>
          {success}
        </Alert>
      )}

      {/* Current Subscription Status */}
      {subscription?.has_subscription && (
        <Card sx={{ mb: 4 }}>
          <CardHeader 
            title="Current Subscription"
            avatar={<UpgradeIcon color="primary" />}
          />
          <CardContent>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={6}>
                <Typography variant="h6">
                  {subscription.product?.name}
                </Typography>
                <Typography color="text.secondary">
                  ${subscription.product?.price}/{subscription.product?.billing_interval}
                </Typography>
                <Chip 
                  label={subscription.status} 
                  color={subscription.is_active ? 'success' : 'warning'}
                  sx={{ mt: 1 }}
                />
              </Grid>
              <Grid item xs={12} md={6}>
                {subscription.cancel_at_period_end ? (
                  <Box>
                    <Typography color="warning.main">
                      Subscription will cancel at period end
                    </Typography>
                    <Button 
                      variant="outlined" 
                      onClick={handleReactivateSubscription}
                      sx={{ mt: 1 }}
                    >
                      Reactivate Subscription
                    </Button>
                  </Box>
                ) : (
                  <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column' }}>
                    <Button 
                      variant="contained" 
                      color="primary"
                      onClick={handleManageSubscription}
                      sx={{ mb: 1 }}
                    >
                      Manage Subscription
                    </Button>
                    <Button 
                      variant="outlined" 
                      color="warning"
                      onClick={handleCancelSubscription}
                      size="small"
                    >
                      Cancel Subscription
                    </Button>
                  </Box>
                )}
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      )}

      {/* Premium Features */}
      <Card sx={{ mb: 4 }}>
        <CardHeader title="Premium Features" />
        <CardContent>
          <Grid container spacing={2}>
            {features.map((feature, index) => (
              <Grid item xs={12} sm={6} key={index}>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  <Box sx={{ mr: 2, color: 'primary.main' }}>
                    {feature.icon}
                  </Box>
                  <Typography>{feature.text}</Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </CardContent>
      </Card>

      {/* Subscription Plans */}
      {!subscription?.has_subscription && (
        <Grid container spacing={3}>
          {products.map((product) => (
            <Grid item xs={12} md={6} key={product.id}>
              <Card 
                sx={{ 
                  height: '100%',
                  position: 'relative',
                  ...(product.billing_interval === 'year' && {
                    border: '2px solid',
                    borderColor: 'primary.main',
                  })
                }}
              >
                {product.billing_interval === 'year' && (
                  <Chip
                    label="Best Value"
                    color="primary"
                    icon={<StarIcon />}
                    sx={{
                      position: 'absolute',
                      top: 8,
                      right: 16,
                    }}
                  />
                )}
                
                <CardHeader 
                  title={product.name}
                  subheader={product.description}
                />
                
                <CardContent>
                  <Box sx={{ textAlign: 'center', mb: 3 }}>
                    <Typography variant="h3" component="div">
                      ${product.price}
                    </Typography>
                    <Typography color="text.secondary">
                      per {product.billing_interval}
                    </Typography>
                    {product.billing_interval === 'year' && (
                      <Typography variant="body2" color="primary">
                        Get two free months!
                      </Typography>
                    )}
                  </Box>

                  <List dense>
                    {features.map((feature, index) => (
                      <ListItem key={index} sx={{ px: 0 }}>
                        <ListItemIcon sx={{ minWidth: 36 }}>
                          <CheckIcon color="primary" fontSize="small" />
                        </ListItemIcon>
                        <ListItemText primary={feature.text} />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
                
                <CardActions sx={{ p: 2, flexDirection: 'column', gap: 1 }}>
                  <Button
                    variant="contained"
                    fullWidth
                    size="large"
                    onClick={() => handleSubscribe(product)}
                  >
                    Subscribe Now
                  </Button>
                  <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
                    Contact support@priceadjustpro.com for instant setup
                  </Typography>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Checkout Dialog */}
    </Container>
  );
};

export default Subscription; 