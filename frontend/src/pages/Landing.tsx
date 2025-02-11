import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Typography,
  Button,
  Box,
  Grid,
  Paper,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  useTheme,
  alpha,
} from '@mui/material';
import {
  MonetizationOn as SavingsIcon,
  Receipt as ReceiptIcon,
  Notifications as NotificationsIcon,
  Analytics as AnalyticsIcon,
  ArrowForward as ArrowForwardIcon,
  ShoppingCart as CartIcon,
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
      title: 'Save Money',
      description: 'Get notified when items you bought go on sale within 30 days. Take advantage of Costco\'s price adjustment policy.',
    },
    {
      icon: <NotificationsIcon fontSize="large" />,
      title: 'Price Drop Alerts',
      description: 'Receive alerts when other users find the same items at lower prices at different Costco locations.',
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
          py: 12,
          mb: 6,
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} md={7}>
              <Typography variant="h2" component="h1" gutterBottom fontWeight="bold">
                Save Money on Your Costco Purchases
              </Typography>
              <Typography variant="h5" paragraph sx={{ mb: 4, opacity: 0.9 }}>
                Track your receipts, get price drop alerts, and never miss out on price adjustments again.
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

      {/* Features Section */}
      <Container maxWidth="lg" sx={{ mb: 8 }}>
        <Grid container spacing={4}>
          {features.map((feature, index) => (
            <Grid item xs={12} sm={6} md={3} key={index}>
              <Paper
                elevation={2}
                sx={{
                  p: 3,
                  height: '100%',
                  transition: 'transform 0.2s',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                  },
                }}
              >
                <Box sx={{ color: 'primary.main', mb: 2 }}>
                  {feature.icon}
                </Box>
                <Typography variant="h6" gutterBottom>
                  {feature.title}
                </Typography>
                <Typography color="text.secondary">
                  {feature.description}
                </Typography>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Container>

      {/* How It Works Section */}
      <Box sx={{ bgcolor: 'grey.50', py: 8 }}>
        <Container maxWidth="lg">
          <Typography variant="h3" align="center" gutterBottom>
            How It Works
          </Typography>
          <Typography variant="h6" align="center" color="text.secondary" paragraph sx={{ mb: 6 }}>
            Start saving money in three simple steps
          </Typography>

          <Grid container spacing={4}>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%' }}>
                <Typography variant="h4" color="primary" gutterBottom>
                  1
                </Typography>
                <Typography variant="h6" gutterBottom>
                  Find Your Costco Receipts
                </Typography>
                <Typography paragraph color="text.secondary">
                  Log in to your Costco.com account, go to Orders & Returns, and download your receipt PDFs.
                </Typography>
                <Button
                  variant="outlined"
                  component="a"
                  href="https://www.costco.com/OrderStatusCmd"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Visit Costco.com
                </Button>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%' }}>
                <Typography variant="h4" color="primary" gutterBottom>
                  2
                </Typography>
                <Typography variant="h6" gutterBottom>
                  Upload Your Receipts
                </Typography>
                <Typography paragraph color="text.secondary">
                  Create an account and upload your receipt PDFs. Save time by uploading multiple receipts at once. Our system will automatically extract and organize your purchase data.
                </Typography>
                <Button
                  variant="outlined"
                  component={RouterLink}
                  to="/register"
                >
                  Create Account
                </Button>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper sx={{ p: 4, height: '100%' }}>
                <Typography variant="h4" color="primary" gutterBottom>
                  3
                </Typography>
                <Typography variant="h6" gutterBottom>
                  Start Saving
                </Typography>
                <Typography paragraph color="text.secondary">
                  Get notified when prices drop within 30 days of your purchase. Visit any Costco location to claim your price adjustment.
                </Typography>
                <Button
                  variant="outlined"
                  component={RouterLink}
                  to="/register"
                >
                  Get Started
                </Button>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Finding Receipts Guide */}
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Typography variant="h4" gutterBottom>
          How to Find Your Costco Receipts
        </Typography>
        <Paper sx={{ p: 4 }}>
          <List>
            <ListItem>
              <ListItemIcon>
                <Typography variant="h6" color="primary">1.</Typography>
              </ListItemIcon>
              <ListItemText 
                primary="Log in to Costco.com" 
                secondary="Visit Costco.com and sign in to your account"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <Typography variant="h6" color="primary">2.</Typography>
              </ListItemIcon>
              <ListItemText 
                primary="Navigate to Orders & Returns" 
                secondary="Click on 'Orders & Returns' in the top navigation menu"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <Typography variant="h6" color="primary">3.</Typography>
              </ListItemIcon>
              <ListItemText 
                primary="Find Your Order" 
                secondary="Locate the order you want to track"
              />
            </ListItem>
            <ListItem>
              <ListItemIcon>
                <Typography variant="h6" color="primary">4.</Typography>
              </ListItemIcon>
              <ListItemText 
                primary="Download Receipt" 
                secondary="Click 'View Receipt' and download the PDF"
              />
            </ListItem>
          </List>
          <Box sx={{ mt: 3 }}>
            <Button
              variant="contained"
              component="a"
              href="https://www.costco.com/OrderStatusCmd"
              target="_blank"
              rel="noopener noreferrer"
              endIcon={<ArrowForwardIcon />}
            >
              Go to Costco Orders
            </Button>
          </Box>
        </Paper>
      </Container>
    </Box>
  );
};

export default Landing; 