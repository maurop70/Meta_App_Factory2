import axios from 'axios';
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

let accessToken = null;
let isRefreshing = false;
let failedQueue = [];

export const setAccessToken = (token) => {
    accessToken = token;
};

const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

export const triggerRefresh = async () => {
    if (isRefreshing) {
        return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
        });
    }
    isRefreshing = true;
    try {
        const { data } = await axios.post(`${API_BASE_URL}/user/refresh`, {}, { withCredentials: true });
        setAccessToken(data.access_token);
        processQueue(null, data.access_token);
        return data.access_token;
    } catch (refreshError) {
        processQueue(refreshError, null);
        setAccessToken(null);
        // Decouple network layer from UI. Broadcast destruction event.
        window.dispatchEvent(new CustomEvent('auth:termination'));
        return Promise.reject(refreshError);
    } finally {
        isRefreshing = false;
    }
};

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true 
});

apiClient.interceptors.request.use(config => {
    if (accessToken) {
        config.headers['Authorization'] = `Bearer ${accessToken}`;
    }
    return config;
}, error => Promise.reject(error));

apiClient.interceptors.response.use(async response => {
    if (response.status === 205 && response.headers['x-token-flush'] === 'true') {
        setAccessToken(null);
        try {
            await triggerRefresh();
        } catch (err) {
            console.error("Proactive token flush failed during refresh", err);
        }
    }
    return response;
}, async error => {
    const originalRequest = error.config;
    if (error.response?.data?.detail && typeof error.response.data.detail !== 'string') {
        const detail = error.response.data.detail;
        error.response.data.detail = Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : JSON.stringify(detail);
    }
    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url.includes('/user/authenticate')) {
        originalRequest._retry = true;
        try {
            const token = await triggerRefresh();
            originalRequest.headers['Authorization'] = `Bearer ${token}`;
            return apiClient(originalRequest);
        } catch (err) {
            return Promise.reject(err);
        }
    }
    return Promise.reject(error);
});

export default apiClient;
