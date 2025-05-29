import React from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  IconButton,
} from '@mui/material';
import {
  TrendingDown as PriceDownIcon,
  Store as StoreIcon,
  CalendarToday as DateIcon,
  AccessTime as TimeIcon,
  Visibility as ViewIcon,
  Close as CloseIcon,
  LocalOffer as OfferIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface PriceAdjustmentInfo {
  item_code: string;
  description: string;
  current_price: number;
  lower_price: number;
  price_difference: number;
  store_location: string;
  store_number: string;
  purchase_date: string;
  days_remaining: number;
  original_store: string;
  original_store_number: string;
  data_source: string;
  is_official: boolean;
  promotion_title?: string;
  sale_type?: string;
  confidence_level: string;
  transaction_number?: string;
}

interface Props {
  adjustments: PriceAdjustmentInfo[];
  onDismiss: (itemCode: string) => void;
}

const PriceAdjustmentAlert: React.FC<Props> = ({ adjustments, onDismiss }) => {
  const navigate = useNavigate();

  if (!adjustments.length) return null;

  const totalSavings = adjustments.reduce((sum, adj) => sum + adj.price_difference, 0);

  const handleCardClick = (adjustment: PriceAdjustmentInfo) => {
    // Navigate directly to the receipt if we have the transaction number
    if (adjustment.transaction_number) {
      navigate(`/receipts/${adjustment.transaction_number}`);
    } else {
      // Fallback to receipts list
      navigate('/receipts');
    }
  };

  const formatDaysRemaining = (days: number) => {
    if (days <= 0) return "Expired";
    if (days === 1) return "1 day remaining";
    if (days <= 7) return `${days} days remaining`;
    if (days <= 30) return `${days} days remaining`;
    return `${Math.ceil(days / 30)} month${Math.ceil(days / 30) > 1 ? 's' : ''} remaining`;
  };

  const getConfidenceColor = (level: string) => {
    switch (level) {
      case 'high': return 'success';
      case 'medium': return 'warning';
      default: return 'default';
    }
  };

  const getSourceLabel = (source: string, isOfficial: boolean) => {
    if (isOfficial) return 'Official Promotion';
    if (source === 'ocr_parsed') return 'Community Deal';
    if (source === 'user_edit') return 'User Reported';
    return 'Price Alert';
  };

  return (
    <Box sx={{ mb: 4 }}>
      <Alert 
        severity="info" 
        variant="outlined"
        icon={<PriceDownIcon />}
        sx={{ mb: 2 }}
      >
        <AlertTitle>💰 Price Adjustment Opportunities</AlertTitle>
        <Typography variant="body1">
          You may be eligible for price adjustments on {adjustments.length} item{adjustments.length > 1 ? 's' : ''}.
          <strong> Total potential savings: ${totalSavings.toFixed(2)}</strong>
        </Typography>
      </Alert>

      {adjustments.map((adjustment) => (
        <Card 
          key={adjustment.item_code} 
          sx={{ 
            mb: 2, 
            borderLeft: 4, 
            borderColor: adjustment.is_official ? 'success.main' : 'info.main',
            cursor: 'pointer',
            transition: 'all 0.2s ease-in-out',
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: 3,
            }
          }}
          onClick={() => handleCardClick(adjustment)}
        >
          <CardContent>
            {/* Header with item name and dismiss button */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h5" gutterBottom sx={{ fontWeight: 'bold', color: 'primary.main' }}>
                  {adjustment.description}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                  <Chip 
                    size="small" 
                    label={getSourceLabel(adjustment.data_source, adjustment.is_official)}
                    color={adjustment.is_official ? 'success' : 'primary'}
                    icon={adjustment.is_official ? <OfferIcon /> : undefined}
                  />
                  <Chip 
                    size="small" 
                    label={`${adjustment.confidence_level} confidence`}
                    color={getConfidenceColor(adjustment.confidence_level) as any}
                    variant="outlined"
                  />
                </Box>
                {adjustment.promotion_title && (
                  <Typography variant="body2" color="success.main" sx={{ fontStyle: 'italic' }}>
                    📢 {adjustment.promotion_title}
                  </Typography>
                )}
              </Box>
              <IconButton 
                onClick={(e) => {
                  e.stopPropagation();
                  onDismiss(adjustment.item_code);
                }}
                size="small"
                sx={{ color: 'text.secondary' }}
              >
                <CloseIcon />
              </IconButton>
            </Box>

            {/* Main content grid */}
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3, mb: 2 }}>
              {/* Left column - Purchase info */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1, color: 'text.secondary' }}>
                  Original Purchase
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <StoreIcon sx={{ color: 'text.secondary', fontSize: 18 }} />
                    <Typography variant="body2">
                      {adjustment.original_store} {adjustment.original_store_number && adjustment.original_store_number.toLowerCase() !== 'null' ? `#${adjustment.original_store_number}` : ''}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <DateIcon sx={{ color: 'text.secondary', fontSize: 18 }} />
                    <Typography variant="body2">
                      Purchased: {new Date(adjustment.purchase_date).toLocaleDateString('en-US', { 
                        year: 'numeric', 
                        month: 'long', 
                        day: 'numeric' 
                      })}
                    </Typography>
                  </Box>
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">Original Price:</Typography>
                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                      ${adjustment.current_price.toFixed(2)}
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {/* Right column - Sale info */}
              <Box>
                <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1, color: 'success.main' }}>
                  Available Deal
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <StoreIcon sx={{ color: 'success.main', fontSize: 18 }} />
                    <Typography variant="body2">
                      Available at: {adjustment.store_location} {adjustment.store_number && adjustment.store_number.toLowerCase() !== 'null' ? `#${adjustment.store_number}` : ''}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TimeIcon sx={{ color: adjustment.days_remaining <= 7 ? 'error.main' : 'warning.main', fontSize: 18 }} />
                    <Typography 
                      variant="body2" 
                      color={adjustment.days_remaining <= 7 ? "error.main" : "warning.main"}
                      sx={{ fontWeight: 'medium' }}
                    >
                      {formatDaysRemaining(adjustment.days_remaining)}
                    </Typography>
                  </Box>
                  <Box sx={{ mt: 1 }}>
                    <Typography variant="body2" color="text.secondary">Sale Price:</Typography>
                    <Typography variant="h6" sx={{ fontWeight: 'bold', color: 'success.main' }}>
                      ${adjustment.lower_price.toFixed(2)}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </Box>

            {/* Savings highlight */}
            <Box 
              sx={{ 
                backgroundColor: 'success.light',
                borderRadius: 2,
                p: 2,
                textAlign: 'center',
                border: '2px solid',
                borderColor: 'success.main'
              }}
            >
              <Typography variant="h4" sx={{ fontWeight: 'bold', color: 'success.contrastText' }}>
                Save ${adjustment.price_difference.toFixed(2)}
              </Typography>
              {adjustment.sale_type && (
                <Typography variant="body2" sx={{ color: 'success.contrastText', mt: 0.5 }}>
                  {adjustment.sale_type === 'discount_only' ? 'Instant Rebate Available' : 'Sale Price Available'}
                </Typography>
              )}
            </Box>

            {/* Action buttons */}
            <Box sx={{ display: 'flex', gap: 1, mt: 2, justifyContent: 'center' }}>
              <Button 
                variant="contained" 
                startIcon={<ViewIcon />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleCardClick(adjustment);
                }}
              >
                View Receipt
              </Button>
              <Button 
                variant="outlined" 
                color="secondary"
                onClick={(e) => {
                  e.stopPropagation();
                  onDismiss(adjustment.item_code);
                }}
              >
                Dismiss Alert
              </Button>
            </Box>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
};

export default PriceAdjustmentAlert; 