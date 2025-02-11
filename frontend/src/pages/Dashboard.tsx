import React, { useState, useEffect } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  LinearProgress,
  Alert,
  Paper,
  Divider,
  useTheme,
  alpha,
} from '@mui/material';
import {
  AttachMoney as MoneyIcon,
  LocalOffer as SavingsIcon,
  Receipt as ReceiptIcon,
  ShoppingCart as CartIcon,
  Add as AddIcon,
  TrendingDown as TrendingDownIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import api from '../api/axios';
import { Receipt, PriceAdjustment } from '../types';
import PriceAdjustmentAlert from '../components/PriceAdjustmentAlert';

interface AnalyticsSummary {
  total_spent: string;
  instant_savings: string;
  total_receipts: number;
  total_items: number;
  average_receipt_total: string;
  spending_by_month: {
    [key: string]: {
      total: string;
      count: number;
    };
  };
}

const formatCurrency = (value: string | null | undefined): string => {
  if (!value) return '$0.00';
  const num = parseFloat(value);
  return num.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};

const StatCard: React.FC<{
  title: string;
  value: string;
  icon: React.ReactNode;
  subtitle?: string;
  to?: string;
}> = ({ title, value, icon, subtitle, to }) => {
  const theme = useTheme();
  const content = (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          {React.cloneElement(icon as React.ReactElement, {
            sx: { fontSize: 32, color: 'primary.main' }
          })}
          <Typography variant="h6" sx={{ ml: 1 }}>
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" gutterBottom>
          {formatCurrency(value)}
        </Typography>
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </Card>
  );

  return to ? (
    <RouterLink to={to} style={{ textDecoration: 'none' }}>
      {content}
    </RouterLink>
  ) : content;
};

const Dashboard: React.FC = () => {
  const theme = useTheme();
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [recentReceipts, setRecentReceipts] = useState<Receipt[]>([]);
  const [priceAdjustments, setPriceAdjustments] = useState<PriceAdjustment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetchAnalytics(),
      fetchRecentReceipts(),
      fetchPriceAdjustments(),
    ]).finally(() => setLoading(false));
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get('/api/analytics/');
      setAnalytics(response.data);
    } catch (err) {
      console.error('Error fetching analytics:', err);
    }
  };

  const fetchRecentReceipts = async () => {
    try {
      const response = await api.get('/api/receipts/');
      setRecentReceipts(response.data.receipts.slice(0, 3));
    } catch (err) {
      console.error('Error fetching receipts:', err);
    }
  };

  const fetchPriceAdjustments = async () => {
    try {
      const response = await api.get('/api/price-adjustments/');
      setPriceAdjustments(response.data.adjustments);
    } catch (err) {
      console.error('Error fetching price adjustments:', err);
    }
  };

  if (loading) return <LinearProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;

  const monthlySpending = analytics?.spending_by_month
    ? Object.entries(analytics.spending_by_month)
        .map(([month, data]) => ({
          month: format(new Date(month + '-01'), 'MMM yyyy'),
          total: parseFloat(data.total),
          visits: data.count,
        }))
        .sort((a, b) => a.month.localeCompare(b.month))
        .slice(-6)
    : [];

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Box sx={{ mb: 4, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4">
          Dashboard
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          component={RouterLink}
          to="/upload"
        >
          Upload Receipt
        </Button>
      </Box>

      {priceAdjustments.length > 0 && (
        <Paper
          elevation={0}
          sx={{
            p: 3,
            mb: 4,
            backgroundColor: alpha(theme.palette.info.main, 0.1),
            border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
            borderRadius: 2,
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <TrendingDownIcon color="info" sx={{ fontSize: 32 }} />
              <Box>
                <Typography variant="h6" gutterBottom sx={{ color: 'info.main' }}>
                  Price Adjustment Opportunities
                </Typography>
                <Typography variant="body1">
                  You have {priceAdjustments.length} items eligible for price adjustment
                </Typography>
              </Box>
            </Box>
            <Button
              variant="contained"
              color="info"
              endIcon={<ArrowForwardIcon />}
              component={RouterLink}
              to="/adjustments"
            >
              View Details
            </Button>
          </Box>
        </Paper>
      )}

      <Grid container spacing={3}>
        {/* Stats */}
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Spent"
            value={analytics ? analytics.total_spent : '0'}
            icon={<MoneyIcon />}
            subtitle={`${analytics?.total_receipts || 0} receipts`}
            to="/analytics"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Savings"
            value={analytics ? analytics.instant_savings : '0'}
            icon={<SavingsIcon />}
            subtitle="From instant savings"
            to="/analytics"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Average Receipt"
            value={analytics ? analytics.average_receipt_total : '0'}
            icon={<ReceiptIcon />}
            subtitle={`${analytics?.total_items || 0} total items`}
            to="/receipts"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Adjustments"
            value={priceAdjustments.length.toString()}
            icon={<TrendingDownIcon />}
            subtitle="Available opportunities"
            to="/adjustments"
          />
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Typography variant="h6" gutterBottom>
              Recent Spending
            </Typography>
            <Box sx={{ height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={monthlySpending}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="month" />
                  <YAxis />
                  <Tooltip
                    formatter={(value: number) => ['$' + value.toFixed(2), 'Total']}
                  />
                  <Bar dataKey="total" fill={theme.palette.primary.main} />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Recent Receipts */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, height: '100%' }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6">
                Recent Receipts
              </Typography>
              <Button
                component={RouterLink}
                to="/receipts"
                endIcon={<ArrowForwardIcon />}
                size="small"
              >
                View All
              </Button>
            </Box>
            {recentReceipts.map((receipt, index) => (
              <React.Fragment key={receipt.transaction_number}>
                <Box sx={{ py: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                    <Typography variant="subtitle1">
                      Receipt #{receipt.transaction_number.slice(-4)}
                    </Typography>
                    <Typography variant="subtitle1" color="primary">
                      ${receipt.total}
                    </Typography>
                  </Box>
                  <Typography variant="body2" color="text.secondary">
                    {format(new Date(receipt.transaction_date), 'MMM d, yyyy')}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {receipt.store_location}
                  </Typography>
                </Box>
                {index < recentReceipts.length - 1 && <Divider />}
              </React.Fragment>
            ))}
            {recentReceipts.length === 0 && (
              <Typography color="text.secondary" align="center">
                No receipts yet
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

export default Dashboard; 