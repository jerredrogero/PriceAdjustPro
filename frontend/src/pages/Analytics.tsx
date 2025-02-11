import React, { useState, useEffect } from 'react';
import {
  Container,
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Alert,
  Paper,
} from '@mui/material';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  AttachMoney as MoneyIcon,
  LocalOffer as SavingsIcon,
  Receipt as ReceiptIcon,
  ShoppingCart as CartIcon,
  Store as StoreIcon,
} from '@mui/icons-material';
import api from '../api/axios';

interface Analytics {
  total_spent: string;
  total_saved: string;
  total_receipts: number;
  total_items: number;
  average_receipt_total: string;
  most_purchased_items: Array<{
    item_code: string;
    description: string;
    count: number;
    total_spent: string;
  }>;
  spending_by_month: {
    [key: string]: {
      total: string;
      count: number;
    };
  };
  most_visited_stores: Array<{
    store: string;
    visits: number;
  }>;
  tax_paid: string;
  total_ebt_used: string;
  instant_savings: string;
}

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

const formatCurrency = (value: string): string => {
  const num = parseFloat(value);
  return num.toLocaleString('en-US', {
    style: 'decimal',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
};

const StatCard: React.FC<{
  title: string;
  value: string;
  icon: React.ReactNode;
  subtitle?: string;
}> = ({ title, value, icon, subtitle }) => (
  <Card>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        {icon}
        <Typography variant="h6" sx={{ ml: 1 }}>
          {title}
        </Typography>
      </Box>
      <Typography variant="h4" gutterBottom>
        {value}
      </Typography>
      {subtitle && (
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      )}
    </CardContent>
  </Card>
);

const Analytics: React.FC = () => {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const response = await api.get('/api/analytics/');
      setAnalytics(response.data);
    } catch (err) {
      setError('Failed to load analytics data');
      console.error('Error fetching analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LinearProgress />;
  if (error) return <Alert severity="error">{error}</Alert>;
  if (!analytics) return null;

  // Prepare data for charts
  const monthlySpending = Object.entries(analytics.spending_by_month)
    .map(([month, data]) => ({
      month: new Date(month + '-01').toLocaleDateString(undefined, {
        month: 'short',
        year: 'numeric',
      }),
      total: parseFloat(data.total),
      visits: data.count,
    }))
    .sort((a, b) => a.month.localeCompare(b.month));

  const storeVisits = analytics.most_visited_stores.map((store) => ({
    name: store.store,
    value: store.visits,
  }));

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Shopping Analytics
      </Typography>

      <Grid container spacing={3}>
        {/* Summary Stats */}
        <Grid item xs={12} md={4}>
          <StatCard
            title="Total Spent"
            value={`$${formatCurrency(analytics.total_spent)}`}
            icon={<MoneyIcon color="primary" />}
            subtitle={`${analytics.total_receipts} receipts`}
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Total Savings"
            value={`$${formatCurrency(analytics.instant_savings)}`}
            icon={<SavingsIcon color="success" />}
            subtitle="From instant savings"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Average Receipt"
            value={`$${formatCurrency(analytics.average_receipt_total)}`}
            icon={<ReceiptIcon color="info" />}
            subtitle={`${analytics.total_items} total items`}
          />
        </Grid>

        {/* Monthly Spending Chart */}
        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Monthly Spending
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
                  <Bar dataKey="total" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Store Visits */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Store Visits
            </Typography>
            <Box sx={{ height: 300 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={storeVisits}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={(entry: { name: string }) => entry.name}
                  >
                    {storeVisits.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </Box>
          </Paper>
        </Grid>

        {/* Most Purchased Items */}
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Most Purchased Items
            </Typography>
            <Box sx={{ maxHeight: 300, overflow: 'auto' }}>
              {analytics.most_purchased_items.map((item) => (
                <Box
                  key={item.item_code}
                  sx={{
                    p: 2,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    '&:last-child': { borderBottom: 'none' },
                  }}
                >
                  <Typography variant="subtitle1">
                    {item.description}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Purchased {item.count} times • Total spent: ${formatCurrency(item.total_spent)}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Container>
  );
};

export default Analytics; 