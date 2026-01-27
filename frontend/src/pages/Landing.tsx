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
  Card,
  CardContent,
  Divider,
  Stack,
} from '@mui/material';
import {
  MonetizationOn as SavingsIcon,
  Receipt as ReceiptIcon,
  Notifications as NotificationsIcon,
  Analytics as AnalyticsIcon,
  ArrowForward as ArrowForwardIcon,
  ShoppingCart as CartIcon,
  Check as CheckIcon,
  LocalOffer as SaleIcon,
  Star as StarIcon,
  Search as SearchIcon,
  AutoGraph as AutoGraphIcon,
  Security as SecurityIcon,
  AccessTime as TimeIcon,
} from '@mui/icons-material';

const Landing: React.FC = () => {
  const theme = useTheme();

  const features = [
    {
      icon: <ReceiptIcon fontSize="large" color="primary" />,
      title: 'AI Receipt Parsing',
      description: 'Snap a photo or upload a PDF. Our Gemini AI automatically extracts every item, price, and date with 99% accuracy.',
    },
    {
      icon: <SavingsIcon fontSize="large" color="success" />,
      title: 'Automatic Price Tracking',
      description: 'We monitor Costco prices daily. If an item you bought drops in price within 30 days, we let you know immediately.',
    },
    {
      icon: <SaleIcon fontSize="large" color="secondary" />,
      title: 'Searchable Sale Directory',
      description: 'Browse every current warehouse markdown and "Instant Rebate" in one clean, searchable list.',
      premium: true,
    },
    {
      icon: <AnalyticsIcon fontSize="large" color="info" />,
      title: 'Spend Analytics',
      description: 'Visualize your spending habits. See where your money goes and how much you save with instant rebates.',
    },
  ];

  return (
    <Box sx={{ overflow: 'hidden' }}>
      {/* Hero Section */}
      <Box
        sx={{
          position: 'relative',
          background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.primary.dark} 100%)`,
          color: 'white',
          pt: { xs: 10, md: 15 },
          pb: { xs: 10, md: 20 },
          clipPath: 'polygon(0 0, 100% 0, 100% 90%, 0% 100%)',
        }}
      >
        <Container maxWidth="lg">
          <Grid container spacing={6} alignItems="center">
            <Grid item xs={12} md={7}>
              <Box sx={{ mb: 2 }}>
                <Chip 
                  label="Trusted by Costco Shoppers Everywhere" 
                  sx={{ 
                    bgcolor: 'rgba(255,255,255,0.1)', 
                    color: 'white', 
                    fontWeight: 'bold',
                    backdropFilter: 'blur(10px)',
                    border: '1px solid rgba(255,255,255,0.2)'
                  }} 
                />
              </Box>
              <Typography 
                variant="h1" 
                sx={{ 
                  fontSize: { xs: '2.5rem', md: '4rem' }, 
                  fontWeight: 900, 
                  lineHeight: 1.1,
                  mb: 3,
                  textShadow: '0 4px 20px rgba(0,0,0,0.1)'
                }}
              >Guarantee You're Getting the <br />
                <Box component="span" sx={{ color: '#4caf50' }}>Lowest Price</Box> <br />
                At Costco.
              </Typography>
              <Typography variant="h5" sx={{ mb: 5, opacity: 0.9, maxWidth: 600, lineHeight: 1.6 }}>
                PriceAdjustPro automatically monitors price drops on your Costco purchases and notifies you of every eligible refund. 
                <br /><br />
                <strong>Upload once. Save forever.</strong>
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
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
                    px: 5,
                    py: 2,
                    fontSize: '1.2rem',
                    fontWeight: 'bold',
                    borderRadius: '50px',
                    boxShadow: '0 8px 30px rgba(0,0,0,0.2)'
                  }}
                  endIcon={<ArrowForwardIcon />}
                >
                  Start Saving Now
                </Button>
                <Button
                  variant="outlined"
                  size="large"
                  component={RouterLink}
                  to="/login"
                  sx={{
                    borderColor: 'white',
                    color: 'white',
                    '&:hover': {
                      borderColor: 'white',
                      backgroundColor: 'rgba(255,255,255,0.1)',
                    },
                    px: 5,
                    py: 2,
                    fontSize: '1.2rem',
                    borderRadius: '50px',
                  }}
                >
                  Sign In
                </Button>
              </Stack>
            </Grid>
            <Grid item xs={12} md={5} sx={{ display: { xs: 'none', md: 'block' } }}>
              <Box 
                sx={{ 
                  position: 'relative',
                  '&::before': {
                    content: '""',
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    width: '120%',
                    height: '120%',
                    background: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 70%)',
                    zIndex: 0
                  }
                }}
              >
                <CartIcon sx={{ fontSize: 350, opacity: 0.2, position: 'absolute', top: -50, right: -50, zIndex: 0 }} />
                <Paper 
                  elevation={24} 
                  sx={{ 
                    p: 3, 
                    borderRadius: 4, 
                    background: theme.palette.mode === 'dark' ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.95)', 
                    backdropFilter: 'blur(20px)',
                    position: 'relative',
                    zIndex: 1,
                    border: `1px solid ${theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(255,255,255,0.3)'}`,
                    transform: 'rotate(2deg)'
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <SavingsIcon color="success" sx={{ fontSize: 40, mr: 2 }} />
                    <Box>
                      <Typography color="text.primary" variant="subtitle2" sx={{ fontWeight: 'bold' }}>Refund Alert!</Typography>
                      <Typography color="text.secondary" variant="caption">Kirkland Coffee dropped $5.00</Typography>
                    </Box>
                  </Box>
                  <Divider sx={{ my: 1.5 }} />
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography color="text.primary" sx={{ fontWeight: 'bold' }}>Total Savings This Year</Typography>
                    <Typography color="success.main" sx={{ fontWeight: 'bold' }}>$242.50</Typography>
                  </Box>
                </Paper>
              </Box>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Main Value Propositions */}
      <Container maxWidth="lg" sx={{ mt: -10, mb: 12, position: 'relative', zIndex: 2 }}>
        <Grid container spacing={4}>
          {features.map((feature, index) => (
            <Grid item xs={12} sm={6} md={3} key={index}>
              <Card 
                sx={{ 
                  height: '100%', 
                  borderRadius: 4, 
                  transition: 'transform 0.3s ease',
                  '&:hover': { transform: 'translateY(-10px)' },
                  boxShadow: '0 10px 40px rgba(0,0,0,0.05)',
                  border: feature.premium ? `1px solid ${theme.palette.primary.light}` : 'none'
                }}
              >
                <CardContent sx={{ p: 4 }}>
                  <Box sx={{ mb: 2 }}>
                    {feature.icon}
                  </Box>
                  <Typography variant="h6" gutterBottom fontWeight="bold">
                    {feature.title}
                    {feature.premium && (
                      <Chip 
                        label="PREMIUM" 
                        size="small" 
                        color="primary" 
                        sx={{ ml: 1, height: 20, fontSize: '0.6rem', fontWeight: 900 }} 
                      />
                    )}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
                    {feature.description}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      </Container>

      {/* The "On Sale" Directory Highlight */}
      <Box sx={{ bgcolor: 'background.paper', py: 12 }}>
        <Container maxWidth="lg">
          <Grid container spacing={8} alignItems="center">
            <Grid item xs={12} md={6}>
              <Box 
                sx={{ 
                  p: 4, 
                  bgcolor: alpha(theme.palette.primary.main, 0.03), 
                  borderRadius: 8,
                  border: `2px dashed ${alpha(theme.palette.primary.main, 0.1)}`,
                  textAlign: 'center'
                }}
              >
                <Typography variant="overline" color="primary" sx={{ fontWeight: 900, letterSpacing: 2 }}>
                  EXCLUSIVE FEATURE
                </Typography>
                <Typography variant="h3" gutterBottom fontWeight="bold">
                  The Ultimate <br /> Costco Sale Tracker
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 4, fontSize: '1.1rem' }}>
                  Premium members get full access to our Live Sale Directory. 
                  Search and filter through every current Costco promotion, 
                  markdown, and instant rebate across the entire store.
                </Typography>
                <Box 
                  sx={{ 
                    display: 'flex', 
                    gap: 2, 
                    justifyContent: 'center', 
                    mb: 4,
                    flexWrap: 'wrap'
                  }}
                >
                  <Chip icon={<SearchIcon />} label="Search by Name" variant="outlined" />
                  <Chip icon={<SaleIcon />} label="Filter by Category" variant="outlined" />
                  <Chip icon={<TimeIcon />} label="Track Expiration" variant="outlined" />
                </Box>
                <Button 
                  variant="contained" 
                  component={RouterLink}
                  to="/register"
                  sx={{ px: 4, borderRadius: '50px' }}
                >
                  Explore Current Sales
                </Button>
              </Box>
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="h4" gutterBottom fontWeight="bold">
                Costco's Policy, Automated.
              </Typography>
              <Typography paragraph color="text.secondary" sx={{ fontSize: '1.1rem', mb: 4 }}>
                Costco offers price adjustments within 30 days of purchase. If an item you bought goes on sale, you're entitled to the difference.
              </Typography>
              <Paper sx={{ p: 3, borderRadius: 4, bgcolor: alpha(theme.palette.success.main, 0.05), border: `1px solid ${alpha(theme.palette.success.main, 0.1)}` }}>
                <List>
                  <ListItem>
                    <ListItemIcon><CheckIcon color="success" /></ListItemIcon>
                    <ListItemText primary="No more checking the monthly flyer manually" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon><CheckIcon color="success" /></ListItemIcon>
                    <ListItemText primary="No more missing out on sales after you've left the store" />
                  </ListItem>
                  <ListItem>
                    <ListItemIcon><CheckIcon color="success" /></ListItemIcon>
                    <ListItemText primary="Simply visit the Returns desk with the item number from our app" />
                  </ListItem>
                </List>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* Pricing Section */}
      <Box sx={{ py: 12, bgcolor: alpha(theme.palette.primary.main, 0.02) }}>
        <Container maxWidth="lg">
          <Box sx={{ textAlign: 'center', mb: 8 }}>
            <Typography variant="h2" gutterBottom fontWeight="bold">
              Simple, Transparent Pricing
            </Typography>
            <Typography variant="h6" color="text.secondary">
              The app that pays for itself in just one alert.
            </Typography>
          </Box>

          <Grid container spacing={4} justifyContent="center" alignItems="stretch">
            {/* Free Plan */}
            <Grid item xs={12} md={4}>
              <Paper 
                elevation={4} 
                sx={{ 
                  p: 5, 
                  height: '100%', 
                  borderRadius: 6,
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <Typography variant="h5" fontWeight="bold" gutterBottom>Free</Typography>
                <Typography variant="h3" sx={{ my: 2, fontWeight: 900 }}>$0</Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 4 }}>For occasional shoppers</Typography>
                <Divider sx={{ mb: 4 }} />
                <List sx={{ mb: 4, flexGrow: 1 }}>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><CheckIcon color="success" fontSize="small" /></ListItemIcon>
                    <ListItemText primary="3 Receipt Uploads" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><CheckIcon color="success" fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Advanced Spending Analytics" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><CheckIcon color="success" fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Customer Support" />
                  </ListItem>
                </List>
                <Button 
                  variant="outlined" 
                  fullWidth 
                  size="large" 
                  component={RouterLink}
                  to="/register"
                  sx={{ borderRadius: '50px', py: 1.5 }}
                >
                  Get Started
                </Button>
              </Paper>
            </Grid>

            {/* Premium Monthly */}
            <Grid item xs={12} md={4}>
              <Paper 
                elevation={24} 
                sx={{ 
                  p: 5, 
                  height: '100%', 
                  borderRadius: 6,
                  bgcolor: '#E31837', // Costco Red
                  backgroundImage: 'none',
                  color: 'white',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  overflow: 'hidden'
                }}
              >
                <Typography variant="h5" fontWeight="bold" gutterBottom>Premium (Monthly)</Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', my: 2 }}>
                  <Typography variant="h3" sx={{ fontWeight: 900 }}>$4.99</Typography>
                  <Typography variant="subtitle1" sx={{ ml: 1, opacity: 0.8 }}>/ month</Typography>
                </Box>
                <Typography variant="body2" sx={{ mb: 4, opacity: 0.8 }}>For Costco enthusiasts</Typography>
                <Divider sx={{ mb: 4, bgcolor: 'rgba(255,255,255,0.2)' }} />
                <List sx={{ mb: 4, flexGrow: 1 }}>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Unlimited Receipt Uploads" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Live Searchable Sale Directory" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Advanced Spending Analytics" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Push Notification Alerts" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Priority Support" />
                  </ListItem>
                </List>
                <Button 
                  variant="contained" 
                  fullWidth 
                  size="large" 
                  component={RouterLink}
                  to="/register"
                  sx={{ 
                    bgcolor: 'white', 
                    color: 'primary.main',
                    fontWeight: 'bold',
                    '&:hover': { bgcolor: alpha('#fff', 0.9) },
                    borderRadius: '50px',
                    py: 1.5
                  }}
                >
                  Go Monthly
                </Button>
              </Paper>
            </Grid>

            {/* Premium Yearly */}
            <Grid item xs={12} md={4}>
              <Paper 
                elevation={24} 
                sx={{ 
                  p: 5, 
                  height: '100%', 
                  borderRadius: 6,
                  bgcolor: '#E31837', // Costco Red
                  backgroundImage: 'none',
                  color: 'white',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  overflow: 'hidden',
                  transform: { md: 'scale(1.05)' },
                  zIndex: 5,
                  boxShadow: '0 20px 60px rgba(227, 24, 55, 0.3)'
                }}
              >
                <Box 
                  sx={{ 
                    position: 'absolute', 
                    top: 20, 
                    right: -30, 
                    bgcolor: 'secondary.main', 
                    color: 'white', 
                    px: 6, 
                    py: 0.5, 
                    transform: 'rotate(45deg)',
                    fontWeight: 900,
                    fontSize: '0.75rem'
                  }}
                >
                  BEST VALUE
                </Box>
                <Typography variant="h5" fontWeight="bold" gutterBottom>Premium (Yearly)</Typography>
                <Box sx={{ display: 'flex', alignItems: 'baseline', my: 2 }}>
                  <Typography variant="h3" sx={{ fontWeight: 900 }}>$49.99</Typography>
                  <Typography variant="subtitle1" sx={{ ml: 1, opacity: 0.8 }}>/ year</Typography>
                </Box>
                <Typography variant="body2" sx={{ mb: 4, opacity: 0.8, fontWeight: 'bold' }}>2 MONTHS FREE</Typography>
                <Divider sx={{ mb: 4, bgcolor: 'rgba(255,255,255,0.2)' }} />
                <List sx={{ mb: 4, flexGrow: 1 }}>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Unlimited Receipt Uploads" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Live Searchable Sale Directory" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Advanced Spending Analytics" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Push Notification Alerts" />
                  </ListItem>
                  <ListItem sx={{ px: 0 }}>
                    <ListItemIcon sx={{ minWidth: 36 }}><StarIcon sx={{ color: 'secondary.light' }} fontSize="small" /></ListItemIcon>
                    <ListItemText primary="Priority Support" />
                  </ListItem>
                </List>
                <Button 
                  variant="contained" 
                  fullWidth 
                  size="large" 
                  component={RouterLink}
                  to="/register"
                  sx={{ 
                    bgcolor: 'white', 
                    color: 'primary.main',
                    fontWeight: 'bold',
                    '&:hover': { bgcolor: alpha('#fff', 0.9) },
                    borderRadius: '50px',
                    py: 1.5
                  }}
                >
                  Go Premium
                </Button>
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>

      {/* CTA Footer */}
      <Box sx={{ py: 12, textAlign: 'center', bgcolor: 'primary.dark', color: 'white' }}>
        <Container maxWidth="md">
          <Typography variant="h3" gutterBottom fontWeight="bold">
            Ready to Start Saving?
          </Typography>
          <Typography variant="h6" sx={{ mb: 6, opacity: 0.8 }}>
            Join thousands of Costco members who never miss a refund. 
            It takes less than 60 seconds to secure your first price adjustment.
          </Typography>
          <Button
            variant="contained"
            size="large"
            component={RouterLink}
            to="/register"
            sx={{
              bgcolor: 'white',
              color: 'primary.main',
              px: 8,
              py: 2,
              fontSize: '1.2rem',
              fontWeight: 'bold',
              borderRadius: '50px',
              '&:hover': { bgcolor: alpha('#fff', 0.9) }
            }}
          >
            Create My Free Account
          </Button>
        </Container>
      </Box>
    </Box>
  );
};

export default Landing;
