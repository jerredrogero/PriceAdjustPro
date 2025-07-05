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
  LineChart,
  Line,
  Area,
  AreaChart,
} from 'recharts';
import {
  AttachMoney as MoneyIcon,
  LocalOffer as SavingsIcon,
  Receipt as ReceiptIcon,
  ShoppingCart as CartIcon,
  Store as StoreIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
  Category as CategoryIcon,
  Notifications as AlertIcon,
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

interface EnhancedAnalytics {
  trends: {
    current_period_spending: number;
    previous_period_spending: number;
    spending_change: number;
    spending_change_percent: number;
    current_period_receipts: number;
    previous_period_receipts: number;
    receipts_change: number;
    receipts_change_percent: number;
    weekly_spending: Array<{
      week: string;
      total: number;
      count: number;
    }>;
  };
  categories: Array<{
    category: string;
    total: number;
    count: number;
    items: number;
  }>;
  savings_tracking: {
    total_potential_savings: number;
    active_alerts: number;
    savings_by_month: {
      [key: string]: {
        savings: number;
        count: number;
      };
    };
  };
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

const TrendCard: React.FC<{
  title: string;
  current: number;
  previous: number;
  change: number;
  changePercent: number;
  icon: React.ReactNode;
  format?: 'currency' | 'number';
}> = ({ title, current, previous, change, changePercent, icon, format = 'currency' }) => {
  const isPositive = change >= 0;
  const formatValue = (value: number) => {
    if (format === 'currency') {
      return `$${value.toFixed(2)}`;
    }
    return value.toString();
  };

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          {icon}
          <Typography variant="h6" sx={{ ml: 1 }}>
            {title}
          </Typography>
        </Box>
        <Typography variant="h4" gutterBottom>
          {formatValue(current)}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          {isPositive ? (
            <TrendingUpIcon color={format === 'currency' ? 'error' : 'success'} sx={{ mr: 1 }} />
          ) : (
            <TrendingDownIcon color={format === 'currency' ? 'success' : 'error'} sx={{ mr: 1 }} />
          )}
          <Typography
            variant="body2"
            color={
              format === 'currency'
                ? isPositive ? 'error.main' : 'success.main'
                : isPositive ? 'success.main' : 'error.main'
            }
          >
            {formatValue(Math.abs(change))} ({Math.abs(changePercent).toFixed(1)}%) vs last month
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

const Analytics: React.FC = () => {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [enhancedAnalytics, setEnhancedAnalytics] = useState<EnhancedAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const [basicResponse, enhancedResponse] = await Promise.all([
        api.get('/api/analytics/'),
        api.get('/api/analytics/enhanced/')
      ]);
      setAnalytics(basicResponse.data);
      setEnhancedAnalytics(enhancedResponse.data);
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
    .map(([month, data]) => {
      // Parse month string safely to avoid timezone issues
      const [year, monthNum] = month.split('-');
      const monthNames = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
      ];
      const monthName = monthNames[parseInt(monthNum) - 1];
      
      return {
        month: `${monthName} ${year}`,
        total: parseFloat(data.total),
        visits: data.count,
      };
    })
    .sort((a, b) => {
      // Sort by year-month for proper chronological order
      const monthNames = [
        'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
      ];
      const getYearMonth = (item: { month: string }) => {
        const parts = item.month.split(' ');
        const year = parseInt(parts[1]);
        const monthIndex = monthNames.findIndex(m => m === parts[0]);
        return year * 12 + monthIndex;
      };
      return getYearMonth(a) - getYearMonth(b);
    });

  const storeVisits = analytics.most_visited_stores.map((store) => ({
    name: store.store,
    value: store.visits,
  }));

  // Prepare enhanced analytics data
  const weeklyTrend = enhancedAnalytics?.trends.weekly_spending.map(week => ({
    ...week,
    week: new Date(week.week).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  })) || [];

  const categoriesData = enhancedAnalytics?.categories.map(cat => ({
    name: cat.category,
    value: cat.total,
    count: cat.count
  })) || [];

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" gutterBottom>
        Shopping Analytics
      </Typography>

      <Grid container spacing={3}>
        {/* Trend Cards Section */}
        {enhancedAnalytics && (
          <>
            <Grid item xs={12}>
              <Typography variant="h5" gutterBottom sx={{ mt: 2, mb: 1 }}>
                Monthly Trends
              </Typography>
            </Grid>
            <Grid item xs={12} md={6}>
              <TrendCard
                title="Monthly Spending"
                current={enhancedAnalytics.trends.current_period_spending}
                previous={enhancedAnalytics.trends.previous_period_spending}
                change={enhancedAnalytics.trends.spending_change}
                changePercent={enhancedAnalytics.trends.spending_change_percent}
                icon={<MoneyIcon color="primary" />}
                format="currency"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <TrendCard
                title="Shopping Frequency"
                current={enhancedAnalytics.trends.current_period_receipts}
                previous={enhancedAnalytics.trends.previous_period_receipts}
                change={enhancedAnalytics.trends.receipts_change}
                changePercent={enhancedAnalytics.trends.receipts_change_percent}
                icon={<ReceiptIcon color="info" />}
                format="number"
              />
            </Grid>
          </>
        )}

        {/* Summary Stats Section */}
        <Grid item xs={12}>
          <Typography variant="h5" gutterBottom sx={{ mt: 3, mb: 1 }}>
            Overview
          </Typography>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Spent"
            value={`$${formatCurrency(analytics.total_spent)}`}
            icon={<MoneyIcon color="primary" />}
            subtitle={`${analytics.total_receipts} receipts`}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Total Savings"
            value={`$${formatCurrency(analytics.instant_savings)}`}
            icon={<SavingsIcon color="success" />}
            subtitle="From instant savings"
          />
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <StatCard
            title="Average Receipt"
            value={`$${formatCurrency(analytics.average_receipt_total)}`}
            icon={<ReceiptIcon color="info" />}
            subtitle={`${analytics.total_items} total items`}
          />
        </Grid>
        
        {/* Savings Tracking Card */}
        {enhancedAnalytics && (
          <Grid item xs={12} sm={6} md={3}>
            <StatCard
              title="Price Adjustment Savings"
              value={`$${enhancedAnalytics.savings_tracking.total_potential_savings.toFixed(2)}`}
              icon={<AlertIcon color="warning" />}
              subtitle={`${enhancedAnalytics.savings_tracking.active_alerts} active opportunities`}
            />
          </Grid>
        )}

        {/* Charts Section */}
        <Grid item xs={12}>
          <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 1 }}>
            Detailed Analytics
          </Typography>
        </Grid>

        {/* Weekly Spending Trend */}
        {enhancedAnalytics && (
          <Grid item xs={12}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Weekly Spending Trend (Last 12 Weeks)
              </Typography>
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer>
                  <LineChart data={weeklyTrend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="week" />
                    <YAxis />
                    <Tooltip
                      formatter={(value: number) => ['$' + value.toFixed(2), 'Spending']}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="total" 
                      stroke="#8884d8" 
                      strokeWidth={2}
                      dot={{ fill: '#8884d8' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Category Spending */}
        {enhancedAnalytics && (
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 3 }}>
              <Typography variant="h6" gutterBottom>
                Spending by Category
              </Typography>
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={categoriesData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label={(entry: { name: string; value: number }) => 
                        `${entry.name}: $${entry.value.toFixed(0)}`
                      }
                    >
                      {categoriesData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={COLORS[index % COLORS.length]}
                        />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => [
                        `$${value.toFixed(2)}`, 
                        name
                      ]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
            </Paper>
          </Grid>
        )}

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
            <Box sx={{ height: 300, width: '100%', overflow: 'hidden' }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={storeVisits}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={(entry: { name: string; value: number }) => {
                      // Truncate long store names and show visit count
                      const storeName = entry.name.length > 20 
                        ? entry.name.substring(0, 17) + '...' 
                        : entry.name;
                      return `${storeName} (${entry.value})`;
                    }}
                    labelLine={false}
                  >
                    {storeVisits.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={COLORS[index % COLORS.length]}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name: string) => [value, `${name} visits`]}
                  />
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