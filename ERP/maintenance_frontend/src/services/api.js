import axios from 'axios';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000',
  headers: { 'Content-Type': 'application/json' },
});

// Interceptor to parse FastAPI errors into clean strings
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.data?.detail) {
      const detail = error.response.data.detail;
      error.response.data.detail = Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : JSON.stringify(detail);
    }
    return Promise.reject(error);
  }
);

export default api;
