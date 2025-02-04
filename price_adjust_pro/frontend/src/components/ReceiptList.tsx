import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  CardContent,
  Typography,
  Grid,
  Chip,
  IconButton,
  Alert,
  Fade,
  Button,
  Skeleton,
  Container,
  Paper,
  Stack,
  Tooltip,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Warning as WarningIcon,
  Add as AddIcon,
  CalendarToday as DateIcon,
  Store as StoreIcon,
  ShoppingCart as CartIcon,
} from '@mui/icons-material';
import axios from 'axios';

interface Receipt {
  id: number;
  store_location: string;
  store_number: string;
  transaction_date: string;
  total: string;
  items_count: number;
  parsed_successfully: boolean;
  parse_error?: string;
}

const ReceiptList: React.FC = () => {
  const navigate = useNavigate();
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchReceipts();
  }, []);

  const fetchReceipts = async () => {
    try {
      const response = await axios.get('/api/receipts/');
      setReceipts(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load receipts');
      console.error('Error fetching receipts:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Grid container spacing={3}>
          {[1, 2, 3].map((skeleton) => (
            <Grid item xs={12} sm={6} md={4} key={skeleton}>
              <Paper elevation={2} sx={{ height: '100%' }}>
                <CardContent>
                  <Stack spacing={2}>
                    <Skeleton variant="text" width="70%" height={32} />
                    <Skeleton variant="text" width="40%" />
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Skeleton variant="text" width="30%" />
                      <Skeleton variant="rectangular" width={80} height={24} />
                    </Box>
                  </Stack>
                </CardContent>
              </Paper>
            </Grid>
          ))}
        </Grid>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert 
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={fetchReceipts}>
              Retry
            </Button>
          }
          sx={{ maxWidth: 600, mx: 'auto' }}
        >
          {error}
        </Alert>
      </Container>
    );
  }

  if (receipts.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 8 }}>
        <Fade in>
          <Paper 
            elevation={3}
            sx={{ 
              textAlign: 'center', 
              p: 6, 
              maxWidth: 500,
              mx: 'auto',
              borderRadius: 4,
              background: 'linear-gradient(to bottom right, #ffffff, #f5f5f5)'
            }}
          >
            <CartIcon sx={{ fontSize: 64, color: 'primary.main', mb: 3, opacity: 0.8 }} />
            <Typography variant="h4" color="text.primary" gutterBottom fontWeight="medium">
              No Receipts Yet
            </Typography>
            <Typography variant="body1" color="text.secondary" sx={{ mb: 4, maxWidth: 400, mx: 'auto' }}>
              Start tracking your expenses by uploading your first receipt. We'll help you organize and analyze your spending.
            </Typography>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => navigate('/upload')}
              size="large"
              sx={{
                px: 4,
                py: 1.5,
                borderRadius: 2,
                textTransform: 'none',
                fontSize: '1.1rem',
                boxShadow: 2,
                '&:hover': {
                  boxShadow: 4,
                },
              }}
            >
              Upload Your First Receipt
            </Button>
          </Paper>
        </Fade>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 5, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" component="h1" fontWeight="medium">
          Your Receipts
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/upload')}
          sx={{
            px: 3,
            py: 1,
            borderRadius: 2,
            textTransform: 'none',
            boxShadow: 2,
            '&:hover': {
              boxShadow: 4,
            },
          }}
        >
          Upload New
        </Button>
      </Box>

      <Grid container spacing={3}>
        {receipts.map((receipt, index) => (
          <Grid item xs={12} sm={6} md={4} key={receipt.id}>
            <Fade in timeout={300} style={{ transitionDelay: `${index * 100}ms` }}>
              <Paper 
                elevation={2}
                sx={{
                  height: '100%',
                  borderRadius: 3,
                  transition: 'all 0.3s ease-in-out',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: 6,
                  },
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Stack spacing={2}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <StoreIcon color="primary" />
                        <Box>
                          <Typography variant="h6" component="div">
                            {receipt.store_location}
                          </Typography>
                          {receipt.store_number && (
                            <Typography variant="caption" color="text.secondary">
                              Store #{receipt.store_number}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                      <Tooltip title="View Details">
                        <IconButton
                          onClick={() => navigate(`/receipt/${receipt.id}`)}
                          color="primary"
                          sx={{
                            backgroundColor: 'action.hover',
                            '&:hover': {
                              backgroundColor: 'primary.main',
                              color: 'primary.contrastText',
                            },
                          }}
                        >
                          <ViewIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <DateIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                      <Typography color="text.secondary">
                        {new Date(receipt.transaction_date).toLocaleDateString(undefined, {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric',
                        })}
                      </Typography>
                    </Box>

                    <Box sx={{ 
                      display: 'flex', 
                      justifyContent: 'space-between', 
                      alignItems: 'center',
                      backgroundColor: 'primary.main',
                      color: 'primary.contrastText',
                      p: 1.5,
                      borderRadius: 2,
                    }}>
                      <Typography variant="h6" component="div">
                        ${receipt.total}
                      </Typography>
                      <Chip
                        label={`${receipt.items_count} items`}
                        size="small"
                        sx={{ 
                          backgroundColor: 'rgba(255, 255, 255, 0.2)',
                          color: 'inherit',
                          '.MuiChip-label': {
                            fontWeight: 500,
                          },
                        }}
                      />
                    </Box>

                    {!receipt.parsed_successfully && (
                      <Alert
                        severity="warning"
                        icon={<WarningIcon />}
                        sx={{ 
                          borderRadius: 2,
                          '& .MuiAlert-icon': {
                            color: 'warning.dark',
                          },
                        }}
                      >
                        <Typography variant="body2">
                          Parse warning
                        </Typography>
                      </Alert>
                    )}
                  </Stack>
                </CardContent>
              </Paper>
            </Fade>
          </Grid>
        ))}
      </Grid>
    </Container>
  );
};

export default ReceiptList; 