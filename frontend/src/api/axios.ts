import axios from 'axios';

// Get the CSRF token from the cookie
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

// Configure base URL based on environment
const baseURL = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:8000'  // Development server
  : '';  // Production server (relative to current domain)

// Configure axios defaults
axios.defaults.withCredentials = true;
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';

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
  // Ensure withCredentials is always true
  config.withCredentials = true;
  
  // For file uploads, don't set Content-Type header
  if (config.data instanceof FormData) {
    delete config.headers['Content-Type'];
  }
  
  // Get CSRF token
  const csrfToken = getCookie('csrftoken');
  if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(config.method?.toLowerCase() ?? '')) {
    config.headers['X-CSRFToken'] = csrfToken;
  }
  
  // Log all requests for debugging
  console.log('API Request:', {
    url: config.url,
    method: config.method,
    withCredentials: config.withCredentials,
    headers: config.headers,
    hasCsrf: !!csrfToken,
  });
  
  // Don't modify URLs that already include /api/
  if (!config.url?.startsWith('/api/')) {
    // Only prepend /api/ if it's not already there
    config.url = `/api${config.url?.startsWith('/') ? '' : '/'}${config.url}`;
  }
  
  return config;
}, error => {
  console.error('API Request Error:', error);
  return Promise.reject(error);
});

// Add response interceptor to handle errors
instance.interceptors.response.use(
  (response) => {
    // Log successful responses
    console.log('API Response:', {
      url: response.config.url,
      status: response.status,
      data: response.data
    });
    return response;
  },
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
      // Only redirect to login if not already on login page
      if (!window.location.pathname.includes('/login') && 
          !window.location.pathname.includes('/register')) {
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

export default instance; 