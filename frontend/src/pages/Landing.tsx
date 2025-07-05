import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Box,
  Typography,
  Button,
  Container,
  Grid,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Alert,
  useTheme,
  alpha,
  Chip,
} from '@mui/material';
import {
  MonetizationOn as SavingsIcon,
  Receipt as ReceiptIcon,
  Notifications as NotificationsIcon,
  Analytics as AnalyticsIcon,
  ArrowForward as ArrowForwardIcon,
  ShoppingCart as CartIcon,
  Check as CheckIcon,
} from '@mui/icons-material';

const Landing: React.FC = () => {
  const theme = useTheme();

  const features = [
    {
      icon: <ReceiptIcon fontSize="large" />,
      title: 'Track Your Receipts',
      description: 'Upload and organize your Costco receipts in one place. Never lose track of your purchases again.',
    },
    {
      icon: <SavingsIcon fontSize="large" />,
      title: 'Never Miss Refunds',
      description: 'Automatic monitoring of price drops on your purchases. Get notified of every eligible refund within 30 days.',
    },
    {
      icon: <NotificationsIcon fontSize="large" />,
      title: 'Official Sale Alerts',
      description: 'Receive alerts when items you bought go on sale or have official Costco promotions within 30 days.',
    },
    {
      icon: <AnalyticsIcon fontSize="large" />,
      title: 'Shopping Analytics',
      description: 'Gain insights into your spending habits with detailed analytics and visualizations.',
    },
  ];

  return (
    <Box>

      {/* Hero Section */}
      <Box
        sx={{
          background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.primary.dark})`,
          color: 'white',
          py: 8,
          mb: 6,
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} md={7}>
              <Typography variant="h2" component="h1" gutterBottom fontWeight="bold">
                Guarantee You're Getting the Lowest Price at Costco
              </Typography>
              <Typography variant="h5" paragraph sx={{ mb: 4, opacity: 0.9 }}>
                PriceAdjustPro monitors price drops on purchases you've already made and notifies you of every eligible refund—automatically.
              </Typography>
              <Button
                variant="contained"
                size="large"
                component={RouterLink}
                to="/register"
                sx={{
                  backgroundColor: 'white',
                  color: 'primary.main',
                  '&:hover': {
                    backgroundColor: alpha('#fff', 0.9),
                  },
                  px: 4,
                  py: 1.5,
                  fontSize: '1.1rem',
                }}
                endIcon={<ArrowForwardIcon />}
              >
                Get Started
              </Button>
            </Grid>
            <Grid item xs={12} md={5}>
              <Box sx={{ textAlign: 'center' }}>
                <CartIcon sx={{ fontSize: 240, opacity: 0.9 }} />
              </Box>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Price Adjustment Policy Section */}
      <Container maxWidth="lg" sx={{ mb: 8 }}>
        <Typography variant="h4" align="center" gutterBottom>
          Costco Price Adjustment Policy
        </Typography>
        <Typography variant="h6" align="center" color="text.secondary" paragraph sx={{ mb: 6 }}>
          Eligible for refunds when prices drop within 30 days
        </Typography>

        <Grid container spacing={4}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 4, height: '100%' }}>
              <Typography variant="h5" gutterBottom color="primary">
                What is a Price Adjustment?
              </Typography>
              <Typography paragraph>
                When an item you purchased goes on sale within 30 days, Costco will refund you the difference between what you paid and the new sale price.
              </Typography>
              <Typography paragraph>
                This applies to both regular price reductions and instant savings offers that appear after your purchase.
              </Typography>
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle1" color="primary" gutterBottom>
                  Example:
                </Typography>
                <Typography>
                  You buy an item for $49.99. Two weeks later, it goes on sale for $39.99.
                  You're eligible for a $10 refund!
                </Typography>
              </Box>
            </Paper>
          </Grid>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 4, height: '100%' }}>
              <Typography variant="h5" gutterBottom color="primary">
                How to Get Your Refund
              </Typography>
              <List>
                <ListItem>
                  <ListItemIcon>
                    <CheckIcon color="success" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Visit any Costco warehouse" 
                    secondary="You can get your adjustment at any location, not just where you made the purchase."
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckIcon color="success" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Bring your membership card" 
                    secondary="It's preferred you have a copy of your receipt, but they can look up your purchase history from your membership card."
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <CheckIcon color="success" />
                  </ListItemIcon>
                  <ListItemText 
                    primary="Have the item number(s) ready" 
                    secondary="You may want a picture of the item on sale in store, but it's not required."
                  />
                </ListItem>
              </List>
              <Alert severity="success" sx={{ mt: 3 }}>
                <Typography variant="subtitle2">Request your refund!</Typography>
              </Alert>
            </Paper>
          </Grid>
        </Grid>
      </Container>

      {/* Features Section */}
      <Box sx={{ 
        bgcolor: theme.palette.mode === 'light' ? 'grey.50' : 'grey.900', 
        py: 8 
      }}>
        <Container maxWidth="lg">
          <Typography variant="h4" align="center" gutterBottom>
            How It Works
          </Typography>
          <Typography variant="h6" align="center" color="text.secondary" paragraph sx={{ mb: 6 }}>
            Start getting money back in three simple steps
          </Typography>

          <Grid container spacing={4}>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%' }}>
                <Typography variant="h4" color="primary" gutterBottom>
                  1
                </Typography>
                <Typography variant="h6" gutterBottom>
                  Get Your Receipt
                </Typography>
                <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic' }}>
                  Option 1: Download PDF from Costco.com
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <ArrowForwardIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Log in to Costco.com" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <ArrowForwardIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Click Orders & Returns" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <ArrowForwardIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Select Warehouse tab" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <ArrowForwardIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Click View Receipt" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <ArrowForwardIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Click Print Receipt" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <ArrowForwardIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Choose Save as PDF" secondary="In the print dialog" />
                  </ListItem>
                </List>
                <Typography variant="body2" sx={{ mt: 2, mb: 1, fontStyle: 'italic', fontWeight: 'bold' }}>
                  Option 2: Take a Photo (NEW!)
                </Typography>
                <Typography variant="body2" sx={{ mb: 2 }}>
                  Simply take a photo of your physical receipt with your phone camera. Our system can read through strikethrough marks!
                </Typography>
                <Button
                  variant="outlined"
                  component="a"
                  href="https://www.costco.com/OrderStatusCmd"
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{ mt: 2 }}
                >
                  Go to Costco.com
                </Button>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%' }}>
                <Typography variant="h4" color="primary" gutterBottom>
                  2
                </Typography>
                <Typography variant="h6" gutterBottom>
                  Upload Your Receipt
                </Typography>
                <Typography paragraph>
                  Create an account and upload your receipt PDFs. Our system will automatically monitor your purchase history and:
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <CheckIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Extract all item details" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <CheckIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Track prices across locations" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <CheckIcon color="success" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Monitor for price drops" />
                  </ListItem>
                </List>
                <Button
                  variant="outlined"
                  component={RouterLink}
                  to="/register"
                  sx={{ mt: 2 }}
                >
                  Start Saving
                </Button>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%' }}>
                <Typography variant="h4" color="primary" gutterBottom>
                  3
                </Typography>
                <Typography variant="h6" gutterBottom>
                  Get Notified & Save Money
                </Typography>
                <Typography paragraph>
                  We automatically monitor and notify you when:
                </Typography>
                <List dense>
                  <ListItem>
                    <ListItemIcon>
                      <NotificationsIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Items go on sale" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <NotificationsIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Instant savings appear" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon>
                      <NotificationsIcon color="primary" fontSize="small" />
                    </ListItemIcon>
                    <ListItemText primary="Lower prices found at other locations" />
                  </ListItem>
                </List>
                <Alert severity="info" sx={{ mt: 2 }}>
                  You have 30 days from your purchase date to claim your money back!
                </Alert>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>
    </Box>
  );
};

export default Landing; 