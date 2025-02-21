import axios from 'axios';

// Get the CSRF token from the cookie
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

// Configure base URL based on environment and device type
const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
const baseURL = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:8000'  // Development server
  : isMobile 
    ? 'https://priceadjustpro.com'  // Mobile production
    : '';  // Desktop production (relative to current domain)

// Configure axios defaults
const instance = axios.create({
  baseURL,
  withCredentials: true,  // Required for cookies
  headers: {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
  }
});

// Add request interceptor
instance.interceptors.request.use((config) => {
  // For file uploads, don't set Content-Type header
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  }
  
  // Get CSRF token
  const csrfToken = getCookie('csrftoken');
  if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase() ?? '')) {
    config.headers['X-CSRFToken'] = csrfToken;
  }
  
  // Ensure URL starts with /api/
  if (!config.url?.startsWith('/api/')) {
    config.url = `/api${config.url?.startsWith('/') ? '' : '/'}${config.url}`;
  }
  
  return config;
});

// Add response interceptor to handle errors
instance.interceptors.response.use(
  (response) => response,
  (error) => {
    // Log error details for debugging
    console.error('API Error:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      data: error.response?.data,
    });

    // Handle specific error cases
    if (error.response?.status === 401) {
      // Handle unauthorized access
      window.location.href = '/login';
    }

    return Promise.reject(error);
  }
);

export default instance; 