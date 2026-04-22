import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import './App.css'; // Strictly Native Vanilla CSS

// Import actual component files
import TechDashboard from './pages/TechDashboard';
import AdminConsole from './pages/AdminConsole';
import Login from './pages/Login';

// Role-Gating Security Component
const ProtectedRoute = ({ allowedRoles, children }) => {
  const { isAuthenticated, userRole } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && !allowedRoles.includes(userRole)) {
    return <Navigate to="/" replace />;
  }

  return children;
};

// Dynamic Home Router
const RoleRouter = () => {
  const { isAuthenticated, userRole } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return userRole === 'Admin' ? <Navigate to="/admin" replace /> : <Navigate to="/tech" replace />;
};

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="erp-app-container">
          <Routes>
            {/* Public Authentication Gate */}
            <Route path="/login" element={<Login />} />

            {/* Base Routing */}
            <Route path="/" element={<RoleRouter />} />

            {/* Quarantined Admin Space */}
            <Route
              path="/admin/*"
              element={
                <ProtectedRoute allowedRoles={['Admin']}>
                  <AdminConsole />
                </ProtectedRoute>
              }
            />

            {/* Technician Floor Access */}
            <Route
              path="/tech/*"
              element={
                <ProtectedRoute allowedRoles={['Technician', 'Admin']}>
                  <TechDashboard />
                </ProtectedRoute>
              }
            />

            {/* Fallback Catch-All */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
