import React from 'react';
import { useAuth } from '../context/MockAuthContext';
import TechDashboardComponent from '../components/TechDashboard';

const TechDashboard = () => {
  const { userRole, logout } = useAuth();
  
  return (
    <div className="erp-login-container">
      <div className="erp-login-card">
        <h2>Technician Dashboard</h2>
        <p>Floor access granted.</p>
        <div className={`erp-status-message success`}>
          Active Role: {userRole}
        </div>
        <button onClick={logout} className="erp-submit-btn" style={{ marginBottom: '20px' }}>
          Terminate Session
        </button>
        <hr className="erp-divider" style={{ border: '1px solid #333', marginBottom: '20px' }} />
        <TechDashboardComponent />
      </div>
    </div>
  );
};

export default TechDashboard;
