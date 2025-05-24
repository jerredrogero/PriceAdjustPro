import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { PaletteMode } from '@mui/material';
import CssBaseline from '@mui/material/CssBaseline';

interface ThemeContextType {
  mode: PaletteMode;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useThemeContext = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useThemeContext must be used within a ThemeContextProvider');
  }
  return context;
};

interface ThemeContextProviderProps {
  children: ReactNode;
}

export const ThemeContextProvider: React.FC<ThemeContextProviderProps> = ({ children }) => {
  const [mode, setMode] = useState<PaletteMode>('light');

  useEffect(() => {
    // Load theme preference from localStorage
    const savedMode = localStorage.getItem('themeMode') as PaletteMode;
    if (savedMode) {
      setMode(savedMode);
    }
  }, []);

  const toggleTheme = () => {
    const newMode = mode === 'light' ? 'dark' : 'light';
    setMode(newMode);
    localStorage.setItem('themeMode', newMode);
  };

  // Costco brand colors
  const costcoRed = '#E31837';
  const costcoBlue = '#005DAA';
  const darkRed = '#C41230';
  const lightRed = '#E31837';

  const theme = createTheme({
    palette: {
      mode,
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
        default: mode === 'light' ? '#f8f9fa' : '#121212',
        paper: mode === 'light' ? '#ffffff' : '#1e1e1e',
      },
      text: {
        primary: mode === 'light' ? '#2A2A2A' : '#ffffff',
        secondary: mode === 'light' ? '#666666' : '#b3b3b3',
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
            boxShadow: mode === 'light' 
              ? '0 2px 8px rgba(0, 0, 0, 0.08)' 
              : '0 2px 8px rgba(0, 0, 0, 0.3)',
          },
          elevation1: {
            boxShadow: mode === 'light' 
              ? '0 2px 8px rgba(0, 0, 0, 0.08)' 
              : '0 2px 8px rgba(0, 0, 0, 0.3)',
          },
          elevation2: {
            boxShadow: mode === 'light' 
              ? '0 4px 12px rgba(0, 0, 0, 0.1)' 
              : '0 4px 12px rgba(0, 0, 0, 0.4)',
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: 12,
            boxShadow: mode === 'light' 
              ? '0 2px 8px rgba(0, 0, 0, 0.08)' 
              : '0 2px 8px rgba(0, 0, 0, 0.3)',
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
            backgroundColor: mode === 'light' ? '#FFF4E5' : '#3d2a00',
            color: mode === 'light' ? '#663C00' : '#ffb74d',
          },
          standardError: {
            backgroundColor: mode === 'light' ? '#FFF5F5' : '#3d0a0a',
            color: mode === 'light' ? '#CC0000' : '#f48fb1',
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
      MuiAppBar: {
        styleOverrides: {
          root: {
            backgroundColor: '#E31837',
          },
          colorPrimary: {
            backgroundColor: '#E31837',
          },
        },
      },
    },
  });

  return (
    <ThemeContext.Provider value={{ mode, toggleTheme }}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </ThemeProvider>
    </ThemeContext.Provider>
  );
}; 