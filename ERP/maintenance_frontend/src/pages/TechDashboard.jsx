import React from 'react';
import { useAuth } from '../context/AuthContext';

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
        <button onClick={logout} className="erp-submit-btn">
          Terminate Session
        </button>
      </div>
    </div>
  );
};

export default TechDashboard;
