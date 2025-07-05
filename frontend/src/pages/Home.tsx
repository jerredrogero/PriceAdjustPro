import React, { useEffect, useState } from 'react';
import { Container, Typography, Box, Alert, Chip } from '@mui/material';
import PriceAdjustmentBanner from '../components/PriceAdjustmentBanner';
import ReceiptList from '../components/ReceiptList';

interface PriceAdjustmentSummary {
  adjustmentCount: number;
  totalSavings: number;
}

const Home: React.FC = () => {
  const [adjustments, setAdjustments] = useState<PriceAdjustmentSummary>({
    adjustmentCount: 0,
    totalSavings: 0
  });

  useEffect(() => {
    fetchAdjustments();
  }, []);

  const fetchAdjustments = async () => {
    try {
      const response = await fetch('/api/price-adjustments/');
      if (response.ok) {
        const data = await response.json();
        setAdjustments({
          adjustmentCount: data.adjustments.length,
          totalSavings: data.total_potential_savings
        });
      }
    } catch (error) {
      console.error('Failed to fetch adjustments:', error);
    }
  };

  return (
    <Container maxWidth="lg">

      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Welcome to PriceAdjustPro
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          Track your Costco receipts and get money back when prices drop
        </Typography>
      </Box>

      <PriceAdjustmentBanner
        adjustmentCount={adjustments.adjustmentCount}
        totalSavings={adjustments.totalSavings}
      />

      <ReceiptList />
    </Container>
  );
};

export default Home; 