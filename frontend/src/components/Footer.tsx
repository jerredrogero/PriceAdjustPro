import React from 'react';
import { 
  Box, 
  Container, 
  Typography, 
  Link, 
  Grid,
  Divider
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';

const Footer: React.FC = () => {
  const currentYear = new Date().getFullYear();

  return (
    <Box
      component="footer"
      sx={{
        mt: 'auto',
        py: 3,
        px: 2,
        backgroundColor: (theme) =>
          theme.palette.mode === 'light'
            ? theme.palette.grey[200]
            : theme.palette.grey[800],
      }}
    >
      <Container maxWidth="lg">
        <Grid container spacing={4} justifyContent="space-between" alignItems="center">
          <Grid item xs={12} sm={6}>
            <Typography variant="body2" color="text.secondary">
              © {currentYear} PriceAdjustPro. All rights reserved.
            </Typography>
          </Grid>
          
          <Grid item xs={12} sm={6}>
            <Box sx={{ display: 'flex', justifyContent: { xs: 'center', sm: 'flex-end' }, gap: 3 }}>
              <Link
                component={RouterLink}
                to="/privacy-policy"
                variant="body2"
                color="text.secondary"
                underline="hover"
              >
                Privacy Policy
              </Link>
              <Link
                component={RouterLink}
                to="/terms-of-service"
                variant="body2"
                color="text.secondary"
                underline="hover"
              >
                Terms of Service
              </Link>
            </Box>
          </Grid>
        </Grid>
        
        <Divider sx={{ my: 2 }} />
        
        <Box sx={{ textAlign: 'center' }}>
          <Typography variant="body2" color="text.secondary">
            Helping Costco shoppers save money through intelligent price tracking
          </Typography>
        </Box>
      </Container>
    </Box>
  );
};

export default Footer;