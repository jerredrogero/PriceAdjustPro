import { createTheme } from '@mui/material/styles';

// Costco brand colors
const costcoRed = '#E31837';  // Primary Costco red
const costcoBlue = '#005DAA'; // Costco blue
const darkRed = '#C41230';    // Darker shade for hover states
const lightRed = '#FF1A1A';   // Lighter shade for accents

const theme = createTheme({
  palette: {
    primary: {
      main: costcoRed,
      dark: darkRed,
      light: lightRed,
      contrastText: '#ffffff',
    },
    secondary: {
      main: costcoBlue,
      contrastText: '#ffffff',
    },
    background: {
      default: '#f8f9fa',
      paper: '#ffffff',
    },
    text: {
      primary: '#2A2A2A',
      secondary: '#666666',
    },
  },
  typography: {
    fontFamily: '"Helvetica Neue", "Segoe UI", Roboto, Arial, sans-serif',
    h4: {
      fontWeight: 600,
      letterSpacing: '-0.5px',
    },
    h5: {
      fontWeight: 600,
      letterSpacing: '-0.5px',
    },
    h6: {
      fontWeight: 500,
      letterSpacing: '-0.25px',
    },
    button: {
      fontWeight: 500,
      letterSpacing: '0.25px',
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: 8,
          padding: '8px 16px',
          fontWeight: 500,
          '&:hover': {
            transform: 'translateY(-1px)',
            boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)',
          },
          transition: 'all 0.2s ease-in-out',
        },
        contained: {
          boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        },
        elevation1: {
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        },
        elevation2: {
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 500,
          '&.MuiChip-outlined': {
            borderWidth: 1.5,
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
        standardWarning: {
          backgroundColor: '#FFF4E5',
          color: '#663C00',
        },
        standardError: {
          backgroundColor: '#FFF5F5',
          color: '#CC0000',
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          '& .MuiTableCell-head': {
            fontWeight: 600,
            backgroundColor: costcoRed,
            color: '#ffffff',
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          padding: '16px',
        },
      },
    },
  },
});

export default theme; 