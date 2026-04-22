import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);
  const [user, setUser] = useState(null);

  // Boot-up sequence: Read from local memory securely (Run ONCE via empty dependency array)
  useEffect(() => {
    const storedRole = localStorage.getItem('erp_role');
    const storedUser = localStorage.getItem('erp_user');
    if (storedRole) {
      setIsAuthenticated(true);
      // Capitalize role to strictly match App.jsx router expectations
      setUserRole(storedRole.charAt(0).toUpperCase() + storedRole.slice(1).toLowerCase());
      setUser(storedUser);
    }
  }, []); // <- Critical: Empty array prevents infinite loop

  const login = (role, userData, pin) => {
    const cleanRole = role.charAt(0).toUpperCase() + role.slice(1).toLowerCase();
    setIsAuthenticated(true);
    setUserRole(cleanRole);
    setUser(userData);
    localStorage.setItem('erp_role', cleanRole);
    localStorage.setItem('erp_user', typeof userData === 'string' ? userData : JSON.stringify(userData));
  };

  const logout = () => {
    setIsAuthenticated(false);
    setUserRole(null);
    setUser(null);
    localStorage.removeItem('erp_role');
    localStorage.removeItem('erp_user');
    window.location.href = '/login'; // Force hard physical redirect
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, userRole, user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
