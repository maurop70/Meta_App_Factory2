import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { MockAuthProvider, LoginSimulator, useAuth } from './context/MockAuthContext';
import './App.css'; // Strictly Native Vanilla CSS

// Import actual component files
import TechDashboard from './pages/TechDashboard';
import AdminConsole from './pages/AdminConsole';
import Login from './pages/Login';

// Role-Gating Security Component
const ProtectedRoute = ({ allowedRoles, children }) => {
  const { userRole } = useAuth();
  
  // Normalize Mock Roles to App Roles
  const normalizedRole = userRole === 'HM (Admin)' ? 'Admin' : 'Technician';

  if (allowedRoles && !allowedRoles.includes(normalizedRole)) {
    return <Navigate to="/" replace />;
  }

  return children;
};

// Dynamic Home Router
const RoleRouter = () => {
  const { userRole } = useAuth();
  const isAdmin = userRole === 'HM (Admin)';
  return isAdmin ? <Navigate to="/admin" replace /> : <Navigate to="/tech" replace />;
};

function App() {
  return (
    <MockAuthProvider>
      <LoginSimulator />
      <Router>
        <div 
          className="maf-app-shell" 
          style={{ 
            minHeight: '100vh', 
            backgroundColor: 'var(--bg-dark)', 
            color: 'var(--text-primary)', 
            fontFamily: 'var(--font)',
            display: 'flex',
            flexDirection: 'column'
          }}
        >
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
    </MockAuthProvider>
  );
}

export default App;
