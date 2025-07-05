import React from 'react';
import {
  Paper,
  Typography,
  Box,
  Button,
  Chip,
  useTheme,
  alpha,
} from '@mui/material';
import {
  TrendingDown as PriceDownIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface Props {
  adjustmentCount: number;
  totalSavings: number;
}

const PriceAdjustmentBanner: React.FC<Props> = ({ adjustmentCount, totalSavings }) => {
  const theme = useTheme();
  const navigate = useNavigate();

  if (adjustmentCount === 0) return null;

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        mb: 4,
        backgroundColor: alpha(theme.palette.info.main, 0.1),
        border: `1px solid ${alpha(theme.palette.info.main, 0.2)}`,
        borderRadius: 2,
      }}
    >
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <PriceDownIcon color="info" sx={{ fontSize: 32 }} />
          <Box>
            <Typography variant="h6" gutterBottom sx={{ color: 'info.main' }}>
              Eligible Refund Alert
            </Typography>
            <Typography variant="body1">
              You have {adjustmentCount} item{adjustmentCount > 1 ? 's' : ''} eligible for refunds
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Chip
            label={`$${totalSavings.toFixed(2)} in refunds`}
            color="success"
            sx={{ 
              fontWeight: 'bold',
              fontSize: '1.1rem',
              height: 'auto',
              padding: '8px 12px',
            }}
          />
          <Button
            variant="contained"
            color="info"
            endIcon={<ArrowForwardIcon />}
            onClick={() => navigate('/price-adjustments')}
            sx={{
              whiteSpace: 'nowrap',
              '&:hover': {
                backgroundColor: theme.palette.info.dark,
              },
            }}
          >
            View Details
          </Button>
        </Box>
      </Box>
    </Paper>
  );
};

export default PriceAdjustmentBanner; 