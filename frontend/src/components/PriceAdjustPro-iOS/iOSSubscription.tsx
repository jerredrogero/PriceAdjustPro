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
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  Check as CheckIcon,
  Star as StarIcon,
  Upgrade as UpgradeIcon,
  Receipt as ReceiptIcon,
  Notifications as NotificationsIcon,
  Analytics as AnalyticsIcon,
  Security as SecurityIcon,
  Apple as AppleIcon,
  Restore as RestoreIcon,
  Settings as SettingsIcon,
  LocalOffer as SaleIcon,
} from '@mui/icons-material';
import { UserContext } from '../Layout';
import StoreKitManager, { StoreKitProduct, SubscriptionStatus } from './StoreKitManager';

const iOSSubscription: React.FC = () => {
  const user = useContext(UserContext);
  const [storeKit] = useState(() => StoreKitManager.getInstance());
  const [products, setProducts] = useState<StoreKitProduct[]>([]);
  const [subscriptionStatus, setSubscriptionStatus] = useState<SubscriptionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [purchasing, setPurchasing] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [restoreDialog, setRestoreDialog] = useState(false);

  useEffect(() => {
    initializeStoreKit();
    
    // Add subscription status listener
    const removeListener = storeKit.addStatusListener((status) => {
      setSubscriptionStatus(status);
    });

    return removeListener;
  }, [storeKit]);

  const initializeStoreKit = async () => {
    try {
      setLoading(true);
      setError('');

      if (!storeKit.isAvailable()) {
        throw new Error('This feature is only available on iOS devices');
      }

      await storeKit.initialize();
      setProducts(storeKit.getProducts());
      setSubscriptionStatus(storeKit.getSubscriptionStatus());

    } catch (err: any) {
      console.error('StoreKit initialization error:', err);
      setError(err.message || 'Failed to initialize App Store purchases');
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async (product: StoreKitProduct) => {
    try {
      setPurchasing(product.id);
      setError('');
      setSuccess('');

      // Use user ID as app account token to link with backend
      const appAccountToken = user?.id?.toString();

      const result = await storeKit.purchaseProduct(product.id, appAccountToken);

      if (result.userCancelled) {
        setError('Purchase was cancelled');
      } else if (result.pending) {
        setSuccess('Purchase is pending approval. You will receive access once approved.');
      } else if (result.transaction) {
        setSuccess('Subscription activated successfully!');
      } else if (result.error) {
        setError(`Purchase failed: ${result.error.message}`);
      }

    } catch (err: any) {
      console.error('Purchase error:', err);
      setError(err.message || 'Purchase failed. Please try again.');
    } finally {
      setPurchasing(null);
    }
  };

  const handleRestorePurchases = async () => {
    try {
      setLoading(true);
      setError('');
      await storeKit.restorePurchases();
      setSuccess('Purchases restored successfully!');
      setRestoreDialog(false);
    } catch (err: any) {
      console.error('Restore error:', err);
      setError(err.message || 'Failed to restore purchases');
    } finally {
      setLoading(false);
    }
  };

  const handleManageSubscription = async () => {
    try {
      await storeKit.showManageSubscriptions();
    } catch (err: any) {
      console.error('Manage subscription error:', err);
      setError('Failed to open subscription management');
    }
  };

  const getProductDisplayInfo = (product: StoreKitProduct) => {
    const isYearly = product.id === StoreKitManager.PRODUCT_IDS.YEARLY;
    return {
      name: isYearly ? 'PriceAdjustPro Yearly' : 'PriceAdjustPro Monthly',
      period: isYearly ? 'year' : 'month',
      savings: isYearly ? 'Save 2 months!' : null,
      recommended: isYearly,
    };
  };

  const features = [
    { icon: <ReceiptIcon />, text: 'Unlimited receipt uploads' },
    { icon: <SaleIcon />, text: 'Searchable Costco sale directory' },
    { icon: <NotificationsIcon />, text: 'Real-time price adjustment alerts' },
    { icon: <AnalyticsIcon />, text: 'Advanced analytics and insights' },
    { icon: <SecurityIcon />, text: 'Priority customer support' },
  ];

  if (!storeKit.isAvailable()) {
    return (
      <Container maxWidth="lg" sx={{ py: 4, textAlign: 'center' }}>
        <Alert severity="info" sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            iOS App Store Purchases Not Available
          </Typography>
          <Typography>
            This feature is only available when using the iOS app. 
            Please use the web version for Stripe payments or download our iOS app from the App Store.
          </Typography>
        </Alert>
      </Container>
    );
  }

  if (loading && products.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 4, textAlign: 'center' }}>
        <CircularProgress />
        <Typography variant="h6" sx={{ mt: 2 }}>
          Loading subscription options...
        </Typography>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2 }}>
          <AppleIcon sx={{ fontSize: 40, mr: 2, color: 'text.secondary' }} />
          <Typography variant="h3" gutterBottom>
            App Store Subscriptions
          </Typography>
        </Box>
        <Typography variant="h6" color="text.secondary" paragraph>
          Subscribe through the App Store with your Apple ID
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Secure payments handled by Apple • Cancel anytime in Settings
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
      {subscriptionStatus?.isActive && (
        <Card sx={{ mb: 4 }}>
          <CardHeader 
            title="Active Subscription"
            avatar={<UpgradeIcon color="primary" />}
          />
          <CardContent>
            <Grid container spacing={2} alignItems="center">
              <Grid item xs={12} md={6}>
                <Typography variant="h6">
                  {products.find(p => p.id === subscriptionStatus.productId)?.displayName || 'PriceAdjustPro'}
                </Typography>
                <Typography color="text.secondary">
                  {subscriptionStatus.expirationDate && (
                    `Expires: ${subscriptionStatus.expirationDate.toLocaleDateString()}`
                  )}
                </Typography>
                <Chip 
                  label={subscriptionStatus.willAutoRenew ? 'Auto-Renewing' : 'Will Expire'} 
                  color={subscriptionStatus.willAutoRenew ? 'success' : 'warning'}
                  sx={{ mt: 1 }}
                />
                {subscriptionStatus.environment === 'sandbox' && (
                  <Chip 
                    label="Sandbox" 
                    color="info" 
                    size="small"
                    sx={{ mt: 1, ml: 1 }}
                  />
                )}
              </Grid>
              <Grid item xs={12} md={6}>
                <Box sx={{ display: 'flex', gap: 1, flexDirection: 'column' }}>
                  <Button 
                    variant="contained" 
                    color="primary"
                    onClick={handleManageSubscription}
                    startIcon={<SettingsIcon />}
                  >
                    Manage Subscription
                  </Button>
                  <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
                    Manage in iOS Settings → Apple ID → Subscriptions
                  </Typography>
                </Box>
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
      {!subscriptionStatus?.isActive && products.length > 0 && (
        <Grid container spacing={3} sx={{ mb: 4 }}>
          {products.map((product) => {
            const displayInfo = getProductDisplayInfo(product);
            return (
              <Grid item xs={12} md={6} key={product.id}>
                <Card 
                  sx={{ 
                    height: '100%',
                    position: 'relative',
                    ...(displayInfo.recommended && {
                      border: '2px solid',
                      borderColor: 'primary.main',
                    })
                  }}
                >
                  {displayInfo.recommended && (
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
                    title={displayInfo.name}
                    subheader={product.description}
                  />
                  
                  <CardContent>
                    <Box sx={{ textAlign: 'center', mb: 3 }}>
                      <Typography variant="h3" component="div">
                        {product.displayPrice}
                      </Typography>
                      <Typography color="text.secondary">
                        per {displayInfo.period}
                      </Typography>
                      {displayInfo.savings && (
                        <Typography variant="body2" color="primary">
                          {displayInfo.savings}
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
                      onClick={() => handlePurchase(product)}
                      disabled={purchasing === product.id}
                      startIcon={purchasing === product.id ? <CircularProgress size={20} /> : <AppleIcon />}
                    >
                      {purchasing === product.id ? 'Processing...' : 'Subscribe with Apple'}
                    </Button>
                    <Typography variant="caption" color="text.secondary" sx={{ textAlign: 'center' }}>
                      Secure payment through App Store
                    </Typography>
                  </CardActions>
                </Card>
              </Grid>
            );
          })}
        </Grid>
      )}

      {/* Restore Purchases Button */}
      <Box sx={{ textAlign: 'center', mt: 4 }}>
        <Button
          variant="outlined"
          onClick={() => setRestoreDialog(true)}
          startIcon={<RestoreIcon />}
          sx={{ mr: 2 }}
        >
          Restore Purchases
        </Button>
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          Already purchased? Restore your subscription
        </Typography>
      </Box>

      {/* Restore Purchases Dialog */}
      <Dialog open={restoreDialog} onClose={() => setRestoreDialog(false)}>
        <DialogTitle>Restore Purchases</DialogTitle>
        <DialogContent>
          <Typography>
            This will restore any previous purchases made with your Apple ID. 
            Make sure you're signed in with the same Apple ID used for the original purchase.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRestoreDialog(false)}>Cancel</Button>
          <Button onClick={handleRestorePurchases} variant="contained">
            Restore
          </Button>
        </DialogActions>
      </Dialog>

      {/* No products available */}
      {products.length === 0 && !loading && (
        <Card sx={{ textAlign: 'center', py: 4 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Subscription options unavailable
            </Typography>
            <Typography color="text.secondary" paragraph>
              Unable to load subscription options from the App Store. Please check your connection and try again.
            </Typography>
            <Button variant="contained" onClick={initializeStoreKit}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}
    </Container>
  );
};

export default iOSSubscription;

