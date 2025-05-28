import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Alert,
  LinearProgress,
  Chip,
  Fade,
  Skeleton,
  Divider,
  useTheme,
  alpha,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Warning as WarningIcon,
  PictureAsPdf as PdfIcon,
  LocalOffer as TagIcon,
  Store as StoreIcon,
  CalendarToday as DateIcon,
} from '@mui/icons-material';
import api from '../api/axios';

interface LineItem {
  id: number;
  item_code: string;
  description: string;
  price: string;
  quantity: number;
  discount: string | null;
  is_taxable: boolean;
  total_price: string;
}

interface Receipt {
  transaction_number: string;
  store_location: string;
  store_number: string;
  transaction_date: string;
  subtotal: string;
  tax: string;
  total: string;
  ebt_amount: string | null;
  instant_savings: string | null;
  items: LineItem[];
  parsed_successfully: boolean;
  parse_error: string | null;
  file: string;
}

const ReceiptDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const theme = useTheme();
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchReceipt();
  }, [id]);

  const fetchReceipt = async () => {
    try {
      const response = await api.get(`/api/receipts/${id}/`);
      setReceipt(response.data);
      setError('');
    } catch (err) {
      setError('Failed to load receipt details');
      console.error('Error fetching receipt:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box>
        <Box sx={{ mb: 3, display: 'flex', gap: 2 }}>
          <Skeleton variant="rectangular" width={120} height={36} />
          <Skeleton variant="rectangular" width={120} height={36} />
        </Box>
        <Card sx={{ mb: 3 }}>
          <CardContent>
            <Skeleton variant="text" width="60%" height={40} />
            <Skeleton variant="text" width="40%" />
            <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
              <Skeleton variant="rectangular" width={100} height={32} />
              <Skeleton variant="rectangular" width={120} height={32} />
            </Box>
          </CardContent>
        </Card>
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell colSpan={4}>
                  <Skeleton variant="text" />
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {[1, 2, 3].map((item) => (
                <TableRow key={item}>
                  <TableCell><Skeleton variant="text" /></TableCell>
                  <TableCell align="right"><Skeleton variant="text" /></TableCell>
                  <TableCell align="right"><Skeleton variant="text" /></TableCell>
                  <TableCell align="right"><Skeleton variant="text" /></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  }

  if (error || !receipt) {
    return (
      <Box sx={{ maxWidth: 600, mx: 'auto', mt: 4 }}>
        <Alert 
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={fetchReceipt}>
              Retry
            </Button>
          }
        >
          {error || 'Receipt not found'}
        </Alert>
      </Box>
    );
  }

  return (
    <Fade in>
      <Box>
        <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Button
            startIcon={<BackIcon />}
            onClick={() => navigate('/')}
            variant="outlined"
            sx={{
              '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.04),
              },
            }}
          >
            Back to Receipts
          </Button>
          {receipt.file && (
            <Button
              startIcon={<PdfIcon />}
              variant="contained"
              color="primary"
              href={receipt.file}
              target="_blank"
              sx={{
                '&:hover': {
                  backgroundColor: theme.palette.primary.dark,
                },
              }}
            >
              View PDF
            </Button>
          )}
        </Box>

        {!receipt.parsed_successfully && (
          <Alert
            severity="warning"
            sx={{ mb: 3 }}
            icon={<WarningIcon />}
            variant="outlined"
          >
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              This receipt had parsing issues
            </Typography>
            {receipt.parse_error && (
              <Typography variant="body2" color="text.secondary">
                Error: {receipt.parse_error}
              </Typography>
            )}
          </Alert>
        )}

        <Card sx={{ mb: 3, overflow: 'visible' }}>
          <CardContent>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
              <StoreIcon sx={{ mr: 1, color: 'primary.main' }} />
              <Typography variant="h5">
                {receipt.store_location}
                {receipt.store_number && (
                  <Typography component="span" variant="subtitle1" sx={{ ml: 1, color: 'text.secondary' }}>
                    #{receipt.store_number && receipt.store_number.toLowerCase() !== 'null' ? receipt.store_number : 'Unknown'}
                  </Typography>
                )}
              </Typography>
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', color: 'text.secondary', mb: 2 }}>
              <DateIcon sx={{ mr: 1, fontSize: 20 }} />
              <Typography>
                {new Date(receipt.transaction_date).toLocaleString(undefined, {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Chip
                icon={<TagIcon />}
                label={`${receipt.items.length} items`}
                color="primary"
                variant="outlined"
              />
              {receipt.instant_savings && (
                <Chip
                  label={`Savings: $${receipt.instant_savings}`}
                  color="success"
                  variant="outlined"
                />
              )}
              {receipt.ebt_amount && (
                <Chip
                  label={`EBT: $${receipt.ebt_amount}`}
                  color="info"
                  variant="outlined"
                />
              )}
            </Box>
          </CardContent>
        </Card>

        <TableContainer 
          component={Paper} 
          sx={{ 
            mb: 3,
            '& .MuiTableCell-head': {
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
            },
          }}
        >
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Item</TableCell>
                <TableCell align="right">Price</TableCell>
                <TableCell align="right">Qty</TableCell>
                <TableCell align="right">Total</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {receipt.items?.map((item, index) => (
                <TableRow 
                  key={item.id}
                  sx={{
                    backgroundColor: index % 2 === 0 ? 'background.paper' : 'action.hover',
                    '&:hover': {
                      backgroundColor: 'action.selected',
                    },
                  }}
                >
                  <TableCell>
                    <Typography>{item.description}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      #{item.item_code}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">${item.price}</TableCell>
                  <TableCell align="right">{item.quantity}</TableCell>
                  <TableCell align="right">
                    ${item.total_price}
                    {item.discount && (
                      <Typography variant="caption" color="success.main" display="block">
                        -${item.discount}
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}

              <TableRow>
                <TableCell colSpan={4}>
                  <Divider sx={{ my: 2 }} />
                </TableCell>
              </TableRow>

              <TableRow>
                <TableCell colSpan={3} align="right">
                  <Typography variant="subtitle1">Subtotal</Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="subtitle1">${receipt.subtotal}</Typography>
                </TableCell>
              </TableRow>

              {receipt.instant_savings && (
                <TableRow>
                  <TableCell colSpan={3} align="right">
                    <Typography variant="subtitle1" color="success.main">
                      Instant Savings
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="subtitle1" color="success.main">
                      -${receipt.instant_savings}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}

              <TableRow>
                <TableCell colSpan={3} align="right">
                  <Typography variant="subtitle1">Tax</Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="subtitle1">${receipt.tax}</Typography>
                </TableCell>
              </TableRow>

              {receipt.ebt_amount && (
                <TableRow>
                  <TableCell colSpan={3} align="right">
                    <Typography variant="subtitle1" color="info.main">
                      EBT Amount
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="subtitle1" color="info.main">
                      ${receipt.ebt_amount}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}

              <TableRow>
                <TableCell colSpan={3} align="right">
                  <Typography variant="h6" color="primary.main">Total</Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="h6" color="primary.main">${receipt.total}</Typography>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    </Fade>
  );
};

export default ReceiptDetail; 