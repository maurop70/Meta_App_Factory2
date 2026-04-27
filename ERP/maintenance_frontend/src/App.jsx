import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import './App.css'; // Strictly Native Vanilla CSS

// Import actual component files
import TechDashboard from './pages/TechDashboard';
import AdminConsole from './pages/AdminConsole';
import Login from './pages/Login';
import MWODashboard from './components/MWODashboard'; // HM Feed
import CreateMWOForm from './components/CreateMWOForm'; // DM Submission

// Strict Role-Gating Security Component
const ProtectedRoute = ({ allowedRoles, children }) => {
  const { userRole } = useAuth();
  
  // Strict Enforcement: No coercing non-matching strings.
  // If the payload does not explicitly match the allowed operational tiers, bounce immediately.
  if (!allowedRoles || !allowedRoles.includes(userRole)) {
    return <Navigate to="/" replace />;
  }

  return children;
};

// Dynamic Home Router maps explicit roles to their terminal paths
const RoleRouter = () => {
  const { userRole } = useAuth();
  
  switch (userRole) {
    case 'ADMINISTRATOR':
    case 'ADMIN':
      return <Navigate to="/admin" replace />;
    case 'DM':
      return <Navigate to="/dm" replace />;
    case 'HM':
      return <Navigate to="/hm" replace />;
    case 'TECHNICIAN':
    case 'TECH':
      return <Navigate to="/tech" replace />;
    default:
      // Fallback for unauthenticated or non-matching payload strings
      return <Navigate to="/login" replace />;
  }
};

function App() {
  return (
    <AuthProvider>
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

            {/* Global Console: Tabbed Visibility for Administrator */}
            <Route
              path="/admin/*"
              element={
                <ProtectedRoute allowedRoles={['ADMINISTRATOR', 'ADMIN']}>
                  <AdminConsole />
                </ProtectedRoute>
              }
            />

            {/* Department Manager (DM) Submission View */}
            <Route
              path="/dm/*"
              element={
                <ProtectedRoute allowedRoles={['DM']}>
                  <CreateMWOForm />
                </ProtectedRoute>
              }
            />

            {/* Head Maintenance (HM) Command Feed */}
            <Route
              path="/hm/*"
              element={
                <ProtectedRoute allowedRoles={['HM']}>
                  <MWODashboard />
                </ProtectedRoute>
              }
            />

            {/* Technician Execution Floor */}
            <Route
              path="/tech/*"
              element={
                <ProtectedRoute allowedRoles={['TECHNICIAN', 'TECH']}>
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
