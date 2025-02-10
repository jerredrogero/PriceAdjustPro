import React from 'react';
import {
  Alert,
  AlertTitle,
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Collapse,
} from '@mui/material';
import {
  TrendingDown as PriceDownIcon,
  Store as StoreIcon,
  CalendarToday as DateIcon,
} from '@mui/icons-material';

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
}

interface Props {
  adjustments: PriceAdjustmentInfo[];
  onDismiss: (itemCode: string) => void;
}

const PriceAdjustmentAlert: React.FC<Props> = ({ adjustments, onDismiss }) => {
  if (!adjustments.length) return null;

  const totalSavings = adjustments.reduce((sum, adj) => sum + adj.price_difference, 0);

  return (
    <Box sx={{ mb: 4 }}>
      <Alert 
        severity="info" 
        variant="outlined"
        icon={<PriceDownIcon />}
        sx={{ mb: 2 }}
      >
        <AlertTitle>Price Adjustment Opportunities</AlertTitle>
        <Typography variant="body1">
          You may be eligible for price adjustments on {adjustments.length} item{adjustments.length > 1 ? 's' : ''}.
          Total potential savings: ${totalSavings.toFixed(2)}
        </Typography>
      </Alert>

      {adjustments.map((adjustment) => (
        <Collapse key={adjustment.item_code} in={true}>
          <Card sx={{ mb: 2, borderLeft: 4, borderColor: 'info.main' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 2 }}>
                <Box>
                  <Typography variant="h6" gutterBottom>
                    {adjustment.description}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Item #{adjustment.item_code}
                  </Typography>
                </Box>
                <Box sx={{ textAlign: 'right' }}>
                  <Typography 
                    variant="h6" 
                    color="success.main"
                    sx={{ 
                      backgroundColor: 'success.light',
                      color: 'success.contrastText',
                      px: 2,
                      py: 1,
                      borderRadius: 2,
                      mb: 1
                    }}
                  >
                    Save ${adjustment.price_difference.toFixed(2)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    Original: ${adjustment.current_price.toFixed(2)}
                  </Typography>
                  <Typography variant="body2" color="success.main">
                    New: ${adjustment.lower_price.toFixed(2)}
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <StoreIcon color="error" />
                  <Typography variant="body2">
                    Purchased at: {adjustment.original_store} #{adjustment.original_store_number}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <StoreIcon color="success" />
                  <Typography variant="body2">
                    Lower price at: {adjustment.store_location} #{adjustment.store_number}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <DateIcon color="action" />
                  <Typography variant="body2">
                    Purchased on {new Date(adjustment.purchase_date).toLocaleDateString()}
                  </Typography>
                </Box>
              </Box>

              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography 
                  variant="body2" 
                  color={adjustment.days_remaining < 7 ? "error.main" : "warning.main"}
                  sx={{ fontWeight: 'medium' }}
                >
                  {adjustment.days_remaining} days remaining for adjustment
                </Typography>
                <Button 
                  variant="outlined" 
                  color="primary"
                  onClick={() => onDismiss(adjustment.item_code)}
                >
                  Dismiss
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Collapse>
      ))}
    </Box>
  );
};

export default PriceAdjustmentAlert; 