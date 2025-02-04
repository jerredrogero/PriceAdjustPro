import React from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  IconButton,
  Menu,
  MenuItem,
  Container,
  useTheme,
} from '@mui/material';
import {
  Receipt as ReceiptIcon,
  AccountCircle as AccountIcon,
  Upload as UploadIcon,
  LocalOffer as PriceIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const theme = useTheme();
  const { isAuthenticated, user, logout } = useAuth();
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    await logout();
    handleClose();
    navigate('/login');
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <AppBar 
      position="sticky" 
      elevation={0}
      sx={{
        backgroundColor: theme.palette.primary.main,
        borderBottom: `1px solid ${theme.palette.primary.dark}`,
      }}
    >
      <Container maxWidth="lg">
        <Toolbar sx={{ px: { xs: 0 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1 }}>
            <PriceIcon sx={{ fontSize: 32, mr: 2 }} />
            <Typography 
              variant="h5" 
              component={RouterLink} 
              to="/"
              sx={{ 
                textDecoration: 'none', 
                color: 'inherit',
                fontWeight: 600,
                letterSpacing: '-0.5px',
                display: { xs: 'none', sm: 'block' }
              }}
            >
              PriceAdjustPro
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Button
              component={RouterLink}
              to="/"
              startIcon={<ReceiptIcon />}
              sx={{
                color: 'white',
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                },
                fontWeight: 500,
              }}
            >
              Receipts
            </Button>
            
            <Button
              component={RouterLink}
              to="/upload"
              startIcon={<UploadIcon />}
              sx={{
                color: 'white',
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                },
                fontWeight: 500,
              }}
            >
              Upload
            </Button>

            <IconButton
              size="large"
              aria-label="account of current user"
              aria-controls="menu-appbar"
              aria-haspopup="true"
              onClick={handleMenu}
              sx={{
                color: 'white',
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.1)',
                },
              }}
            >
              <AccountIcon />
            </IconButton>
            <Menu
              id="menu-appbar"
              anchorEl={anchorEl}
              anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
              }}
              keepMounted
              transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
              }}
              open={Boolean(anchorEl)}
              onClose={handleClose}
              PaperProps={{
                elevation: 2,
                sx: {
                  mt: 1,
                  minWidth: 180,
                  borderRadius: 2,
                }
              }}
            >
              <MenuItem disabled sx={{ opacity: 0.7 }}>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  Signed in as {user?.username || 'User'}
                </Typography>
              </MenuItem>
              <MenuItem 
                onClick={handleLogout}
                sx={{ 
                  color: theme.palette.error.main,
                  '&:hover': {
                    backgroundColor: theme.palette.error.light + '20',
                  }
                }}
              >
                Logout
              </MenuItem>
            </Menu>
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Navigation; 