import React from 'react';
import { useAuth } from '../context/AuthContext';
import MWODashboard from '../components/MWODashboard';

const AdminConsole = () => {
  const { userRole, logout } = useAuth();
  
  return (
    <div className="erp-login-container" style={{ padding: '20px', maxWidth: '1200px' }}>
      <div className="erp-login-card" style={{ width: '100%', maxWidth: '100%' }}>
        <h2>Admin Command Console</h2>
        <p>Security clearance verified.</p>
        <div className={`erp-status-message success`}>
          Active Role: {userRole}
        </div>
        <button onClick={logout} className="erp-submit-btn" style={{ marginBottom: '20px' }}>
          Terminate Session
        </button>
        <hr className="erp-divider" style={{ border: '1px solid #333', marginBottom: '20px' }} />
        <MWODashboard />
      </div>
    </div>
  );
};

export default AdminConsole;
