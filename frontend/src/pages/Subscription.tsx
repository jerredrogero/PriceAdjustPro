import React, { useState, useEffect } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import { Elements, CardElement, useStripe, useElements } from '@stripe/react-stripe-js';
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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  CircularProgress,
  Divider,
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
import { useAuth } from '../contexts/AuthContext';

// Load Stripe with the publishable key
const stripePromise = loadStripe('pk_live_5Pl9Z3VnAi1DOLqNryAk7C7F');

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

const CheckoutForm: React.FC<{
  product: SubscriptionProduct;
  onSuccess: () => void;
  onCancel: () => void;
}> = ({ product, onSuccess, onCancel }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (!stripe || !elements) {
      return;
    }

    setLoading(true);

    const cardElement = elements.getElement(CardElement);
    if (!cardElement) {
      setError('Card element not found');
      setLoading(false);
      return;
    }

    // Create payment method
    const { error: pmError, paymentMethod } = await stripe.createPaymentMethod({
      type: 'card',
      card: cardElement,
    });

    if (pmError) {
      setError(pmError.message || 'Failed to create payment method');
      setLoading(false);
      return;
    }

    try {
      // Create subscription
      const response = await fetch('/api/subscriptions/create/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          product_id: product.id,
          payment_method_id: paymentMethod.id,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to create subscription');
      }

      // Handle subscription confirmation if needed
      if (data.client_secret) {
        const { error: confirmError } = await stripe.confirmCardPayment(data.client_secret);
        
        if (confirmError) {
          setError(confirmError.message || 'Payment confirmation failed');
          setLoading(false);
          return;
        }
      }

      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create subscription');
    }

    setLoading(false);
  };

  return (
    <form onSubmit={handleSubmit}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Subscribe to {product.name}
        </Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          ${product.price}/{product.billing_interval}
        </Typography>
      </Box>

      <Box sx={{ mb: 3, p: 2, border: '1px solid #e0e0e0', borderRadius: 1 }}>
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '16px',
                color: '#424770',
                '::placeholder': {
                  color: '#aab7c4',
                },
              },
            },
          }}
        />
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={onCancel} disabled={loading}>
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          disabled={!stripe || loading}
          startIcon={loading && <CircularProgress size={20} />}
        >
          {loading ? 'Processing...' : 'Subscribe'}
        </Button>
      </Box>
    </form>
  );
};

const Subscription: React.FC = () => {
  const { user } = useAuth();
  const [products, setProducts] = useState<SubscriptionProduct[]>([]);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedProduct, setSelectedProduct] = useState<SubscriptionProduct | null>(null);
  const [checkoutOpen, setCheckoutOpen] = useState(false);

  useEffect(() => {
    fetchSubscriptionData();
  }, []);

  const fetchSubscriptionData = async () => {
    try {
      setLoading(true);

      // Fetch subscription status and products
      const [statusResponse, productsResponse] = await Promise.all([
        fetch('/api/subscriptions/status/'),
        fetch('/api/subscriptions/products/'),
      ]);

      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        setSubscription(statusData);
      }

      if (productsResponse.ok) {
        const productsData = await productsResponse.json();
        setProducts(productsData.products || []);
      }
    } catch (err) {
      setError('Failed to load subscription information');
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = (product: SubscriptionProduct) => {
    setSelectedProduct(product);
    setCheckoutOpen(true);
  };

  const handleSubscriptionSuccess = () => {
    setCheckoutOpen(false);
    setSelectedProduct(null);
    setSuccess('Subscription created successfully!');
    fetchSubscriptionData();
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
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError('')}>
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
                  <Button 
                    variant="outlined" 
                    color="warning"
                    onClick={handleCancelSubscription}
                  >
                    Cancel Subscription
                  </Button>
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
                      top: -10,
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
                        Save 50% compared to monthly
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
                
                <CardActions sx={{ p: 2 }}>
                  <Button
                    variant="contained"
                    fullWidth
                    size="large"
                    onClick={() => handleSubscribe(product)}
                  >
                    Subscribe Now
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Checkout Dialog */}
      <Dialog 
        open={checkoutOpen} 
        onClose={() => setCheckoutOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Complete Your Subscription</DialogTitle>
        <DialogContent>
          {selectedProduct && (
            <Elements stripe={stripePromise}>
              <CheckoutForm
                product={selectedProduct}
                onSuccess={handleSubscriptionSuccess}
                onCancel={() => setCheckoutOpen(false)}
              />
            </Elements>
          )}
        </DialogContent>
      </Dialog>
    </Container>
  );
};

export default Subscription; 