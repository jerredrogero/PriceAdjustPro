import axios from 'axios';

// Get the CSRF token from the cookie
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

// Configure base URL
const baseURL = process.env.NODE_ENV === 'development' 
  ? 'http://localhost:8000'  // Development server
  : '';  // Production server (relative to current domain)

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

export default instance; 