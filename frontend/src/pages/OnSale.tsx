import React, { useState, useEffect, useRef, useContext } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Container,
  Paper,
  Divider,
  TextField,
  InputAdornment,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  Fade,
  Button,
} from '@mui/material';
import {
  LocalOffer as SaleIcon,
  Search as SearchIcon,
  Schedule as TimeIcon,
  TrendingDown as SavingsIcon,
  Store as StoreIcon,
  Star as StarIcon,
  Upgrade as UpgradeIcon,
} from '@mui/icons-material';
import { useTheme, alpha } from '@mui/material/styles';
import { useLocation, useSearchParams, Link as RouterLink } from 'react-router-dom';
import { UserContext } from '../components/Layout';

interface SaleItem {
  id: number;
  item_code: string;
  description: string;
  regular_price: number | string | null;
  sale_price: number | string | null;
  instant_rebate: number | string | null;
  savings: number | string | null;
  sale_type: string;
  promotion: {
    title: string;
    sale_start_date: string;
    sale_end_date: string;
    days_remaining: number;
  };
}

interface Promotion {
  title: string;
  sale_start_date: string;
  sale_end_date: string;
  items_count: number;
}

interface SalesData {
  sales: SaleItem[];
  total_count: number;
  active_promotions: Promotion[];
  current_date: string;
  last_updated: string;
}

const OnSale: React.FC = () => {
  const theme = useTheme();
  const location = useLocation();
  const user = useContext(UserContext);
  const [searchParams] = useSearchParams();
  const [salesData, setSalesData] = useState<SalesData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [highlightedItemCode, setHighlightedItemCode] = useState<string | null>(null);
  const highlightedItemRef = useRef<HTMLDivElement>(null);

  const isPremium = user?.account_type === 'paid' || user?.is_paid_account;

  useEffect(() => {
    if (isPremium) {
      fetchCurrentSales();
      
      // Auto-refresh every hour to catch new promotions
      const interval = setInterval(() => {
        fetchCurrentSales();
      }, 60 * 60 * 1000); // 1 hour
      
      return () => clearInterval(interval);
    } else {
      setLoading(false);
    }
  }, [isPremium]);

  // Check for item parameter in URL and handle highlighting
  useEffect(() => {
    const itemCode = searchParams.get('item');
    if (itemCode) {
      setHighlightedItemCode(itemCode);
      setSearchTerm(itemCode); // Also filter to show the item
      
      // Scroll to the highlighted item after data loads
      if (salesData && highlightedItemRef.current) {
        setTimeout(() => {
          highlightedItemRef.current?.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
          });
        }, 500);
      }
    }
  }, [searchParams, salesData]);

  // Extract category from item description
  const extractCategory = (description: string): string => {
    const desc = description.toLowerCase();
    
    // Pet Supplies (check this before Baby & Kids to avoid "toy" conflicts)
    if (desc.includes('kong') || desc.includes('pet') || desc.includes('dog') || 
        desc.includes('cat') || desc.includes('puppy') || desc.includes('kitten') || 
        desc.includes('bird') || desc.includes('fish') || desc.includes('reptile') ||
        desc.includes('pet food') || desc.includes('dog food') || desc.includes('cat food') ||
        desc.includes('treats') || desc.includes('leash') || desc.includes('collar') ||
        desc.includes('litter') || desc.includes('aquarium') || desc.includes('pet toy') ||
        desc.includes('chew') || desc.includes('pet bed') || desc.includes('pet carrier')) {
      return 'Pet Supplies';
    }
    
    // Food & Beverages
    if (desc.includes('organic') || desc.includes('fruit') || desc.includes('vegetable') || 
        desc.includes('meat') || desc.includes('chicken') || desc.includes('beef') || 
        desc.includes('fish') || desc.includes('salmon') || desc.includes('cheese') || 
        desc.includes('milk') || desc.includes('bread') || desc.includes('cereal') ||
        desc.includes('snack') || desc.includes('cookie') || desc.includes('chip') ||
        desc.includes('juice') || desc.includes('water') || desc.includes('coffee') ||
        desc.includes('tea') || desc.includes('wine') || desc.includes('beer')) {
      return 'Food & Beverages';
    }
    
    // Electronics
    if (desc.includes('tv') || desc.includes('television') || desc.includes('computer') || 
        desc.includes('laptop') || desc.includes('phone') || desc.includes('tablet') || 
        desc.includes('camera') || desc.includes('speaker') || desc.includes('headphone') ||
        desc.includes('monitor') || desc.includes('printer') || desc.includes('electronic') ||
        desc.includes('battery') || desc.includes('charger') || desc.includes('apple') ||
        desc.includes('samsung') || desc.includes('sony')) {
      return 'Electronics';
    }
    
    // Health & Beauty
    if (desc.includes('vitamin') || desc.includes('supplement') || desc.includes('lotion') || 
        desc.includes('shampoo') || desc.includes('soap') || desc.includes('toothpaste') || 
        desc.includes('cosmetic') || desc.includes('skincare') || desc.includes('perfume') ||
        desc.includes('deodorant') || desc.includes('health') || desc.includes('beauty') ||
        desc.includes('fiber') || desc.includes('gummies') || desc.includes('gummy') ||
        desc.includes('probiotic') || desc.includes('omega') || desc.includes('multivitamin') ||
        desc.includes('razor') || desc.includes('gillette') || desc.includes('shave') ||
        desc.includes('cartridge') || desc.includes('blade') || desc.includes('personal care') ||
        desc.includes('oral care') || desc.includes('dental') || desc.includes('mouthwash') ||
        desc.includes('sunscreen') || desc.includes('moisturizer') || desc.includes('serum') ||
        desc.includes('cream') || desc.includes('ointment') || desc.includes('chapstick') ||
        desc.includes('lip balm') || desc.includes('medicine') || desc.includes('pain relief') ||
        desc.includes('allergy') || desc.includes('cold') || desc.includes('flu')) {
      return 'Health & Beauty';
    }
    
    // Household & Cleaning
    if (desc.includes('detergent') || desc.includes('cleaner') || desc.includes('paper towel') || 
        desc.includes('toilet paper') || desc.includes('laundry') || desc.includes('dish') || 
        desc.includes('household') || desc.includes('cleaning') || desc.includes('trash bag') ||
        desc.includes('tissue') || desc.includes('napkin')) {
      return 'Household & Cleaning';
    }
    
    // Clothing & Accessories
    if (desc.includes('shirt') || desc.includes('pants') || desc.includes('jacket') || 
        desc.includes('shoe') || desc.includes('sock') || desc.includes('clothing') || 
        desc.includes('apparel') || desc.includes('hat') || desc.includes('belt') ||
        desc.includes('jean') || desc.includes('dress')) {
      return 'Clothing & Accessories';
    }
    
    // Home & Garden
    if (desc.includes('furniture') || desc.includes('mattress') || desc.includes('pillow') || 
        desc.includes('blanket') || desc.includes('towel') || desc.includes('garden') || 
        desc.includes('plant') || desc.includes('tool') || desc.includes('storage') ||
        desc.includes('decor') || desc.includes('lighting') || desc.includes('outdoor')) {
      return 'Home & Garden';
    }
    
    // Baby & Kids (check this after Pet Supplies to avoid conflicts)
    if (desc.includes('baby') || desc.includes('infant') || desc.includes('kid') || 
        desc.includes('child') || desc.includes('diaper') || desc.includes('formula') || 
        desc.includes('stroller') || (desc.includes('toy') && !desc.includes('pet'))) {
      return 'Baby & Kids';
    }
    
    // Automotive
    if (desc.includes('tire') || desc.includes('car') || desc.includes('auto') || 
        desc.includes('motor oil') || desc.includes('battery') || desc.includes('automotive')) {
      return 'Automotive';
    }
    
    return 'Other';
  };

  // Get unique categories from current sales
  const getAvailableCategories = (): string[] => {
    if (!salesData) return [];
    
    const categories = new Set<string>();
    salesData.sales.forEach(sale => {
      categories.add(extractCategory(sale.description));
    });
    
    return Array.from(categories).sort();
  };

  const fetchCurrentSales = async () => {
    try {
      const response = await fetch('/api/on-sale/', {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setSalesData(data);
    } catch (err) {
      console.error('Error fetching current sales:', err);
      setError('Failed to fetch current sales data.');
    } finally {
      setLoading(false);
    }
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(event.target.value);
  };

  const handleCategoryChange = (event: SelectChangeEvent) => {
    setCategoryFilter(event.target.value);
  };

  const toNumber = (value: number | string | null | undefined): number | null => {
    if (value === null || value === undefined) return null;
    if (typeof value === 'number') {
      return Number.isFinite(value) ? value : null;
    }
    const parsed = parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const formatPrice = (price: number | string | null): string => {
    const numericPrice = toNumber(price);
    return numericPrice !== null ? `$${numericPrice.toFixed(2)}` : 'N/A';
  };

  const formatEndDate = (dateString: string): string => {
    // Parse the date string as a local date to avoid timezone issues
    const [year, month, day] = dateString.split('-').map(Number);
    const endDate = new Date(year, month - 1, day); // month - 1 because JS months are 0-indexed
    
    return endDate.toLocaleDateString('en-US', {
      month: 'numeric',
      day: 'numeric', 
      year: 'numeric'
    });
  };

  const formatDaysRemaining = (days: number): string => {
    if (days === 0) return 'Ends today';
    if (days === 1) return '1 day left';
    if (days < 0) return 'Expired';
    return `${days} days left`;
  };

  const getSaleTypeLabel = (saleType: string): string => {
    const labels: { [key: string]: string } = {
      instant_rebate: 'Instant Rebate',
      discount_only: 'Instant Rebate',
      markdown: 'Markdown Sale',
      member_only: 'Member Only Deal',
      manufacturer: 'Manufacturer Coupon',
    };
    return labels[saleType] || saleType;
  };

  const getSaleTypeColor = (saleType: string) => {
    const colors: { [key: string]: "primary" | "secondary" | "success" | "error" | "warning" } = {
      instant_rebate: 'success',
      discount_only: 'success',
      markdown: 'warning',
      member_only: 'secondary',
      manufacturer: 'error',
    };
    return colors[saleType] || 'primary';
  };

  // Filter sales based on search term and category
  const filteredSales = salesData?.sales.filter(sale => {
    const matchesSearch = searchTerm === '' || 
      sale.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
      sale.item_code.toLowerCase().includes(searchTerm.toLowerCase());
    
    let matchesCategory = false;
    if (categoryFilter === 'all') {
      matchesCategory = true;
    } else {
      matchesCategory = extractCategory(sale.description) === categoryFilter;
    }
    
    return matchesSearch && matchesCategory;
  }) || [];

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <CircularProgress size={60} />
        </Box>
      </Container>
    );
  }

  if (!isPremium) {
    return (
      <Container maxWidth="md" sx={{ py: 8 }}>
        <Paper 
          elevation={3} 
          sx={{ 
            p: 6, 
            textAlign: 'center',
            borderRadius: 4,
            background: `linear-gradient(135deg, ${theme.palette.background.paper} 0%, ${alpha(theme.palette.primary.main, 0.05)} 100%)`,
            border: `1px solid ${alpha(theme.palette.primary.main, 0.1)}`,
          }}
        >
          <Box sx={{ mb: 4 }}>
            <Box 
              sx={{ 
                width: 80, 
                height: 80, 
                borderRadius: '50%', 
                backgroundColor: alpha(theme.palette.primary.main, 0.1), 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center',
                margin: '0 auto',
                mb: 2
              }}
            >
              <StarIcon sx={{ fontSize: 48, color: 'primary.main' }} />
            </Box>
            <Typography variant="h3" gutterBottom fontWeight="bold">
              Premium Feature
            </Typography>
            <Typography variant="h6" color="text.secondary" paragraph>
              The "On Sale" directory is exclusive to PriceAdjustPro Premium members.
            </Typography>
          </Box>

          <Grid container spacing={3} sx={{ mb: 6, textAlign: 'left' }}>
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%', backgroundColor: 'transparent' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold" gutterBottom display="flex" alignItems="center">
                    <SaleIcon sx={{ mr: 1, color: 'success.main' }} />
                    Live Sale Directory
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Browse all current Costco promotions and markdowns in one searchable list.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card variant="outlined" sx={{ height: '100%', backgroundColor: 'transparent' }}>
                <CardContent>
                  <Typography variant="subtitle1" fontWeight="bold" gutterBottom display="flex" alignItems="center">
                    <SavingsIcon sx={{ mr: 1, color: 'primary.main' }} />
                    Price Drop Tracking
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Get alerted the moment items you've already purchased go on sale.
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Button
            variant="contained"
            size="large"
            component={RouterLink}
            to="/subscription"
            startIcon={<UpgradeIcon />}
            sx={{ 
              px: 6, 
              py: 1.5, 
              fontSize: '1.1rem',
              borderRadius: 3,
              textTransform: 'none',
              fontWeight: 'bold',
              boxShadow: theme.shadows[4],
            }}
          >
            Upgrade to Premium
          </Button>
          
          <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
            Starting at just $4.99/month
          </Typography>
        </Paper>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      </Container>
    );
  }

  if (!salesData || salesData.sales.length === 0) {
    return (
      <Container maxWidth="lg" sx={{ py: 4 }}>
        <Box textAlign="center" py={8}>
          <SaleIcon sx={{ fontSize: 80, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h4" gutterBottom color="text.secondary">
            No Current Sales
          </Typography>
          <Typography variant="body1" color="text.secondary">
            There are no active sales or promotions available at this time.
          </Typography>
        </Box>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      {/* Header */}
      <Box mb={4}>
        <Typography variant="h3" component="h1" gutterBottom fontWeight="bold">
          <SaleIcon sx={{ mr: 2, verticalAlign: 'middle' }} />
          Current Sales & Promotions
        </Typography>
        <Typography variant="h6" color="text.secondary" gutterBottom>
          Shop the latest deals from Costco's weekly flyers
        </Typography>
        {salesData && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            📅 Current date: {new Date(salesData.current_date).toLocaleDateString()} • 
            🔄 Last updated: {new Date(salesData.last_updated).toLocaleString()} • 
            📦 {salesData.total_count} items on sale
          </Typography>
        )}
      </Box>

      {/* Highlight alert when coming from price adjustment */}
      {highlightedItemCode && (
        <Alert 
          severity="success" 
          sx={{ mb: 3 }}
          onClose={() => setHighlightedItemCode(null)}
        >
          <Typography variant="body1">
            <strong>🎯 Price Adjustment Alert!</strong> We found the item you're looking for (#{highlightedItemCode}). 
            It's highlighted below with a green border. Show this page to customer service to request your price adjustment.
          </Typography>
        </Alert>
      )}

      {/* Active Promotions Summary */}
      {salesData.active_promotions.length > 0 && (
        <Paper elevation={2} sx={{ p: 3, mb: 4, backgroundColor: theme.palette.primary.main, color: 'white' }}>
          <Typography variant="h5" gutterBottom>
            <StoreIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
            Active Promotions
          </Typography>
          <Grid container spacing={2}>
            {salesData.active_promotions.map((promo, index) => (
              <Grid item xs={12} md={6} lg={4} key={index}>
                <Box 
                  sx={{ 
                    backgroundColor: 'rgba(255, 255, 255, 0.1)', 
                    borderRadius: 1, 
                    p: 2,
                    border: '1px solid rgba(255, 255, 255, 0.2)'
                  }}
                >
                  <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                    {promo.title}
                  </Typography>
                  <Typography variant="body2">
                    {promo.items_count} items on sale
                  </Typography>
                  <Typography variant="body2">
                    Ends: {formatEndDate(promo.sale_end_date)}
                  </Typography>
                </Box>
              </Grid>
            ))}
          </Grid>
        </Paper>
      )}

      {/* Search and Filter Controls */}
      <Paper elevation={1} sx={{ p: 3, mb: 4 }}>
        <Grid container spacing={3} alignItems="center">
          <Grid item xs={12} md={8}>
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Search by item name or code..."
              value={searchTerm}
              onChange={handleSearchChange}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Grid>
          <Grid item xs={12} md={4}>
            <FormControl fullWidth variant="outlined">
              <InputLabel>Category</InputLabel>
              <Select
                value={categoryFilter}
                onChange={handleCategoryChange}
                label="Category"
              >
                <MenuItem value="all">All Categories</MenuItem>
                {getAvailableCategories().map((category, index) => (
                  <MenuItem key={index} value={category}>{category}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>
        <Box mt={2}>
          <Typography variant="body2" color="text.secondary">
            Showing {filteredSales.length} of {salesData.total_count} sale items
            {categoryFilter !== 'all' && ` in ${categoryFilter}`}
          </Typography>
        </Box>
      </Paper>

      {/* Sales Grid */}
      <Grid container spacing={3}>
        {filteredSales.map((sale) => {
          const isHighlighted = highlightedItemCode === sale.item_code;
          return (
          <Grid item xs={12} sm={6} lg={4} key={sale.id}>
              <Fade in={true} timeout={1000}>
            <Card 
                  ref={isHighlighted ? highlightedItemRef : undefined}
                  elevation={isHighlighted ? 8 : 2} 
              sx={{ 
                height: '100%', 
                display: 'flex', 
                flexDirection: 'column',
                transition: 'transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out',
                    border: isHighlighted ? 3 : 0,
                    borderColor: isHighlighted ? 'success.main' : 'transparent',
                    backgroundColor: isHighlighted ? 'success.light' : 'background.paper',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: theme.shadows[8],
                }
              }}
            >
              <CardContent sx={{ flexGrow: 1 }}>
                {/* Item Code */}
                <Typography variant="body2" color="text.secondary" gutterBottom>
                  Item #{sale.item_code}
                </Typography>

                {/* Description */}
                <Typography variant="h6" component="h3" gutterBottom sx={{ fontWeight: 'bold', minHeight: '3em' }}>
                  {sale.description}
                </Typography>

                {/* Sale Type Badge */}
                <Box mb={2}>
                  <Chip
                    label={getSaleTypeLabel(sale.sale_type)}
                    color={getSaleTypeColor(sale.sale_type)}
                    size="small"
                    sx={{ fontWeight: 'bold' }}
                  />
                </Box>

                <Divider sx={{ my: 2 }} />

                {/* Pricing Information */}
                <Box mb={2}>
                  {(() => {
                    const instantRebate = toNumber(sale.instant_rebate);
                    const salePrice = toNumber(sale.sale_price);
                    const regularPrice = toNumber(sale.regular_price);
                    const savings = toNumber(sale.savings);

                    if ((sale.sale_type === 'discount_only' || sale.sale_type === 'instant_rebate') && 
                        instantRebate !== null && salePrice === null) {
                      return (
                        <Box>
                          <Typography variant="h5" color="success.main" fontWeight="bold">
                            ${instantRebate.toFixed(2)} OFF
                          </Typography>
                          <Typography variant="body2" color="text.secondary">
                            Discount applied at checkout
                          </Typography>
                        </Box>
                      );
                    }

                    return (
                      <Box>
                        <Box display="flex" alignItems="baseline" gap={1}>
                          <Typography variant="h5" color="success.main" fontWeight="bold">
                            {formatPrice(salePrice)}
                          </Typography>
                          {regularPrice !== null && (
                            <Typography 
                              variant="body1" 
                              color="text.secondary"
                              sx={{ textDecoration: 'line-through' }}
                            >
                              {formatPrice(regularPrice)}
                            </Typography>
                          )}
                        </Box>
                        {savings !== null && (
                          <Box display="flex" alignItems="center" mt={1}>
                            <SavingsIcon sx={{ fontSize: 16, color: 'success.main', mr: 0.5 }} />
                            <Typography variant="body2" color="success.main" fontWeight="bold">
                              Save ${savings.toFixed(2)}
                            </Typography>
                          </Box>
                        )}
                      </Box>
                    );
                  })()}
                </Box>

                {/* Time Remaining */}
                <Box display="flex" alignItems="center" mt={2}>
                  <TimeIcon 
                    sx={{ 
                      fontSize: 16, 
                      color: sale.promotion.days_remaining <= 3 ? 'error.main' : 'warning.main', 
                      mr: 0.5 
                    }} 
                  />
                  <Typography 
                    variant="body2" 
                    color={sale.promotion.days_remaining <= 3 ? "error.main" : "warning.main"}
                    fontWeight="medium"
                  >
                    {formatDaysRemaining(sale.promotion.days_remaining)}
                  </Typography>
                </Box>

                {/* Promotion Title */}
                <Typography variant="body2" color="text.secondary" mt={1}>
                  From: {sale.promotion.title}
                </Typography>
              </CardContent>
            </Card>
          </Fade>
          </Grid>
      );
    })}
      </Grid>

      {filteredSales.length === 0 && searchTerm && (
        <Box textAlign="center" py={8}>
          <SearchIcon sx={{ fontSize: 80, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h5" gutterBottom color="text.secondary">
            No results found
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Try adjusting your search terms or filters.
          </Typography>
        </Box>
      )}
    </Container>
  );
};

export default OnSale; 