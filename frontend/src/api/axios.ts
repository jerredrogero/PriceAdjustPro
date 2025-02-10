import axios from 'axios';

// Get the CSRF token from the cookie
function getCookie(name: string): string | null {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop()?.split(';').shift() || null;
  return null;
}

// Configure axios defaults
const instance = axios.create();

// Add request interceptor to include CSRF token
instance.interceptors.request.use((config) => {
  // Get the CSRF token from cookie
  const csrfToken = getCookie('csrftoken');
  
  if (csrfToken) {
    // Add the CSRF token to the headers
    config.headers['X-CSRFToken'] = csrfToken;
  }
  
  return config;
});

export default instance; 