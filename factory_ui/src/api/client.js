import axios from 'axios';

// ============================================================================
// Centralized API Client Interception System (Antigravity Synthesis Node)
// ============================================================================

// Intercept the default global axios instance (and all custom instances that import from axios)
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response ? error.response.status : null;
    const is5xx = status && status >= 500 && status < 600;
    const isTimeout = error.code === 'ECONNABORTED' || error.message?.toLowerCase().includes('timeout') || error.message?.toLowerCase().includes('network error');

    if (is5xx || isTimeout) {
      const payload = {
        type: is5xx ? '5XX_ERROR' : 'TIMEOUT_ERROR',
        status: status || 'TIMEOUT',
        statusText: error.response ? error.response.statusText : 'Network Timeout / Connection Severed',
        message: error.message || 'The request timed out or connection failed.',
        url: error.config?.url || 'Unknown Endpoint',
        method: error.config?.method?.toUpperCase() || 'UNKNOWN',
        timestamp: Date.now()
      };

      console.warn('⚠️ [API INTERCEPTOR] Global Error Trapped:', payload);
      // Dispatch a custom event globally to trigger the blocking overlay instantly
      window.dispatchEvent(new CustomEvent('global-api-error', { detail: payload }));
    }

    return Promise.reject(error);
  }
);

// Intercept native window.fetch as well to trap non-Axios API calls
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  try {
    const response = await originalFetch(...args);
    
    if (response.status >= 500 && response.status < 600) {
      let errorData = null;
      try {
        errorData = await response.clone().json();
      } catch {
        try {
          errorData = await response.clone().text();
        } catch {}
      }

      const payload = {
        type: '5XX_ERROR',
        status: response.status,
        statusText: response.statusText,
        message: typeof errorData === 'string' ? errorData : errorData?.message || `HTTP ${response.status}: ${response.statusText}`,
        url: typeof args[0] === 'string' ? args[0] : args[0]?.url || 'Unknown Endpoint',
        method: args[1]?.method || 'GET',
        timestamp: Date.now()
      };

      console.warn('⚠️ [FETCH INTERCEPTOR] Global Error Trapped:', payload);
      window.dispatchEvent(new CustomEvent('global-api-error', { detail: payload }));
    }
    
    return response;
  } catch (error) {
    const isTimeout = error.name === 'TimeoutError' || error.message?.toLowerCase().includes('timeout') || error.message?.toLowerCase().includes('failed to fetch') || error.message?.toLowerCase().includes('network');
    
    if (isTimeout) {
      const payload = {
        type: 'TIMEOUT_ERROR',
        status: 'TIMEOUT',
        statusText: 'Network Connection Refused / Timeout',
        message: error.message || 'Connection to the primary engine room failed.',
        url: typeof args[0] === 'string' ? args[0] : args[0]?.url || 'Unknown Endpoint',
        method: args[1]?.method || 'GET',
        timestamp: Date.now()
      };

      console.warn('⚠️ [FETCH INTERCEPTOR] Timeout Trapped:', payload);
      window.dispatchEvent(new CustomEvent('global-api-error', { detail: payload }));
    }
    throw error;
  }
};

export default axios;
