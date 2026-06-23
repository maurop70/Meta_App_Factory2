import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import './App.css'; // Strictly Native Vanilla CSS

// Import actual component files
import TechDashboard from './pages/TechDashboard';
import AdminConsole from './pages/AdminConsole';
import Login from './pages/Login';
import HMDashboard from './components/HMDashboard'; // HM Feed
import CreateMWOForm from './components/CreateMWOForm'; // DM Submission
import ArchiveDashboard from './components/ArchiveDashboard'; // Unified Archive
import CFODashboard from './pages/CFODashboard'; // CFO PO Approval Gateway
import ProfileSettings from './components/ProfileSettings'; // First-time activation gate

// Strict Role-Gating Security Component
const ProtectedRoute = ({ allowedRoles, children }) => {
  const { userRole, jwtPayload } = useAuth();
  
  // Synchronous deep-inspection of JWT payload
  if (!jwtPayload) {
    return <Navigate to="/login" replace />;
  }
  
  // Verify expiration
  const currentTimeMs = Date.now();
  if (jwtPayload.exp * 1000 < currentTimeMs) {
    return <Navigate to="/login" replace />;
  }

  // Strict Enforcement: No coercing non-matching strings.
  // If the payload does not explicitly match the allowed operational tiers, bounce immediately.
  if (!allowedRoles || !allowedRoles.includes(userRole) || !allowedRoles.includes(jwtPayload.role)) {
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
    case 'CFO':
      return <Navigate to="/cfo" replace />;
    case 'TECHNICIAN':
    case 'TECH':
      return <Navigate to="/tech" replace />;
    default:
      // Fallback for unauthenticated or non-matching payload strings
      return <Navigate to="/login" replace />;
  }
};

// First-time activation gate: an authenticated user whose JWT still carries
// setup_required must choose custom credentials before any console access. On
// completion we log them out so they re-authenticate and receive a fresh token
// with setup_required cleared.
const SetupGate = ({ children }) => {
  const { setupRequired, logout } = useAuth();
  if (setupRequired) {
    return <ProfileSettings forced onComplete={logout} />;
  }
  return children;
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
          <SetupGate>
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
                  <HMDashboard />
                </ProtectedRoute>
              }
            />

            {/* CFO Financial Actuation Gateway */}
            <Route
              path="/cfo/*"
              element={
                <ProtectedRoute allowedRoles={['CFO', 'ADMIN', 'ADMINISTRATOR']}>
                  <CFODashboard />
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

            {/* Unified Archive Dashboard */}
            <Route
              path="/archive"
              element={
                <ProtectedRoute allowedRoles={['DM', 'HM', 'TECH', 'TECHNICIAN', 'ADMIN', 'ADMINISTRATOR']}>
                  <ArchiveDashboard />
                </ProtectedRoute>
              }
            />

            {/* Fallback Catch-All */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </SetupGate>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
