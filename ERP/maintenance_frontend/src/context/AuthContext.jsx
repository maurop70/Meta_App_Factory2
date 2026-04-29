import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { setAccessToken, triggerRefresh } from '../services/api';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
    const [userRole, setUserRole] = useState(null);
    const [jwtPayload, setJwtPayload] = useState(null);
    const [isBootstrapped, setIsBootstrapped] = useState(false);
    const refreshTimerRef = useRef(null);
    const isLoggedOutRef = useRef(false);

    const clearRefreshTimer = () => {
        if (refreshTimerRef.current) {
            clearTimeout(refreshTimerRef.current);
            refreshTimerRef.current = null;
        }
    };

    const logout = () => {
        isLoggedOutRef.current = true;
        clearRefreshTimer();
        setAccessToken(null);
        setUserRole(null);
        setJwtPayload(null);
        // Add React Router navigation here depending on your routing setup
    };

    const setupProactiveRefresh = (token) => {
        if (isLoggedOutRef.current || !token) return;
        clearRefreshTimer();
        
        try {
            // SILENT PATCH: Fixed split() array indexing to prevent TypeError
            const payloadBase64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
            const payloadJson = atob(payloadBase64);
            const payload = JSON.parse(payloadJson);
            const expTimeMs = payload.exp * 1000;
            const currentTimeMs = Date.now();
            
            const timeUntilRefreshMs = (expTimeMs - currentTimeMs) - (60 * 1000);
            
            if (timeUntilRefreshMs > 0) {
                refreshTimerRef.current = setTimeout(async () => {
                    if (isLoggedOutRef.current) return; // Strict unmounted mutation check
                    try {
                        const newToken = await triggerRefresh();
                        setupProactiveRefresh(newToken);
                    } catch (err) {
                        logout();
                    }
                }, timeUntilRefreshMs);
            } else {
                triggerRefresh().then(newToken => setupProactiveRefresh(newToken)).catch(logout);
            }
        } catch (err) {
            console.error("JWT Decode Error", err);
            logout();
        }
    };

    const authenticateContext = (token, role, payload) => {
        isLoggedOutRef.current = false;
        setAccessToken(token);
        setUserRole(role);
        setJwtPayload(payload);
        setupProactiveRefresh(token);
    };

    // SYSTEM BOOTSTRAP & EVENT LISTENER
    useEffect(() => {
        const handleAuthTermination = () => logout();
        window.addEventListener('auth:termination', handleAuthTermination);

        const bootstrapSession = async () => {
            try {
                // Attempt to silently reconstruct session from HttpOnly cookie on F5
                const token = await triggerRefresh();
                const payloadBase64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
                const payload = JSON.parse(atob(payloadBase64));
                
                // Assuming 'role' or equivalent key exists in your JWT payload
                authenticateContext(token, payload.role || payload.sub_role, payload); 
            } catch (error) {
                // Initial session reconstruction failed (user is logged out)
            } finally {
                setIsBootstrapped(true);
            }
        };

        bootstrapSession();

        return () => {
            window.removeEventListener('auth:termination', handleAuthTermination);
            clearRefreshTimer();
        };
    }, []);

    // Prevent rendering protected routes until session reconstruction resolves
    if (!isBootstrapped) return null; // Or insert a global strict loading indicator here

    return (
        <AuthContext.Provider value={{ userRole, jwtPayload, authenticateContext, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);
