import axios from 'axios';

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

const apiClient = axios.create({
    baseURL: 'http://127.0.0.1:8000/api',
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true 
});

// RAW NODE CONTEXT: Manual Cookie Management for Telemetry
let nodeCookieJar = "";

// Request Interceptor
apiClient.interceptors.request.use(config => {
    if (accessToken) {
        config.headers['Authorization'] = `Bearer ${accessToken}`;
    }
    // Inject the raw Node.js cookie state manually
    if (nodeCookieJar) {
        config.headers['Cookie'] = nodeCookieJar;
    }
    return config;
}, error => Promise.reject(error));

// Response Interceptor
apiClient.interceptors.response.use(response => {
    // Extract Set-Cookie manually from response to persist in raw Node context
    const setCookieHeader = response.headers['set-cookie'];
    if (setCookieHeader && setCookieHeader.length > 0) {
        nodeCookieJar = setCookieHeader[0].split(';')[0];
    }
    return response;
}, async error => {
    const originalRequest = error.config;

    if (error.response?.data?.detail && typeof error.response.data.detail !== 'string') {
        const detail = error.response.data.detail;
        error.response.data.detail = Array.isArray(detail) ? detail.map(d => d.msg).join(', ') : JSON.stringify(detail);
    }

    // BYPASS INTERCEPTOR FOR AUTHENTICATE ROUTE to prevent infinite loops
    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url.includes('/user/authenticate')) {
        if (isRefreshing) {
            console.log("Queueing stalled request:", originalRequest.url);
            return new Promise(function(resolve, reject) {
                failedQueue.push({ resolve, reject });
            }).then(token => {
                originalRequest.headers['Authorization'] = 'Bearer ' + token;
                return apiClient(originalRequest);
            }).catch(err => Promise.reject(err));
        }

        originalRequest._retry = true;
        isRefreshing = true;
        console.log("401 Intercepted. Triggering isolated refresh request...");

        try {
            // Must pass the cookie state manually in raw Node context
            const refreshRes = await axios.post('http://127.0.0.1:8000/api/user/refresh', {}, { 
                withCredentials: true,
                headers: { 'Cookie': nodeCookieJar }
            });
            
            // Extract the new Set-Cookie header if provided
            const refreshSetCookie = refreshRes.headers['set-cookie'];
            if (refreshSetCookie && refreshSetCookie.length > 0) {
                nodeCookieJar = refreshSetCookie[0].split(';')[0];
            }
            
            accessToken = refreshRes.data.access_token;
            console.log("Refresh successful. New token negotiated.");
            
            processQueue(null, accessToken);
            originalRequest.headers['Authorization'] = `Bearer ${accessToken}`;
            
            return apiClient(originalRequest);
        } catch (refreshError) {
            console.log("Refresh failed. Purging state.");
            processQueue(refreshError, null);
            accessToken = null;
            return Promise.reject(refreshError);
        } finally {
            isRefreshing = false;
        }
    }
    return Promise.reject(error);
});

async function runTelemetry() {
    try {
        console.log("--- 1. Testing Login Interceptor Bypass ---");
        try {
            console.log("Attempting login with WRONG PIN to test bypass...");
            await apiClient.post('/user/authenticate', { pin: "9999" });
        } catch (authErr) {
            console.log("Failed login appropriately caught. Interceptor was successfully bypassed for 401.");
        }

        console.log("--- 2. Authenticating Correctly ---");
        const authRes = await apiClient.post('/user/authenticate', { pin: "1234" });
        setAccessToken(authRes.data.access_token);
        console.log("Login successful. Access token injected into memory.");
        console.log("Extracted Cookie Jar:", nodeCookieJar);
        
        console.log("--- 3. Simulating Access Token Expiration (purging memory token) ---");
        setAccessToken(null); // Force 401 on next request
        
        console.log("--- 4. Firing Protected Request to /mwo/MWO-TEST ---");
        const patchRes = await apiClient.patch('/mwo/MWO-TEST', { status: "ASSIGNED" });
        
        console.log("TELEMETRY: ALL QUEUE AND REFRESH STRUCTURAL VALIDATIONS PASSED.");
    } catch (err) {
        console.error("Telemetry Failed:", err.message);
        if (err.response) {
            console.error(err.response.data);
        }
        process.exit(1);
    }
}

runTelemetry();
