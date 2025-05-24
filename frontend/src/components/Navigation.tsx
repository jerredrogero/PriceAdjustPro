import React, { useState, useEffect } from 'react';
import { Link as RouterLink, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  Button,
  Box,
  Menu,
  MenuItem,
  Badge,
  useTheme,
  useMediaQuery,
  Link,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Receipt as ReceiptIcon,
  LocalOffer as AdjustmentIcon,
  CloudUpload as UploadIcon,
  Logout as LogoutIcon,
  Analytics as AnalyticsIcon,
  Dashboard as DashboardIcon,
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
} from '@mui/icons-material';
import { useThemeContext } from '../contexts/ThemeContext';
import LogoLight from '../assets/images/PAP_LM.svg';
import LogoDark from '../assets/images/PAP_DM.svg';

// Define the User interface
interface User {
  id: number;
  username: string;
  email?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
}

// Define props for the Navigation component
interface NavigationProps {
  user: User | null;
}

const Navigation: React.FC<NavigationProps> = ({ user }) => {
  const location = useLocation();
  const theme = useTheme();
  const { mode, toggleTheme } = useThemeContext();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const isAuthenticated = !!user;
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);
  const [adjustmentCount, setAdjustmentCount] = useState(0);

  useEffect(() => {
    if (isAuthenticated) {
      fetchAdjustmentCount();
    }
  }, [isAuthenticated, location]);

  const fetchAdjustmentCount = async () => {
    try {
      const response = await fetch('/api/price-adjustments/');
      if (response.ok) {
        const data = await response.json();
        setAdjustmentCount(data.adjustments.length);
      }
    } catch (error) {
      console.error('Failed to fetch adjustment count:', error);
    }
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setMenuAnchor(event.currentTarget);
  };

  const handleMenuClose = () => {
    setMenuAnchor(null);
  };

  const handleLogout = async () => {
    try {
      // Call the API logout endpoint with JSON request
      await fetch('/api/auth/logout/', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      // Force a full page reload to clear React state and redirect to login
      window.location.href = '/login';
    } catch (error) {
      console.error('Failed to logout:', error);
      // Even if logout fails, clear the session by redirecting
      window.location.href = '/login';
    }
  };

  const menuItems = [
    { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
    { text: 'Receipts', icon: <ReceiptIcon />, path: '/receipts' },
    {
      text: 'Price Adjustments',
      icon: <AdjustmentIcon />,
      path: '/price-adjustments',
      badge: adjustmentCount,
    },
    { text: 'Analytics', icon: <AnalyticsIcon />, path: '/analytics' },
    { text: 'Upload', icon: <UploadIcon />, path: '/upload' },
  ];

  return (
    <AppBar 
      position="fixed"
      color="transparent"
      elevation={0}
      sx={{ 
        backgroundColor: '#E31837',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
      }}
    >
      <Toolbar 
        sx={{
          color: mode === 'light' ? '#ffffff' : '#000000',
          '& .MuiTypography-root': {
            color: mode === 'light' ? '#ffffff' : '#000000',
          },
          '& .MuiButton-root': {
            color: mode === 'light' ? '#ffffff' : '#000000',
          },
          '& .MuiIconButton-root': {
            color: mode === 'light' ? '#ffffff' : '#000000',
          },
          '& .MuiChip-root': {
            color: 'white', // Keep BETA chip white always
          },
        }}
      >
        {isMobile && isAuthenticated && (
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleMenuOpen}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>
        )}

        <Link
          component={RouterLink}
          to="/"
          sx={{
            textDecoration: 'none',
            color: 'inherit',
            display: 'flex',
            alignItems: 'center',
            flexGrow: 1,
          }}
        >
          <Box
            component="img"
            src={mode === 'light' ? LogoLight : LogoDark}
            alt="PriceAdjustPro Logo"
            sx={{
              height: 48,
              width: 'auto',
              mr: 1.5,
            }}
          />
          <Typography variant="h6" component="span">
            PriceAdjustPro
          </Typography>
          <Chip 
            label="BETA" 
            size="small" 
            sx={{ 
              ml: 1, 
              backgroundColor: 'secondary.main',
              color: 'white',
              fontSize: '0.7rem',
              height: '20px',
              fontWeight: 'bold'
            }} 
          />
        </Link>

        {!isAuthenticated ? (
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Button color="inherit" component={RouterLink} to="/login">
              Login
            </Button>
            <Button color="inherit" component={RouterLink} to="/register">
              Register
            </Button>
          </Box>
        ) : (
          <>
            {!isMobile && (
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {menuItems.map((item) => (
                  <Button
                    key={item.path}
                    color="inherit"
                    component={RouterLink}
                    to={item.path}
                    startIcon={
                      item.badge ? (
                        <Badge badgeContent={item.badge} color="error">
                          {item.icon}
                        </Badge>
                      ) : (
                        item.icon
                      )
                    }
                    sx={{ ml: 1 }}
                  >
                    {item.text}
                  </Button>
                ))}
                <Button
                  color="inherit"
                  onClick={handleLogout}
                  startIcon={<LogoutIcon />}
                  sx={{ ml: 1 }}
                >
                  Logout
                </Button>
              </Box>
            )}
          </>
        )}

        {/* Theme Toggle Button - Always at far right */}
        <Tooltip title={`Switch to ${mode === 'light' ? 'dark' : 'light'} mode`}>
          <IconButton
            color="inherit"
            onClick={toggleTheme}
            sx={{ ml: 1 }}
          >
            {mode === 'light' ? <DarkModeIcon /> : <LightModeIcon />}
          </IconButton>
        </Tooltip>

        <Menu
          anchorEl={menuAnchor}
          open={Boolean(menuAnchor)}
          onClose={handleMenuClose}
        >
          {menuItems.map((item) => (
            <MenuItem
              key={item.path}
              component={RouterLink}
              to={item.path}
              onClick={handleMenuClose}
            >
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {item.badge ? (
                  <Badge badgeContent={item.badge} color="error">
                    {item.icon}
                  </Badge>
                ) : (
                  item.icon
                )}
                <Typography sx={{ ml: 1 }}>{item.text}</Typography>
              </Box>
            </MenuItem>
          ))}
          {/* Theme Toggle for mobile - inside hamburger menu */}
          <MenuItem onClick={() => { handleMenuClose(); toggleTheme(); }}>
            {mode === 'light' ? <DarkModeIcon sx={{ mr: 1 }} /> : <LightModeIcon sx={{ mr: 1 }} />}
            <Typography>{mode === 'light' ? 'Dark Mode' : 'Light Mode'}</Typography>
          </MenuItem>
          <MenuItem onClick={() => { handleMenuClose(); handleLogout(); }}>
            <LogoutIcon sx={{ mr: 1 }} />
            Logout
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
};

export default Navigation; 